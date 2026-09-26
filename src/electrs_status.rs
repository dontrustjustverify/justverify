//! Independent index progress and Electrum readiness observations.
use crate::{Sample, Snapshot, header_hash, now};
use anyhow::{Context, Result, bail};
use serde_json::{Value, json};
use std::{
    io::{Read, Write},
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
    pub runtime: Sample,
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
        .timeout(Duration::from_secs(3))
        .build()?;
    let metrics = status.clone();
    thread::spawn(move || {
        loop {
            let result = read_metrics(&client, metrics_port);
            let mut status = metrics.write().unwrap();
            update(&mut status.progress, result);
            status.runtime = runtime_status(port).unwrap_or_default();
            drop(status);
            thread::sleep(Duration::from_secs(2));
        }
    });
    let rpc = status.clone();
    thread::spawn(move || {
        let mut connection = ElectrumClient::default();
        loop {
            let result = connection.poll(port);
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

// Only accept the local supervisor's live, bounded observation for this endpoint.
fn runtime_status(port: u16) -> Option<Sample> {
    let mut body = String::new();
    std::fs::File::open("/run/justverify-electrs/status.json")
        .ok()?
        .take(4097)
        .read_to_string(&mut body)
        .ok()?;
    if body.len() > 4096 {
        return None;
    }
    let value: Value = serde_json::from_str(&body).ok()?;
    let updated = value["updated"].as_u64()?;
    let pid = value["pid"].as_u64()?;
    if value["port"].as_u64()? != u64::from(port)
        || !value["running"].is_boolean()
        || pid == 0
        || value["running"] == true && !std::path::Path::new(&format!("/proc/{pid}")).exists()
    {
        return None;
    }
    Some(Sample {
        value,
        updated,
        error: None,
    })
}

fn io_error(error: std::io::Error) -> anyhow::Error {
    use std::io::ErrorKind::*;
    anyhow::anyhow!(match error.kind() {
        TimedOut | WouldBlock => "Electrum response delayed",
        _ => "Electrum connection unavailable",
    })
}

/// A slow index keeps one connection and one outstanding header/ping pair.
/// Soft read deadlines update the UI without abandoning queued server requests.
pub struct ElectrumClient {
    stream: Option<TcpStream>,
    buffer: Vec<u8>,
    header: Option<(u64, String)>,
    ready: Option<bool>,
    pending: bool,
    id: u64,
    received: usize,
    retry_at: Instant,
    backoff: u64,
}
impl Default for ElectrumClient {
    fn default() -> Self {
        Self {
            stream: None,
            buffer: Vec::new(),
            header: None,
            ready: None,
            pending: false,
            id: 0,
            received: 0,
            retry_at: Instant::now(),
            backoff: 10,
        }
    }
}
impl ElectrumClient {
    pub fn poll(&mut self, port: u16) -> Result<Value> {
        if self.stream.is_none() && Instant::now() < self.retry_at {
            bail!("Electrum connection unavailable");
        }
        let result = self.receive(port);
        if let Err(ref error) = result {
            if error.to_string() != "Electrum response delayed" {
                self.stream = None;
                self.buffer.clear();
                self.pending = false;
                self.retry_at = Instant::now() + Duration::from_secs(self.backoff);
                self.backoff = (self.backoff * 2).min(60);
            }
        }
        result
    }
    fn receive(&mut self, port: u16) -> Result<Value> {
        if self.stream.is_none() {
            if Instant::now() < self.retry_at {
                bail!("Electrum connection unavailable");
            }
            let stream = TcpStream::connect_timeout(
                &format!("127.0.0.1:{port}").parse()?,
                Duration::from_millis(300),
            )
            .map_err(|_| anyhow::anyhow!("Electrum connection unavailable"))?;
            stream.set_write_timeout(Some(Duration::from_millis(500)))?;
            self.stream = Some(stream);
        }
        if !self.pending {
            self.id = self.id.checked_add(2).context("Electrum request limit")?;
            self.header = None;
            self.ready = None;
            self.received = 0;
            let request = format!(
                "{}\n{}\n",
                json!({"jsonrpc":"2.0","id":self.id,"method":"blockchain.headers.subscribe","params":[]}),
                json!({"jsonrpc":"2.0","id":self.id+1,"method":"server.ping","params":[]})
            );
            // A partial write must never be retried on this stream.
            self.stream
                .as_mut()
                .unwrap()
                .write_all(request.as_bytes())
                .map_err(|_| anyhow::anyhow!("Electrum connection unavailable"))?;
            self.pending = true;
        }
        let deadline = Instant::now() + Duration::from_secs(2);
        loop {
            while let Some(end) = self.buffer.iter().position(|b| *b == b'\n') {
                let line: Vec<u8> = self.buffer.drain(..=end).collect();
                self.received += line.len();
                if self.received > 16384 {
                    bail!("Invalid Electrum response");
                }
                let value: Value =
                    serde_json::from_slice(&line).context("Invalid Electrum response")?;
                match value["id"].as_u64() {
                    Some(id) if id == self.id => {
                        if self.header.is_some() || !value["error"].is_null() {
                            bail!("Invalid Electrum header response");
                        }
                        let height = value["result"]["height"]
                            .as_u64()
                            .context("Invalid Electrum height")?;
                        let tip = header_hash(
                            value["result"]["hex"]
                                .as_str()
                                .context("Invalid Electrum header")?,
                        )?;
                        self.header = Some((height, tip));
                    }
                    Some(id) if id == self.id + 1 => {
                        if self.ready.is_some() {
                            bail!("Invalid Electrum readiness response");
                        }
                        self.ready = Some(
                            if value["error"].is_null() && value.get("result") == Some(&Value::Null)
                            {
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
                    None if value["method"] == "blockchain.headers.subscribe" => (),
                    _ => bail!("Invalid Electrum response id"),
                }
                if let (Some((height, tip)), Some(ready)) = (&self.header, self.ready) {
                    self.pending = false;
                    self.backoff = 10;
                    return Ok(json!({"height":height,"tip":tip,"index_ready":ready}));
                }
            }
            let left = deadline
                .checked_duration_since(Instant::now())
                .context("Electrum response delayed")?;
            let stream = self.stream.as_mut().unwrap();
            stream.set_read_timeout(Some(left.max(Duration::from_millis(1))))?;
            let mut bytes = [0u8; 4096];
            let count = stream.read(&mut bytes).map_err(io_error)?;
            if count == 0 {
                bail!("Electrum connection unavailable");
            }
            if self.received + self.buffer.len() + count > 16384 {
                bail!("Invalid Electrum response");
            }
            self.buffer.extend_from_slice(&bytes[..count]);
        }
    }
}

// One-shot checks are reserved for explicit preflight/administrative operations.
pub fn read_electrum(port: u16) -> Result<Value> {
    ElectrumClient::default().poll(port)
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
        let matches_core = core_fresh
            && rpc_fresh
            && chain_value["initialblockdownload"] == false
            && self.electrum.value["height"].as_u64().is_some()
            && self.electrum.value["height"] == chain_value["blocks"]
            && self.electrum.value["tip"] == chain_value["bestblockhash"];
        // A functional Electrum reply matching Core is stronger evidence than
        // a metrics scrape taken just before the last block was indexed.
        let confirmed = matches_core && self.electrum.value["index_ready"] == true;
        let (source, sample) = if confirmed {
            ("electrum", &self.electrum)
        } else if metrics_fresh {
            ("metrics", &self.progress)
        } else if rpc_fresh {
            ("electrum", &self.electrum)
        } else if self.progress.updated >= self.electrum.updated {
            ("metrics", &self.progress)
        } else {
            ("electrum", &self.electrum)
        };
        let runtime_fresh = fresh(&self.runtime, at);
        let compacted = runtime_fresh && self.runtime.value["compacted"] == true;
        let listener_failed = runtime_fresh && self.runtime.value["listener_error"] == true;
        let state = if runtime_fresh && self.runtime.value["running"] == false {
            "UNAVAILABLE"
        } else if listener_failed {
            if self.runtime.value["resource_error"] == true {
                "RESOURCE_ERROR"
            } else {
                "CONNECTION_ERROR"
            }
        } else if metrics_fresh && self.progress.value["db_error"] == true {
            "INDEX_ERROR"
        } else if confirmed {
            "READY"
        } else if matches_core && self.electrum.value["index_ready"] == false {
            if compacted {
                "CATCHING_UP"
            } else {
                "FINALIZING"
            }
        } else if core_fresh && chain_value["initialblockdownload"] == true {
            "CORE_SYNCING"
        } else if runtime_fresh && self.runtime.value["phase"] == "compacting" {
            "FINALIZING"
        } else if self.electrum.error.as_deref() == Some("Electrum connection unavailable") {
            "UNAVAILABLE"
        } else if rpc_fresh && self.electrum.value["index_ready"] == false
            || metrics_fresh
                && core_fresh
                && self.progress.value["height"]
                    .as_u64()
                    .zip(chain_value["blocks"].as_u64())
                    .is_some_and(|(h, c)| h < c)
        {
            if compacted { "CATCHING_UP" } else { "INDEXING" }
        } else if metrics_fresh || rpc_fresh {
            if compacted {
                "CATCHING_UP"
            } else {
                "VERIFYING"
            }
        } else if self.electrum.error.as_deref() == Some("Electrum connection unavailable") {
            "UNAVAILABLE"
        } else if sample.updated > 0 {
            "STALE"
        } else {
            "STARTING"
        };
        let db = &self.runtime.value["compaction_progress"];
        let db_points = if runtime_fresh
            && self.runtime.value["phase"] == "compacting"
            && db["basis"] == "estimated_records"
            && db["complete"] == false
        {
            db["percent_basis_points"].as_u64().filter(|p| *p < 10000)
        } else {
            None
        };
        json!({"state":state,"height":sample.value["height"],"height_source":source,
            "target_height":chain_value["blocks"].as_u64().map(|blocks| if chain_value["initialblockdownload"] == true { blocks.max(chain_value["headers"].as_u64().unwrap_or(blocks)) } else { blocks }),
            "core_headers":chain_value["headers"],
            "core_ibd":chain_value["initialblockdownload"],"target_updated":chain.map_or(0,|s|s.updated),"target_stale":!core_fresh,
            "height_updated":sample.updated,"height_stale":!fresh(sample,at),
            "served_height":self.electrum.value["height"],"tip":self.electrum.value["tip"],
            "rpc_updated":self.electrum.updated,"rpc_error":self.electrum.error,
            "metrics_updated":self.progress.updated,"metrics_error":self.progress.error,
            "wallet_ready":state=="READY","port":port,
            "compaction":if runtime_fresh { self.runtime.value["compaction"].clone() } else { Value::Null },
            "compaction_percent_basis_points":db_points,"compaction_complete":compacted,
            "recovery_pending":runtime_fresh && self.runtime.value["recovery_pending"] == true})
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

pub fn state_text(value: &Value) -> &str {
    match value["state"].as_str().unwrap_or("N/A") {
        "INDEXING" => "블록 인덱싱 중",
        "FINALIZING" => "DB 정리 중",
        "CATCHING_UP" => "최신 블록 반영 중",
        "READY" => "동기화 완료",
        state => state,
    }
}

pub fn progress_text(value: &Value) -> String {
    if value["state"] == "FINALIZING" {
        return match value["compaction_percent_basis_points"]
            .as_u64()
            .filter(|p| *p < 10000)
        {
            Some(points) => format!("~{}.{:02}%", points / 100, points % 100),
            None => "N/A".into(),
        };
    }
    match (value["height"].as_u64(), value["target_height"].as_u64()) {
        (Some(height), Some(total)) if total > 0 => {
            let points = height
                .saturating_mul(10000)
                .checked_div(total)
                .unwrap()
                .min(if value["wallet_ready"] == true {
                    10000
                } else {
                    9999
                });
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
