//! Independent index progress and Electrum readiness observations.
use crate::{Sample, Snapshot, header_hash, now};
use anyhow::{Context, Result, bail};
use serde_json::{Value, json};
use std::{
    io::{BufRead, BufReader, Read, Write},
    net::TcpStream,
    sync::{Arc, RwLock},
    thread,
    time::{Duration, Instant},
};

const FRESH_SECONDS: u64 = 15;
#[derive(Default)]
pub struct Status {
    pub progress: Sample,
    pub electrum: Sample,
}
pub type Monitor = Arc<RwLock<Status>>;

fn update(sample: &mut Sample, result: Result<Value>) {
    match result {
        Ok(value) => {
            sample.value = value;
            sample.updated = now();
            sample.error = None;
        }
        Err(e) => sample.error = Some(e.to_string()),
    }
}

pub fn start(port: u16, metrics_port: u16) -> Result<Monitor> {
    let status = Arc::new(RwLock::new(Status::default()));
    let client = reqwest::blocking::Client::builder()
        .no_proxy()
        .redirect(reqwest::redirect::Policy::none())
        .timeout(Duration::from_secs(1))
        .build()?;
    let metrics = status.clone();
    thread::spawn(move || {
        loop {
            let result = read_metrics(&client, metrics_port);
            update(&mut metrics.write().unwrap().progress, result);
            thread::sleep(Duration::from_secs(2));
        }
    });
    let rpc = status.clone();
    thread::spawn(move || {
        loop {
            let result = read_electrum(port);
            update(&mut rpc.write().unwrap().electrum, result);
            thread::sleep(Duration::from_secs(5));
        }
    });
    Ok(status)
}

pub fn parse_metrics(text: &str) -> Result<Value> {
    let mut height = None;
    let mut db_error = false;
    for line in text.lines() {
        if let Some(raw) = line.strip_prefix("electrs_index_height{type=\"tip\"} ") {
            if height.is_some() {
                bail!("Invalid index metrics");
            }
            // This gauge is an integer even though Prometheus transports numbers as text.
            let value: f64 = raw.trim().parse().context("Invalid index metrics")?;
            if !value.is_finite() || value < 0.0 || value.fract() != 0.0 || value > u32::MAX as f64
            {
                bail!("Invalid index metrics");
            }
            height = Some(value as u64);
        }
        if line.starts_with("electrs_index_db_properties{name=\"rocksdb.background-errors:") {
            let value: f64 = line
                .rsplit_once(' ')
                .context("Invalid index metrics")?
                .1
                .parse()
                .context("Invalid index metrics")?;
            if !value.is_finite() || value < 0.0 {
                bail!("Invalid index metrics");
            }
            db_error |= value > 0.0;
        }
    }
    Ok(json!({"height":height.context("Index metrics not ready")?,"db_error":db_error}))
}

fn read_metrics(client: &reqwest::blocking::Client, port: u16) -> Result<Value> {
    let response = client
        .get(format!("http://127.0.0.1:{port}/metrics"))
        .send()
        .map_err(|_| anyhow::anyhow!("Index metrics unavailable"))?;
    if !response.status().is_success() {
        bail!("Index metrics unavailable");
    }
    let mut body = String::new();
    response
        .take(262145)
        .read_to_string(&mut body)
        .map_err(|_| anyhow::anyhow!("Index metrics unavailable"))?;
    if body.len() > 262144 {
        bail!("Invalid index metrics");
    }
    parse_metrics(&body)
}

fn io_error(error: std::io::Error) -> anyhow::Error {
    use std::io::ErrorKind::*;
    anyhow::anyhow!(match error.kind() {
        TimedOut | WouldBlock => "Electrum response delayed",
        _ => "Electrum connection unavailable",
    })
}

pub fn read_electrum(port: u16) -> Result<Value> {
    let deadline = Instant::now() + Duration::from_secs(2);
    let mut stream = TcpStream::connect_timeout(
        &format!("127.0.0.1:{port}").parse()?,
        Duration::from_millis(300),
    )
    .map_err(io_error)?;
    stream.set_write_timeout(Some(Duration::from_millis(500)))?;
    stream.write_all(b"{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"blockchain.headers.subscribe\",\"params\":[]}\n{\"jsonrpc\":\"2.0\",\"id\":2,\"method\":\"server.ping\",\"params\":[]}\n").map_err(io_error)?;
    let mut reader = BufReader::new(stream);
    let mut header = None;
    let mut ready = None;
    let mut size = 0;
    while header.is_none() || ready.is_none() {
        let left = deadline
            .checked_duration_since(Instant::now())
            .context("Electrum response delayed")?;
        reader
            .get_ref()
            .set_read_timeout(Some(left.max(Duration::from_millis(1))))?;
        let mut line = String::new();
        // Limit total input and total elapsed time even when a peer sends partial lines.
        let mut data = Vec::new();
        loop {
            let left = deadline
                .checked_duration_since(Instant::now())
                .context("Electrum response delayed")?;
            reader
                .get_ref()
                .set_read_timeout(Some(left.max(Duration::from_millis(1))))?;
            let buffer = reader.fill_buf().map_err(io_error)?;
            if buffer.is_empty() {
                bail!("Electrum connection unavailable");
            }
            let n = buffer
                .iter()
                .position(|b| *b == b'\n')
                .map_or(buffer.len(), |i| i + 1);
            if size + data.len() + n > 16384 {
                bail!("Invalid Electrum response");
            }
            data.extend_from_slice(&buffer[..n]);
            reader.consume(n);
            if data.last() == Some(&b'\n') {
                break;
            }
        }
        let bytes = data.len();
        line.push_str(std::str::from_utf8(&data).context("Invalid Electrum response")?);
        size += bytes;
        if bytes == 0 || size > 16384 || !line.ends_with('\n') || Instant::now() > deadline {
            bail!("Invalid or delayed Electrum response");
        }
        let value: Value = serde_json::from_str(&line).context("Invalid Electrum response")?;
        match value["id"].as_u64() {
            Some(1) => {
                if header.is_some() || !value["error"].is_null() {
                    bail!("Invalid Electrum header response");
                }
                let result = &value["result"];
                let height = result["height"]
                    .as_u64()
                    .context("Invalid Electrum height")?;
                let tip = header_hash(result["hex"].as_str().context("Invalid Electrum header")?)?;
                header = Some((height, tip));
            }
            Some(2) => {
                if ready.is_some() {
                    bail!("Invalid Electrum readiness response");
                }
                ready = Some(
                    if value["error"].is_null() && value.get("result") == Some(&Value::Null) {
                        true
                    } else if value["error"]["code"] == -32603
                        && value["error"]["message"] == "unavailable index"
                    {
                        false
                    } else {
                        bail!("Electrum readiness failed");
                    },
                );
            }
            // Header subscription notifications may arrive between the two replies.
            None if value["method"] == "blockchain.headers.subscribe" => (),
            _ => bail!("Invalid Electrum response id"),
        }
    }
    let (height, tip) = header.unwrap();
    Ok(json!({"height":height,"tip":tip,"index_ready":ready.unwrap()}))
}

