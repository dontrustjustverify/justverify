pub mod backup_ui;
pub mod client_ui;
pub mod collector;
pub mod connection_ui;
pub mod dashboard;
pub mod download;
pub mod miner;
pub mod policy;
pub mod policy_service;
pub mod storage;
pub mod storage_ui;
pub mod tui;
pub mod version_service;
pub mod version_ui;
pub mod versions;
use anyhow::{Context, Result, bail};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::{
    collections::BTreeMap,
    fs,
    path::Path,
    time::{Duration, SystemTime, UNIX_EPOCH},
};

pub fn now() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs()
}

/// Remove complete CSI/OSC/DCS sequences, all control characters and bidi controls.
pub fn clean(input: &str) -> String {
    let mut out = String::new();
    let mut chars = input.chars().peekable();
    while let Some(c) = chars.next() {
        if c == '\x1b' {
            match chars.next() {
                Some('[') => {
                    for x in chars.by_ref() {
                        if ('@'..='~').contains(&x) {
                            break;
                        }
                    }
                }
                Some(']' | 'P' | '^' | '_') => {
                    while let Some(x) = chars.next() {
                        if x == '\x07' {
                            break;
                        }
                        if x == '\x1b' && chars.peek() == Some(&'\\') {
                            chars.next();
                            break;
                        }
                    }
                }
                _ => {}
            }
        } else if !c.is_control() && !matches!(c, '\u{202a}'..='\u{202e}' | '\u{2066}'..='\u{2069}')
        {
            out.push(c);
        }
    }
    out
}

/// sat/vB -> BTC/kvB using integer arithmetic; Core has 8 decimal BTC precision.
pub fn fee_to_core(input: &str) -> Result<String> {
    if input.is_empty() || !input.chars().all(|c| c.is_ascii_digit() || c == '.') {
        bail!("nonnegative decimal sat/vB required");
    }
    let parts: Vec<_> = input.split('.').collect();
    if parts.len() > 2 || parts[0].is_empty() {
        bail!("invalid fee");
    }
    let frac = parts.get(1).copied().unwrap_or("");
    if frac.len() > 3 {
        bail!("precision exceeds 0.001 sat/vB");
    }
    let value = parts[0]
        .parse::<u64>()?
        .checked_mul(1000)
        .and_then(|n| n.checked_add(format!("{frac:0<3}").parse::<u64>().ok()?))
        .context("fee overflow")?;
    Ok(format!(
        "{}.{:08}",
        value / 100_000_000,
        value % 100_000_000
    ))
}

#[derive(Clone, Default, Debug, Serialize, Deserialize)]
pub struct Sample {
    pub value: Value,
    pub updated: u64,
    pub error: Option<String>,
}
#[derive(Clone, Default, Debug, Serialize, Deserialize)]
pub struct Snapshot {
    pub collected: u64,
    pub rpc: BTreeMap<String, Sample>,
    pub host: Value,
}

pub struct Rpc {
    client: reqwest::blocking::Client,
    url: String,
    cookie: std::path::PathBuf,
}
impl Rpc {
    pub fn new(port: u16, cookie: &Path) -> Result<Self> {
        Self::with_timeout(port, cookie, Duration::from_secs(3))
    }
    pub fn with_timeout(port: u16, cookie: &Path, timeout: Duration) -> Result<Self> {
        Ok(Self {
            client: reqwest::blocking::Client::builder()
                .timeout(timeout)
                .no_proxy()
                .build()?,
            url: format!("http://127.0.0.1:{port}"),
            cookie: cookie.into(),
        })
    }
    pub fn call(&self, method: &str, params: Value) -> Result<Value> {
        let secret = fs::read_to_string(&self.cookie).context("RPC cookie unavailable")?;
        let (user, pass) = secret.trim().split_once(':').context("invalid cookie")?;
        let response = self
            .client
            .post(&self.url)
            .basic_auth(user, Some(pass))
            .json(&json!({"jsonrpc":"1.0","id":"justverify","method":method,"params":params}))
            .send()
            .map_err(rpc_transport_error)?;
        // Core legacy RPC uses HTTP 500 for valid JSON-RPC errors.
        let body: Value = response.json().map_err(rpc_transport_error)?;
        if !body["error"].is_null() {
            bail!("RPC error code {}", body["error"]["code"]);
        }
        Ok(body["result"].clone())
    }
}

fn rpc_transport_error(error: reqwest::Error) -> anyhow::Error {
    // Do not expose request URLs, authentication headers or response bodies.
    anyhow::anyhow!(if error.is_timeout() {
        "RPC request timed out"
    } else if error.is_connect() {
        "RPC connection failed"
    } else {
        "RPC response failed"
    })
}

