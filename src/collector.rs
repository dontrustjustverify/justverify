//! Independent read-only collection lanes. Slow block/coinbase reads never hold up
//! current chain status, network samples or the socket serving the shared cache.
use crate::{Rpc, Snapshot, clean, miner, now, probe_electrs, probe_tor};
use anyhow::{Context, Result, bail};
use serde_json::{Value, json};
use std::{
    collections::BTreeMap,
    path::Path,
    sync::{Arc, RwLock},
    thread,
    time::{Duration, Instant},
};

type Cache = Arc<RwLock<Snapshot>>;
fn publish(cache: &Cache, method: &str, result: Result<Value>) {
    let mut state = cache.write().unwrap();
    let sample = state.rpc.entry(method.into()).or_default();
    match result {
        Ok(value) => {
            sample.value = value;
            sample.updated = now();
            sample.error = None;
        }
        Err(error) => sample.error = Some(clean(&error.to_string())),
    }
    state.collected = now();
}

pub fn start(
    cache: Cache,
    port: u16,
    cookie: &Path,
    electrs_port: u16,
    tor_port: u16,
) -> Result<()> {
    let chain_rpc = Rpc::with_timeout(port, cookie, Duration::from_secs(10))?;
    let network_rpc = Rpc::new(port, cookie)?;
    let block_rpc = Rpc::with_timeout(port, cookie, Duration::from_secs(10))?;
    let miner_rpc = Rpc::with_timeout(port, cookie, Duration::from_secs(10))?;
    let chain_cache = cache.clone();
    thread::spawn(move || {
        loop {
            publish(
                &chain_cache,
                "getblockchaininfo",
                chain_rpc.call("getblockchaininfo", json!([])),
            );
            thread::sleep(Duration::from_secs(2));
        }
    });
    let network_cache = cache.clone();
    thread::spawn(move || {
        loop {
            for (method, params) in [
                ("getnetworkinfo", json!([])),
                ("getnettotals", json!([])),
                ("getmempoolinfo", json!([])),
                ("getpeerinfo", json!([])),
                ("getindexinfo", json!([])),
                ("estimatesmartfee", json!([6])),
            ] {
                publish(&network_cache, method, network_rpc.call(method, params));
            }
            thread::sleep(Duration::from_secs(2));
        }
    });
    let block_cache = cache.clone();
    thread::spawn(move || {
        loop {
            let state = block_cache.read().unwrap().clone();
            let chain = state
                .rpc
                .get("getblockchaininfo")
                .cloned()
                .unwrap_or_default();
            let previous = state.rpc.get("recentblocks").cloned().unwrap_or_default();
            let ibd = chain.value["initialblockdownload"] == true;
            if chain.updated == 0
                || chain.error.is_some()
                || now().saturating_sub(chain.updated) > 15
            {
                publish(
                    &block_cache,
                    "recentblocks",
                    Err(anyhow::anyhow!("Core status not current")),
                );
            } else {
                let tip = chain.value["bestblockhash"].as_str().unwrap_or("");
                let result = headers(&block_rpc, tip, &previous.value);
                // Coinbase enrichment may have completed while headers were loading.
                // Merge only by immutable block hash, never by height or list position.
                let result = result.map(|mut blocks| {
                    let current = block_cache.read().unwrap();
                    let old = current.rpc.get("recentblocks").map(|s| &s.value);
                    for block in blocks.as_array_mut().unwrap() {
                        if let Some(cached) = old
                            .and_then(|v| v.as_array())
                            .into_iter()
                            .flatten()
                            .find(|b| b["hash"] == block["hash"])
                        {
                            if !cached["miner"].is_null() {
                                block["miner"] = cached["miner"].clone();
                            }
                        }
                    }
                    blocks
                });
                publish(&block_cache, "recentblocks", result);
            }
            // IBD can validate many blocks a second. Keep a sampled list without
            // reading six full blocks on every two-second status refresh.
            thread::sleep(Duration::from_secs(if ibd { 15 } else { 2 }));
        }
    });
    let miner_cache = cache.clone();
    thread::spawn(move || {
        let mut known = BTreeMap::<String, Value>::new();
        loop {
            let state = miner_cache.read().unwrap().clone();
            let chain = state
                .rpc
                .get("getblockchaininfo")
                .cloned()
                .unwrap_or_default();
            let ibd = chain.value["initialblockdownload"] == true;
            let mainnet = chain.value["chain"] == "main";
            let start = Instant::now();
            if chain.updated > 0
                && chain.error.is_none()
                && now().saturating_sub(chain.updated) <= 15
            {
                for block in state
                    .rpc
                    .get("recentblocks")
                    .and_then(|s| s.value.as_array())
                    .into_iter()
                    .flatten()
                {
                    let Some(hash) = block["hash"].as_str() else {
                        continue;
                    };
                    let current = known.get(hash).or_else(|| block.get("miner"));
                    let retry = current.is_none_or(|v| {
                        v["status"] == "pending"
                            || (v["status"] == "unavailable"
                                && now().saturating_sub(v["checked"].as_u64().unwrap_or(0)) >= 30)
                    });
                    let value = if retry {
                        let result = coinbase(&miner_rpc, block, mainnet);
                        let mut value = result.unwrap_or_else(|_| json!({"status":"unavailable"}));
                        value["checked"] = json!(now());
                        known.insert(hash.to_owned(), value.clone());
                        value
                    } else {
                        current
                            .cloned()
                            .unwrap_or_else(|| json!({"status":"pending"}))
                    };
                    let mut shared = miner_cache.write().unwrap();
                    if let Some(rows) = shared
                        .rpc
                        .get_mut("recentblocks")
                        .and_then(|s| s.value.as_array_mut())
                    {
                        if let Some(target) = rows.iter_mut().find(|b| b["hash"] == hash) {
                            target["miner"] = value;
                        }
                    }
                    drop(shared);
                    if start.elapsed() >= Duration::from_secs(if ibd { 2 } else { 5 }) {
                        break;
                    }
                }
            }
            if known.len() > 128 {
                known.retain(|hash, _| {
                    state
                        .rpc
                        .get("recentblocks")
                        .and_then(|s| s.value.as_array())
                        .is_some_and(|rows| rows.iter().any(|b| b["hash"] == hash.as_str()))
                });
            }
            thread::sleep(Duration::from_secs(if ibd { 3 } else { 1 }));
        }
    });
    thread::spawn(move || {
        let mut host = sysinfo::System::new_all();
        let mut disks = sysinfo::Disks::new_with_refreshed_list();
        let mut last_disk_refresh = 0;
        loop {
            host.refresh_memory();
            host.refresh_cpu_usage();
            if now().saturating_sub(last_disk_refresh) >= 10 {
                disks.refresh(true);
                last_disk_refresh = now();
            }
            let core = cache.read().unwrap().clone();
            let value = json!({
                "updated":now(), "hostname":clean(&sysinfo::System::host_name().unwrap_or_default()),
                "uptime":sysinfo::System::uptime(), "used_memory_mib":host.used_memory()/1048576,
                "total_memory_mib":host.total_memory()/1048576, "cpu_percent":format!("{:.1}",host.global_cpu_usage()),
                "disks":disks.iter().map(|d|json!({"mount":clean(&d.mount_point().display().to_string()),"total":d.total_space(),"available":d.available_space()})).collect::<Vec<_>>(),
                "swap_mib":host.used_swap()/1048576, "electrs":probe_electrs(electrs_port,&core), "tor":probe_tor(tor_port), "i2p":crate::probe_i2p(&core)
            });
            let mut shared = cache.write().unwrap();
            shared.host = value;
            shared.collected = now();
            drop(shared);
            thread::sleep(Duration::from_secs(2));
        }
    });
    Ok(())
}