fn fresh(sample: &Sample, at: u64) -> bool {
    sample.updated > 0
        && sample.updated <= at
        && at - sample.updated <= FRESH_SECONDS
        && sample.error.is_none()
}

impl Status {
    pub fn view(&self, core: &Snapshot, port: u16, at: u64) -> Value {
        let metrics_fresh = fresh(&self.progress, at);
        let rpc_fresh = fresh(&self.electrum, at);
        let chain = core.rpc.get("getblockchaininfo");
        let core_fresh = chain.is_some_and(|s| fresh(s, at));
        let chain_value = chain.map(|s| &s.value).unwrap_or(&Value::Null);
        let (source, sample) = if metrics_fresh {
            ("metrics", &self.progress)
        } else if rpc_fresh {
            ("electrum", &self.electrum)
        } else if self.progress.updated >= self.electrum.updated {
            ("metrics", &self.progress)
        } else {
            ("electrum", &self.electrum)
        };
        let matches_core = core_fresh
            && rpc_fresh
            && chain_value["initialblockdownload"] == false
            && self.electrum.value["height"].as_u64().is_some()
            && self.electrum.value["height"] == chain_value["blocks"]
            && self.electrum.value["tip"] == chain_value["bestblockhash"];
        let state = if metrics_fresh && self.progress.value["db_error"] == true {
            "INDEX_ERROR"
        } else if matches_core
            && self.electrum.value["index_ready"] == true
            && (!metrics_fresh || self.progress.value["height"] == self.electrum.value["height"])
        {
            "READY"
        } else if rpc_fresh && self.electrum.value["index_ready"] == false
            || metrics_fresh
                && core_fresh
                && self.progress.value["height"]
                    .as_u64()
                    .zip(chain_value["blocks"].as_u64())
                    .is_some_and(|(h, c)| h < c)
        {
            "INDEXING"
        } else if core_fresh && chain_value["initialblockdownload"] == true {
            "CORE_SYNCING"
        } else if metrics_fresh || rpc_fresh {
            "VERIFYING"
        } else if self.electrum.error.as_deref() == Some("Electrum connection unavailable") {
            "UNAVAILABLE"
        } else if sample.updated > 0 {
            "STALE"
        } else {
            "STARTING"
        };
        json!({"state":state,"height":sample.value["height"],"height_source":source,
            "target_height":chain_value["blocks"],"target_updated":chain.map_or(0,|s|s.updated),"target_stale":!core_fresh,
            "height_updated":sample.updated,"height_stale":!fresh(sample,at),
            "served_height":self.electrum.value["height"],"tip":self.electrum.value["tip"],
            "rpc_updated":self.electrum.updated,"rpc_error":self.electrum.error,
            "metrics_updated":self.progress.updated,"metrics_error":self.progress.error,
            "wallet_ready":state=="READY","port":port})
    }
}

pub fn height_text(value: &Value) -> String {
    match value["height"].as_u64() {
        None => "N/A".into(),
        Some(height) if value["height_stale"] == true => {
            format!("{height} [STALE @{}]", value["height_updated"])
        }
        Some(height) => height.to_string(),
    }
}

pub fn progress_text(value: &Value) -> String {
    match (value["height"].as_u64(), value["target_height"].as_u64()) {
        (Some(height), Some(total)) => {
            let points = if total == 0 {
                10000
            } else {
                height
                    .saturating_mul(10000)
                    .checked_div(total)
                    .unwrap()
                    .min(10000)
            };
            let text = format!("{}.{:02}% ({height}/{total})", points / 100, points % 100);
            if value["height_stale"] == true || value["target_stale"] == true {
                format!("{text} [STALE @{}]", value["height_updated"])
            } else {
                text
            }
        }
        _ => height_text(value),
    }
}