pub fn field(s: &Snapshot, method: &str, key: &str) -> String {
    let Some(sample) = s.rpc.get(method) else {
        return "N/A".into();
    };
    let value = &sample.value[key];
    let text = if value.is_null() {
        "N/A".into()
    } else if let Some(v) = value.as_str() {
        clean(v)
    } else {
        clean(&value.to_string())
    };
    if sample.error.is_some() || sample.updated == 0 || now().saturating_sub(sample.updated) > 15 {
        format!("{text} [STALE @{}]", sample.updated)
    } else {
        text
    }
}

pub fn main_lines(s: &Snapshot) -> Vec<String> {
    let f = |m, k| field(s, m, k);
    vec![
        format!(
            "JustVerify | {} | {} | {}",
            s.host["hostname"].as_str().unwrap_or("N/A"),
            f("getblockchaininfo", "chain"),
            f("getnetworkinfo", "subversion")
        ),
        format!(
            "HOST uptime {}s | RAM {} / {} MiB | CPU {}%",
            s.host["uptime"],
            s.host["used_memory_mib"],
            s.host["total_memory_mib"],
            s.host["cpu_percent"]
        ),
        format!(
            "CHAIN blocks {} / headers {} | IBD {}",
            f("getblockchaininfo", "blocks"),
            f("getblockchaininfo", "headers"),
            f("getblockchaininfo", "initialblockdownload")
        ),
        format!(
            "verification {} | disk {} bytes | prune {}",
            f("getblockchaininfo", "verificationprogress"),
            f("getblockchaininfo", "size_on_disk"),
            f("getblockchaininfo", "pruned")
        ),
        format!(
            "MEMPOOL tx {} | vsize {} vB",
            f("getmempoolinfo", "size"),
            f("getmempoolinfo", "bytes")
        ),
        format!(
            "RAM {} / {} bytes | total fee {} BTC",
            f("getmempoolinfo", "usage"),
            f("getmempoolinfo", "maxmempool"),
            f("getmempoolinfo", "total_fee")
        ),
        format!(
            "mempool floor {} BTC/kvB | relay {} BTC/kvB",
            f("getmempoolinfo", "mempoolminfee"),
            f("getmempoolinfo", "minrelaytxfee")
        ),
        format!(
            "FEE target 6 blocks {} BTC/kvB (N/A = no estimate)",
            f("estimatesmartfee", "feerate")
        ),
        format!(
            "NET in {} / out {} | recv {} / sent {} bytes",
            f("getnetworkinfo", "connections_in"),
            f("getnetworkinfo", "connections_out"),
            f("getnettotals", "totalbytesrecv"),
            f("getnettotals", "totalbytessent")
        ),
        format!(
            "Core {} | last collection {}",
            if s.rpc
                .get("getblockchaininfo")
                .is_some_and(|x| x.error.is_none() && x.updated > 0 && now().saturating_sub(x.updated) <= 15)
            {
                "ONLINE"
            } else {
                "UNAVAILABLE / STALE"
            },
            s.rpc.get("getblockchaininfo").map_or(0, |x| x.updated)
        ),
        format!(
            "Electrs {} | height {}",
            s.host["electrs"]["state"].as_str().unwrap_or("N/A"),
            s.host["electrs"]["height"]
        ),
        format!("Tor {}", s.host["tor"]["state"].as_str().unwrap_or("N/A")),
        format!(
            "FEE estimate {} sat/vB | floor {} sat/vB | relay {} sat/vB",
            display_fee(s, "estimatesmartfee", "feerate"),
            display_fee(s, "getmempoolinfo", "mempoolminfee"),
            display_fee(s, "getmempoolinfo", "minrelaytxfee")
        ),
        "비트코인코어: V 버전 | M 정책 | P 피어 | C 지갑 연결 | S 기기 설정 | Esc 현황 | Ctrl-C 종료"
            .into(),
    ]
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn terminal_injection() {
        assert_eq!(
            clean("peer\x1b]52;c;c2VjcmV0\x07\x1b[31mred\x1b[0m\n\u{202e}"),
            "peerred"
        );
    }
    #[test]
    fn fee_units() {
        assert_eq!(fee_to_core("1").unwrap(), "0.00001000");
        assert_eq!(fee_to_core("0.001").unwrap(), "0.00000001");
        assert!(fee_to_core("0.0001").is_err());
        assert!(fee_to_core("1\nserver=1").is_err());
        assert!(fee_to_core("18446744073709551615").is_err());
    }
    #[test]
    fn stale_does_not_disappear() {
        let mut s = Snapshot::default();
        s.rpc.insert(
            "x".into(),
            Sample {
                value: json!({"a":42}),
                updated: 7,
                error: Some("timeout".into()),
            },
        );
        assert_eq!(field(&s, "x", "a"), "42 [STALE @7]");
        assert_eq!(field(&s, "missing", "a"), "N/A");
    }
    #[test]
    fn host_heartbeat_cannot_refresh_old_core_or_fee_samples() {
        let mut s = Snapshot {
            collected: now(),
            ..Snapshot::default()
        };
        s.rpc.insert(
            "getblockchaininfo".into(),
            Sample {
                value: json!({"blocks":42}),
                updated: now() - 20,
                error: None,
            },
        );
        s.rpc.insert(
            "estimatesmartfee".into(),
            Sample {
                value: json!({"feerate":0.00001}),
                updated: now() - 20,
                error: None,
            },
        );
        assert!(field(&s, "getblockchaininfo", "blocks").contains("STALE"));
        assert!(display_fee(&s, "estimatesmartfee", "feerate").contains("STALE"));
        assert!(
            main_lines(&s)
                .iter()
                .any(|line| line.starts_with("Core UNAVAILABLE / STALE"))
        );
    }
}