fn headers(rpc: &Rpc, tip: &str, cached: &Value) -> Result<Value> {
    if tip.is_empty() {
        bail!("Core tip unavailable");
    }
    let mut hash = tip.to_owned();
    let mut rows = Vec::new();
    for _ in 0..6 {
        let mut block = match cached
            .as_array()
            .into_iter()
            .flatten()
            .find(|b| b["hash"] == hash)
        {
            Some(block) => block.clone(),
            None => rpc.call("getblockheader", json!([hash, true]))?,
        };
        if block["hash"].as_str() != Some(&hash) {
            bail!("Block header hash mismatch");
        }
        if block["miner"].is_null() {
            block["miner"] = json!({"status":"pending"});
        }
        let previous = block["previousblockhash"].as_str().unwrap_or("").to_owned();
        rows.push(block);
        if previous.is_empty() {
            break;
        }
        hash = previous;
    }
    Ok(json!(rows))
}
fn coinbase(rpc: &Rpc, block: &Value, mainnet: bool) -> Result<Value> {
    if block["height"] == 0 {
        return Ok(json!({"status":"unknown"}));
    }
    let hash = block["hash"].as_str().context("block hash missing")?;
    // One txid list and only its coinbase; never decode the entire block.
    let body = rpc.call("getblock", json!([hash, 1]))?;
    let txid = body["tx"][0].as_str().context("coinbase unavailable")?;
    let tx = rpc.call("getrawtransaction", json!([txid, true, hash]))?;
    Ok(miner::identify(&tx, mainnet))
}