pub fn electrs_tip(port: u16) -> Result<(u64, String)> {
    use std::io::{Read, Write};

    let mut stream = std::net::TcpStream::connect_timeout(
        &format!("127.0.0.1:{port}").parse()?,
        Duration::from_millis(300),
    )?;
    stream.set_read_timeout(Some(Duration::from_millis(500)))?;
    stream.set_write_timeout(Some(Duration::from_millis(500)))?;
    stream.write_all(b"{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"blockchain.headers.subscribe\",\"params\":[]}\n")?;
    let mut bytes = Vec::new();
    for byte in stream.take(4096).bytes() {
        let b = byte?;
        if b == b'\n' {
            break;
        }
        bytes.push(b);
    }
    let response: Value = serde_json::from_slice(&bytes)?;
    let height = response["result"]["height"]
        .as_u64()
        .context("no electrs height")?;
    let header = response["result"]["hex"]
        .as_str()
        .context("no electrs header")?;
    Ok((height, header_hash(header)?))
}

pub fn header_hash(header: &str) -> Result<String> {
    use sha2::{Digest, Sha256};
    if header.len() != 160 || !header.is_ascii() {
        bail!("invalid block header length");
    }
    let bytes: Vec<u8> = (0..160)
        .step_by(2)
        .map(|i| u8::from_str_radix(&header[i..i + 2], 16))
        .collect::<std::result::Result<_, _>>()?;
    Ok(Sha256::digest(Sha256::digest(bytes))
        .iter()
        .rev()
        .map(|byte| format!("{byte:02x}"))
        .collect())
}

#[test]
fn block_header_hash_uses_bitcoin_byte_order() {
    let genesis = "0100000000000000000000000000000000000000000000000000000000000000000000003ba3edfd7a7b12b27ac72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4a29ab5f49ffff001d1dac2b7c";
    assert_eq!(
        header_hash(genesis).unwrap(),
        "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f"
    );
    assert!(header_hash(&genesis[..158]).is_err());
    assert!(header_hash(&"g".repeat(160)).is_err());
}

pub fn electrs_height(port: u16) -> Result<u64> {
    Ok(electrs_tip(port)?.0)
}
pub fn probe_electrs(port: u16, core: &Snapshot) -> Value {
    let result = (|| -> Result<Value> {
        let (height, tip) = electrs_tip(port)?;
        let ready = core.rpc.get("getblockchaininfo").is_some_and(|s| {
            s.error.is_none()
                && s.updated > 0
                && now().saturating_sub(s.updated) <= 15
                && s.value["blocks"].as_u64() == Some(height)
                && s.value["bestblockhash"].as_str() == Some(tip.as_str())
                && s.value["initialblockdownload"] == false
        });
        Ok(
            json!({"state":if ready {"READY"} else {"INDEXING / CORE NOT READY"},"height":height,"tip":tip,"port":port}),
        )
    })();
    result.unwrap_or_else(|_| json!({"state":"UNAVAILABLE","height":null,"port":port}))
}

pub fn probe_tor(port: u16) -> Value {
    use std::io::{Read, Write};
    let result = (|| -> Result<()> {
        let mut stream = std::net::TcpStream::connect_timeout(
            &format!("127.0.0.1:{port}").parse()?,
            Duration::from_millis(300),
        )?;
        stream.set_read_timeout(Some(Duration::from_millis(500)))?;
        stream.set_write_timeout(Some(Duration::from_millis(500)))?;
        stream.write_all(&[5, 1, 0])?;
        let mut response = [0; 2];
        stream.read_exact(&mut response)?;
        if response != [5, 0] {
            bail!("SOCKS negotiation failed");
        }
        Ok(())
    })();
    json!({"state":if result.is_ok(){"SOCKS LISTENING; circuit unverified"}else{"UNAVAILABLE"},"port":port})
}

// Display rounding only; all submitted configuration fees use integer fee_to_core.
fn display_fee(s: &Snapshot, m: &str, k: &str) -> String {
    s.rpc
        .get(m)
        .map(|v| {
            let text = v.value[k]
                .as_f64()
                .map(|f| format!("{:.3}", f * 100000.0))
                .unwrap_or("N/A".into());
            if v.error.is_some() || v.updated == 0 || now().saturating_sub(v.updated) > 15 {
                format!("{text} STALE")
            } else {
                text
            }
        })
        .unwrap_or("N/A".into())
}
