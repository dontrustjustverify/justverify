//! Version-aware policy plans and crash-visible atomic configuration transactions.
use anyhow::{Context, Result, bail};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::{
    collections::BTreeMap,
    fs::{self, OpenOptions},
    io::Write,
    os::unix::fs::{OpenOptionsExt, PermissionsExt},
    path::{Path, PathBuf},
};

pub type Values = BTreeMap<String, String>;
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Plan {
    pub version: String,
    pub network: String,
    pub revision: String,
    pub requested: Values,
    pub core_values: Values,
    pub changes: Vec<String>,
    pub warning: Vec<String>,
}
#[derive(Debug, Serialize, Deserialize)]
pub struct Journal {
    pub binary_digest: String,
    pub phase: String,
    pub version: String,
    pub network: String,
    pub before: String,
    pub after: String,
    pub error: Option<String>,
}
pub struct Policy {
    version: String,
    network: String,
    entries: BTreeMap<String, Value>,
}
fn digest(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}
impl Policy {
    pub fn load(catalog: &Path, version: &str, network: &str) -> Result<Self> {
        let releases: Value = serde_json::from_slice(&fs::read(catalog.join("releases.json"))?)?;
        let row = releases["releases"]
            .as_array()
            .context("invalid releases")?
            .iter()
            .find(|r| r["version"] == version)
            .context("unknown Core version")?;
        if row["availability"] != "OFFICIAL_BINARY_VERIFIED" {
            bail!("Core release is unavailable or unverified");
        }
        if !row["networks"]
            .as_array()
            .context("missing networks")?
            .iter()
            .any(|n| n == network)
        {
            bail!("network unsupported by selected version");
        }
        let records: Vec<Value> =
            serde_json::from_slice(&fs::read(catalog.join(format!("policy-{version}.json")))?)?;
        let mut entries: BTreeMap<String, Value> = records
            .into_iter()
            .map(|v| (v["key"].as_str().unwrap_or("").to_owned(), v))
            .collect();
        let resources = catalog.join(format!("resources-{version}.json"));
        if resources.exists() {
            let rows: Vec<Value> = serde_json::from_slice(&fs::read(resources)?)?;
            for row in rows {
                let key = row["key"]
                    .as_str()
                    .context("resource key missing")?
                    .to_owned();
                if row["core_version"] != version {
                    bail!("resource catalog version mismatch")
                }
                entries.insert(key, row);
            }
        }
        // Core 31 derives this default on the running device; a catalog captured
        // on an 8 GiB builder must not advertise 1024 MiB on a smaller Pi.
        if version.starts_with("31.") {
            let mut system = sysinfo::System::new();
            system.refresh_memory();
            if let Some(entry) = entries.get_mut("dbcache") {
                let default = if system.total_memory() >= 4_294_967_296 {
                    "1024"
                } else {
                    "450"
                };
                entry["default"] = serde_json::json!(default);
                if let Some(description) = entry["description"].as_str() {
                    entry["description"] = serde_json::json!(
                        description.replace("default: 1024", &format!("default: {default}"))
                    );
                }
            }
        }
        let runtime: Value =
            serde_json::from_slice(&fs::read(catalog.join("runtime-options.json"))?)?;
        for (key, kind, default, description) in [
            (
                "listen",
                "incoming_set",
                if network == "regtest" {
                    "tor (loopback backend)"
                } else {
                    "clearnet,tor"
                },
                "Incoming peers: none, clearnet, tor, or clearnet,tor. Internal loopback P2P remains available for electrs. Tor uses its separate tagged listener; RPC exposure is unchanged.",
            ),
            (
                "onlynet",
                "network_set",
                "all available networks",
                "Automatic outgoing destinations: comma-separated ipv4,ipv6,onion. Does not restrict incoming or manually added peers. I2P is not installed.",
            ),
            (
                "proxy",
                "tor_proxy",
                "0 (direct clearnet)",
                "0: direct Clearnet. 1: Clearnet destinations through local Tor SOCKS. Onion destinations use Tor independently. Requires running Tor for successful connections.",
            ),
        ] {
            if runtime[version]["options"]
                .as_array()
                .is_some_and(|options| options.iter().any(|option| option == key))
            {
                entries.insert(key.into(), serde_json::json!({"key":key,"type":kind,"default":default,"description":description,"unit":"network selection","source":format!("https://github.com/bitcoin/bitcoin/blob/v{version}/src/init.cpp"),"source_registration_present":true,"ignored_or_wallet_only":false,"restart_required":true,"editable":true}));
            }
        }
        Ok(Self {
            version: version.into(),
            network: network.into(),
            entries,
        })
    }
    pub fn validate(&self, input: &Values) -> Result<Values> {
        let mut out = Values::new();
        for (key, value) in input {
            let entry = self.entries.get(key).context(format!(
                "{key}: unsupported policy option for {}",
                self.version
            ))?;
            if entry["editable"] == false
                || entry["ignored_or_wallet_only"] == true
                || entry["source_registration_present"] != true
            {
                bail!("{key}: ignored, wallet-only or unverified option");
            }
            if key == "blockversion" && self.network != "regtest" {
                bail!("blockversion is restricted to regtest mining tests");
            }
            if key == "acceptnonstdtxn" && self.network == "main" && value != "0" {
                bail!("mainnet standardness cannot be disabled");
            }
            let canonical = if key == "blockversion" {
                value
                    .parse::<i32>()
                    .context("blockversion must fit signed 32-bit")?
                    .to_string()
            } else {
                match entry["type"].as_str() {
                    Some("incoming_set") => {
                        let _ = incoming_bindings(&self.network, value, None)?;
                        if value == "none" {
                            value.clone()
                        } else {
                            value
                                .split(',')
                                .collect::<std::collections::BTreeSet<_>>()
                                .into_iter()
                                .collect::<Vec<_>>()
                                .join(",")
                        }
                    }
                    Some("network_set") => {
                        let choices: std::collections::BTreeSet<_> = value.split(',').collect();
                        if choices.is_empty()
                            || choices.len() != value.split(',').count()
                            || choices
                                .iter()
                                .any(|n| !matches!(*n, "ipv4" | "ipv6" | "onion"))
                        {
                            bail!("onlynet: choose unique comma-separated ipv4,ipv6,onion");
                        }
                        choices.into_iter().collect::<Vec<_>>().join(",")
                    }
                    Some("tor_proxy") => match value.as_str() {
                        "0" => "0".into(),
                        "1" => "127.0.0.1:9050".into(),
                        _ => bail!("proxy: use 0 for direct Clearnet or 1 for local Tor"),
                    },
                    Some("boolean") => {
                        if !matches!(value.as_str(), "0" | "1") {
                            bail!("{key}: use 0 or 1");
                        }
                        value.clone()
                    }
                    Some("decimal") => {
                        crate::fee_to_core(value).context(format!("{key}: input unit is sat/vB"))?
                    }
                    Some("integer") => {
                        if value.is_empty() || !value.bytes().all(|c| c.is_ascii_digit()) {
                            bail!("{key}: nonnegative integer required");
                        }
                        let n = value.parse::<i64>().context("integer overflow")?;
                        if let (Some(min), Some(max)) = (
                            entry["range"]["min"].as_i64(),
                            entry["range"]["max"].as_i64(),
                        ) {
                            if !(min..=max).contains(&n) {
                                bail!(
                                    "{key}: accepted range is {min}..{max}; see catalog constraints"
                                )
                            }
                        }
                        if key == "dbcache" {
                            if let Ok(meminfo) = fs::read_to_string("/proc/meminfo") {
                                if let Some(kib) = meminfo.lines().find_map(|l| {
                                    l.strip_prefix("MemTotal:")
                                        .and_then(|v| v.split_whitespace().next())
                                        .and_then(|v| v.parse::<i64>().ok())
                                }) {
                                    if n > kib / 1024 * 3 / 4 {
                                        bail!(
                                            "dbcache exceeds 75% of device RAM; leave memory for Core mempool, electrs and services"
                                        )
                                    }
                                }
                            }
                        }
                        // Core multiplies these in signed 64-bit arithmetic. Reject overflow before startup.
                        let multiplier = match key.as_str() {
                            "maxmempool" => 1_000_000,
                            "maxsendbuffer" | "maxreceivebuffer" => 1000,
                            "dbcache" | "maxuploadtarget" => 1_048_576,
                            "mempoolexpiry" => 3600,
                            "limitclustersize" => 4000,
                            "limitancestorsize" | "limitdescendantsize" => 1000,
                            _ => 1,
                        };
                        n.checked_mul(multiplier)
                            .context("Core unit conversion would overflow")?;
                        if key == "limitclustercount" && n > 64 {
                            bail!("cluster count maximum is 64");
                        }
                        if matches!(
                            key.as_str(),
                            "datacarriersize" | "maxorphantx" | "bytespersigop"
                        ) && n > u32::MAX as i64
                        {
                            bail!("{key}: value would overflow Core unsigned storage");
                        }
                        if key == "blockmaxweight" {
                            let (minimum, maximum) =
                                if self.entries.contains_key("blockreservedweight") {
                                    (2000, 4_000_000)
                                } else {
                                    (4000, 3_996_000)
                                };
                            if !(minimum..=maximum).contains(&n) {
                                bail!(
                                    "blockmaxweight outside effective range {minimum}..{maximum} WU"
                                );
                            }
                        }
                        if key == "blockreservedweight" && !(2000..=4_000_000).contains(&n) {
                            bail!("blockreservedweight must be 2000..4000000 WU");
                        }
                        n.to_string()
                    }
                    _ => bail!("unreviewed policy type"),
                }
            };
            out.insert(key.clone(), canonical);
        }
        if self.entries.contains_key("blockreservedweight") {
            let reserved = out
                .get("blockreservedweight")
                .map(|v| v.parse::<u64>())
                .transpose()?
                .unwrap_or(8000);
            let maximum = out
                .get("blockmaxweight")
                .map(|v| v.parse::<u64>())
                .transpose()?
                .unwrap_or(4_000_000);
            if maximum < reserved {
                bail!("maximum block weight would be clamped to reserved weight");
            }
        }
        if out.get("privatebroadcast").is_some_and(|v| v == "1") {
            if self.version == "31.0" {
                bail!(
                    "privatebroadcast has a documented IP leak in Core31.0; choose31.1 with the upstream fix"
                )
            }
            if self.network == "regtest" {
                bail!("privatebroadcast conflicts with the isolated regtest connect=0 profile")
            }
            if out
                .get("onlynet")
                .is_some_and(|v| !v.split(',').any(|n| n == "onion"))
            {
                bail!("privatebroadcast requires onion outgoing in this Tor-only privacy stack")
            }
        }
        if out.get("peerblockfilters").is_some_and(|v| v == "1")
            && !out.get("blockfilterindex").is_some_and(|v| v == "1")
        {
            bail!("peerblockfilters requires explicitly reviewed blockfilterindex=1")
        }
        // The limit is based on topology size, not a fixed 5MB across every configuration.
        if let Some(size) = out.get("maxmempool") {
            let size = size.parse::<i64>()?;
            let cluster = self.version.split('.').next().unwrap().parse::<u32>()? >= 31;
            let key = if cluster {
                "limitclustersize"
            } else {
                "limitdescendantsize"
            };
            let kb = out
                .get(key)
                .map(|x| x.parse::<i64>())
                .transpose()?
                .unwrap_or(101);
            let bytes = kb.checked_mul(40_000).context("topology limit overflow")?;
            if !(cluster && size == 0) && size * 1_000_000 < bytes {
                bail!(
                    "maxmempool is below topology-dependent minimum ({} MB)",
                    bytes / 1_000_000 + i64::from(bytes % 1_000_000 != 0)
                );
            }
        }
        Ok(out)
    }
    pub fn preview(&self, path: &Path, requested: Values) -> Result<Plan> {
        self.current(path)?;
        let before = read_config(path)?;
        let core_values = self.validate(&requested)?;
        let old = parse_config(&before, &self.network)?;
        let changes = old
            .keys()
            .chain(core_values.keys())
            .collect::<std::collections::BTreeSet<_>>()
            .into_iter()
            .filter(|k| old.get(*k) != core_values.get(*k))
            .map(|k| {
                format!(
                    "{k}: {} -> {} (Core unit)",
                    old.get(k).map(String::as_str).unwrap_or("Core default"),
                    core_values
                        .get(k)
                        .map(String::as_str)
                        .unwrap_or("Core default")
                )
            })
            .collect();
        let mut warning=vec!["Core restart required; local relay policy does not change consensus".into(),"A private preflight startup is required before service application; help parsing alone is not semantic validation".into(),"RPC exposes only some effective values; other settings need startup/behavior evidence".into()];
        if core_values
            .get("onlynet")
            .is_some_and(|selected| !selected.split(',').any(|network| network == "onion"))
        {
            warning.push("Derived noonion=1 disables Tor outgoing explicitly, including Core22. Incoming Tor is unchanged.".into());
        }
        if core_values.get("proxy").is_some_and(|proxy| proxy != "0") {
            warning.push("Clearnet destinations will use local Tor SOCKS; working Tor and an exit allowing the destination port are required.".into());
        }
        if let Some(incoming) = core_values.get("listen") {
            warning.push(format!("Incoming selection {incoming}: Core keeps listen=1 for electrs. Derived nobind=1 replaces base bindings with {}. RPC settings do not change.",incoming_bindings(&self.network,incoming,None)?.join(", ")));
        }
        if core_values
            .get("privatebroadcast")
            .is_some_and(|v| v == "1")
        {
            warning.push("Private broadcast requires working Tor and eligible peers. Isolated preflight uses networkactive=0 instead of incompatible connect=0 and verifies startup only, not anonymity or real broadcast transport.".into());
        }
        if ["txindex", "txospenderindex", "blockfilterindex"]
            .iter()
            .any(|key| core_values.get(*key).is_some_and(|v| v == "1"))
        {
            warning.push("Optional Core indexes build asynchronously and require extra disk space. Startup acceptance is not index sync completion; getindexinfo tracks progress. Disabling an index retains its files.".into());
        }
        if old.get("txindex").is_some_and(|v| v == "1")
            && !core_values.get("txindex").is_some_and(|v| v == "1")
        {
            warning.push("Disabling txindex prevents the bundled mempool explorer from becoming ready. Historical transaction lookup is limited; existing index files are retained.".into());
        }
        if core_values.get("datacarrier").is_some_and(|v| v == "0") {
            warning.push("OP_RETURN data outputs will be rejected by local standard transaction policy. This does not reject valid blocks or filter every kind of arbitrary data. datacarriersize is inactive while datacarrier=0.".into());
        }
        if core_values.get("rest").is_some_and(|v| v == "1") {
            warning.push("REST provides unauthenticated public chain reads on the local Core RPC listener only; it is not forwarded by the LAN/onion wallet gateway.".into());
        }
        if core_values.contains_key("dbcache") {
            warning.push("dbcache excludes additional shared unused mempool cache; input is capped at 75% of device RAM, which is not a performance guarantee.".into());
        }
        Ok(Plan {
            version: self.version.clone(),
            network: self.network.clone(),
            revision: digest(before.as_bytes()),
            requested,
            core_values,
            changes,
            warning,
        })
    }
    /// The caller must preflight the same pinned binary and serialize service control.
    /// restart_and_check must coordinate Core/indexer restart and verify actual health.
    pub fn apply(
        &self,
        path: &Path,
        plan: &Plan,
        preflight: &Preflight,
        mut restart_and_check: impl FnMut() -> Result<()>,
    ) -> Result<Journal> {
        if preflight.plan_digest != digest(&serde_json::to_vec(plan)?)
            || preflight.binary_digest != digest(&fs::read(&preflight.binary_path)?)
        {
            bail!("preflight receipt or selected binary changed");
        }
        private_parent(path)?;
        let lockpath = path.with_extension("lock");
        let lock = OpenOptions::new()
            .create(true)
            .truncate(false)
            .read(true)
            .write(true)
            .mode(0o600)
            .open(lockpath)?;
        lock.lock()?;
        if plan.version != self.version || plan.network != self.network {
            bail!("preview profile mismatch");
        }
        let before = read_config(path)?;
        if digest(before.as_bytes()) != plan.revision {
            bail!("configuration changed since preview; review again");
        }
        let checked = self.preview(path, plan.requested.clone())?;
        if checked.core_values != plan.core_values {
            bail!("preview values altered");
        }
        let journalpath = path.with_extension("transaction.json");
        if journalpath.exists() {
            let previous: Journal = serde_json::from_slice(&fs::read(&journalpath)?)?;
            if !matches!(previous.phase.as_str(), "committed" | "rolled_back") {
                bail!("unfinished configuration transaction requires explicit recovery");
            }
        }
        let after = render(&checked.core_values, &self.network, None)?;
        let mut journal = Journal {
            binary_digest: preflight.binary_digest.clone(),
            phase: "prepared".into(),
            version: self.version.clone(),
            network: self.network.clone(),
            before: before.clone(),
            after: after.clone(),
            error: None,
        };
        atomic(&journalpath, &serde_json::to_vec_pretty(&journal)?)?;
        atomic(path, after.as_bytes())?;
        journal.phase = "restarting".into();
        atomic(&journalpath, &serde_json::to_vec_pretty(&journal)?)?;
        match restart_and_check() {
            Ok(()) => journal.phase = "committed".into(),
            Err(_) => {
                journal.phase = "rolling_back".into();
                journal.error = Some("Core configuration health check failed".into());
                atomic(&journalpath, &serde_json::to_vec_pretty(&journal)?)?;
                atomic(path, before.as_bytes())?;
                match restart_and_check() {
                    Ok(()) => journal.phase = "rolled_back".into(),
                    Err(_) => journal.phase = "recovery_failed".into(),
                }
            }
        }
        atomic(&journalpath, &serde_json::to_vec_pretty(&journal)?)?;
        Ok(journal)
    }
}
fn read_config(path: &Path) -> Result<String> {
    if let Ok(m) = fs::symlink_metadata(path) {
        if !m.is_file() || m.file_type().is_symlink() {
            bail!("managed config must be a regular file");
        }
    }
    match fs::read_to_string(path) {
        Ok(s) => Ok(s),
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(String::new()),
        Err(e) => Err(e.into()),
    }
}
fn incoming_bindings(
    network: &str,
    selection: &str,
    isolated_port: Option<u16>,
) -> Result<Vec<String>> {
    let selected: std::collections::BTreeSet<_> = selection.split(',').collect();
    if selection != "none"
        && (selected.len() != selection.split(',').count()
            || selected.iter().any(|n| !matches!(*n, "clearnet" | "tor")))
    {
        bail!("listen: choose none, clearnet, tor, or clearnet,tor");
    }
    let port = isolated_port.unwrap_or(match network {
        "main" => 8333,
        "test" => 18333,
        "testnet4" => 48333,
        "signet" => 38333,
        "regtest" => 18444,
        _ => bail!("unknown listener network"),
    });
    let mut bindings = if selected.contains("clearnet") && isolated_port.is_none() {
        vec![format!("0.0.0.0:{port}"), format!("[::]:{port}")]
    } else {
        vec![format!("127.0.0.1:{port}")]
    };
    if selected.contains("tor") {
        bindings.push(format!(
            "127.0.0.1:{}=onion",
            port.checked_add(1).context("onion port overflow")?
        ));
    }
    Ok(bindings)
}

/// Verify the actual systemd Core process owns exactly the reviewed P2P listeners.
/// RPC does not expose bound sockets, so never label this an RPC observation.
pub fn verify_incoming_process(
    values: &Values,
    network: &str,
    binary: &Path,
    backend_port: Option<u16>,
) -> Result<()> {
    if !values.contains_key("listen") && backend_port.is_none() {
        return Ok(());
    }
    let selection = values
        .get("listen")
        .map(String::as_str)
        .unwrap_or(if network == "regtest" {
            "tor"
        } else {
            "clearnet,tor"
        });
    let mut expected: std::collections::BTreeSet<std::net::SocketAddr> =
        incoming_bindings(network, selection, None)?
            .iter()
            .map(|b| b.trim_end_matches("=onion").parse())
            .collect::<std::result::Result<_, _>>()?;
    let port = expected
        .iter()
        .map(|a| a.port())
        .min()
        .context("no P2P listener")?;
    if let Some(backend) = backend_port {
        if backend != port + 2 {
            bail!("unexpected electrs backend port")
        }
        expected.insert(std::net::SocketAddr::from(([127, 0, 0, 1], backend)));
    }
    let output = std::process::Command::new("/usr/bin/systemctl")
        .args([
            "show",
            "--property=MainPID",
            "--value",
            "justverify-core.service",
        ])
        .output()?;
    if !output.status.success() {
        bail!("cannot identify Core service process")
    }
    let pid: u32 = std::str::from_utf8(&output.stdout)?.trim().parse()?;
    if pid == 0 {
        bail!("Core service has no process")
    }
    let process = PathBuf::from(format!("/proc/{pid}"));
    if fs::read_link(process.join("exe"))?.canonicalize()? != binary.canonicalize()? {
        bail!("Core service executable differs from selected binary")
    }
    let mut owned = std::collections::BTreeSet::new();
    for fd in fs::read_dir(process.join("fd"))? {
        // Short-lived RPC sockets may close while enumerating. Required listening
        // sockets remain open and their omission fails the exact comparison below.
        if let Ok(target) = fs::read_link(fd?.path()) {
            if let Some(inode) = target
                .to_str()
                .and_then(|s| s.strip_prefix("socket:["))
                .and_then(|s| s.strip_suffix(']'))
            {
                owned.insert(inode.to_string());
            }
        }
    }
    let mut actual = std::collections::BTreeSet::new();
    for table in ["tcp", "tcp6"] {
        let contents = fs::read_to_string(process.join("net").join(table))?;
        for line in contents.lines().skip(1) {
            let fields: Vec<_> = line.split_whitespace().collect();
            if fields.len() < 10 || fields[3] != "0A" || !owned.contains(fields[9]) {
                continue;
            }
            let (ip, hex_port) = fields[1].split_once(':').context("invalid kernel socket")?;
            let bound_port = u16::from_str_radix(hex_port, 16)?;
            if bound_port != port && bound_port != port + 1 && Some(bound_port) != backend_port {
                continue;
            }
            let ip: std::net::IpAddr = if ip.len() == 8 {
                std::net::Ipv4Addr::from(u32::from_str_radix(ip, 16)?.to_ne_bytes()).into()
            } else if ip.len() == 32 {
                let mut bytes = [0u8; 16];
                for i in 0..4 {
                    bytes[i * 4..i * 4 + 4].copy_from_slice(
                        &u32::from_str_radix(&ip[i * 8..i * 8 + 8], 16)?.to_ne_bytes(),
                    );
                }
                std::net::Ipv6Addr::from(bytes).into()
            } else {
                bail!("invalid kernel socket address")
            };
            actual.insert(std::net::SocketAddr::new(ip, bound_port));
        }
    }
    if actual != expected {
        bail!("Core process P2P listeners differ from reviewed incoming selection")
    }
    Ok(())
}

fn parse_config(text: &str, network: &str) -> Result<Values> {
    let mut out = Values::new();
    let mut bindings = Vec::new();
    let mut clear_bind = false;
    let mut binding_section = false;
    for line in text.lines() {
        if let Some(incoming) = line.strip_prefix("# JustVerify incoming=") {
            if out.insert("listen".into(), incoming.into()).is_some() {
                bail!("duplicate incoming selector");
            }
            continue;
        }
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        if line == format!("[{network}]") && !binding_section {
            binding_section = true;
            continue;
        }
        let (k, v) = line
            .split_once('=')
            .context("managed config syntax error")?;
        if binding_section != matches!(k, "bind" | "nobind") {
            bail!("managed option in incorrect network section");
        }
        if k == "noasmap" {
            if v != "1" || out.insert("asmap".into(), "0".into()).is_some() {
                bail!("invalid disabled asmap")
            }
        } else if k == "bind" {
            bindings.push(v.to_string());
        } else if k == "nobind" {
            if v != "1" || clear_bind {
                bail!("invalid derived binding reset");
            }
            clear_bind = true;
        } else if k == "onlynet" {
            out.entry(k.into())
                .and_modify(|old| {
                    old.push(',');
                    old.push_str(v);
                })
                .or_insert_with(|| v.into());
        } else if out.insert(k.into(), v.into()).is_some() {
            bail!("duplicate managed key");
        }
    }
    if let Some(incoming) = out.get("listen") {
        if !clear_bind || bindings != incoming_bindings(network, incoming, None)? {
            bail!("incoming bindings differ from reviewed selector");
        }
    } else if clear_bind || !bindings.is_empty() {
        bail!("unmanaged bindings refused");
    }
    if let Some(derived) = out.remove("noonion") {
        if derived != "1"
            || !out
                .get("onlynet")
                .is_some_and(|selected| !selected.split(',').any(|network| network == "onion"))
        {
            bail!("unexpected derived onion setting");
        }
    }
    Ok(out)
}
fn render(values: &Values, network: &str, isolated_port: Option<u16>) -> Result<String> {
    let mut out =
        String::from("# JustVerify managed policy; units are Bitcoin Core native units\n");
    for (k, v) in values {
        if k == "listen" {
            continue;
        } else if k == "asmap" && v == "0" {
            out.push_str("noasmap=1\n");
        } else if k == "onlynet" {
            for network in v.split(',') {
                out.push_str(&format!("onlynet={network}\n"));
            }
        } else {
            out.push_str(&format!("{k}={v}\n"));
        }
    }
    // Core22 explicitly warns that onlynet does not override onion/proxy.
    // A negated setting in the included file clears the base onion default.
    if values
        .get("onlynet")
        .is_some_and(|selected| !selected.split(',').any(|network| network == "onion"))
    {
        out.push_str("noonion=1\n");
    }
    if let Some(incoming) = values.get("listen") {
        out.push_str(&format!(
            "# JustVerify incoming={incoming}\n[{network}]\nnobind=1\n"
        ));
        for binding in incoming_bindings(network, incoming, isolated_port)? {
            out.push_str(&format!("bind={binding}\n"));
        }
    }
    Ok(out)
}
fn private_parent(path: &Path) -> Result<PathBuf> {
    let parent = path.parent().context("missing config directory")?;
    if fs::symlink_metadata(parent)?.file_type().is_symlink()
        || fs::metadata(parent)?.permissions().mode() & 0o077 != 0
    {
        bail!("private nonsymlink configuration directory required");
    }
    Ok(parent.into())
}
pub(crate) fn atomic(path: &Path, bytes: &[u8]) -> Result<()> {
    let parent = private_parent(path)?;
    let temp = parent.join(format!(".jv-{}-{}", std::process::id(), digest(bytes)));
    let mut f = OpenOptions::new()
        .create_new(true)
        .write(true)
        .mode(0o600)
        .open(&temp)?;
    let outcome = (|| -> Result<()> {
        f.write_all(bytes)?;
        f.sync_all()?;
        fs::rename(&temp, path)?;
        fs::File::open(parent)?.sync_all()?;
        Ok(())
    })();
    if outcome.is_err() {
        let _ = fs::remove_file(temp);
    }
    outcome
}

#[derive(Debug, Serialize)]
pub struct Preflight {
    plan_digest: String,
    binary_path: PathBuf,
    binary_digest: String,
    pub observed: Value,
    pub networks: Value,
    pub resources: Vec<String>,
    pub indexes: Value,
    pub verification: String,
}
struct ChildGuard(std::process::Child);
impl Drop for ChildGuard {
    fn drop(&mut self) {
        if self.0.try_wait().ok().flatten().is_none() {
            let _ = self.0.kill();
            let _ = self.0.wait();
        }
    }
}
impl Policy {
    /// Starts the selected binary on fresh private data and an ephemeral loopback RPC port.
    /// This checks actual startup/RPC, not all possible policy transaction behavior.
    pub fn preflight(&self, binary: &Path, staging_root: &Path, plan: &Plan) -> Result<Preflight> {
        if plan.version != self.version
            || plan.network != self.network
            || self.validate(&plan.requested)? != plan.core_values
        {
            bail!("invalid preview for preflight");
        }
        private_parent(&staging_root.join("probe"))?;
        let nonce = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)?
            .as_nanos();
        let stage = staging_root.join(format!("preflight-{}-{nonce}", std::process::id()));
        fs::create_dir(&stage)?;
        fs::set_permissions(&stage, fs::Permissions::from_mode(0o700))?;
        let binary = binary.canonicalize()?;
        let binary_digest = digest(&fs::read(&binary)?);
        let result = (|| -> Result<Preflight> {
            let config = stage.join("bitcoin.conf");
            let managed = stage.join("managed.conf");
            // Reserve both adjacent P2P ports while selecting the RPC port.
            // A free first port does not imply its onion port is free.
            let (probe_listener, onion_listener) = (0..64)
                .find_map(|_| {
                    let first = std::net::TcpListener::bind("127.0.0.1:0").ok()?;
                    let second_port = first.local_addr().ok()?.port().checked_add(1)?;
                    let second = std::net::TcpListener::bind(("127.0.0.1", second_port)).ok()?;
                    Some((first, second))
                })
                .context("cannot reserve isolated P2P/onion port pair")?;
            let probe_port = probe_listener.local_addr()?.port();
            atomic(
                &managed,
                render(&plan.core_values, &self.network, Some(probe_port))?.as_bytes(),
            )?;
            atomic(
                &config,
                format!(
                    "onion=127.0.0.1:9050\nlistenonion=0\nincludeconf={}\n",
                    managed.display()
                )
                .as_bytes(),
            )?;
            let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
            let port = listener.local_addr()?.port();
            drop(listener);
            drop(probe_listener);
            drop(onion_listener);
            let mut command = std::process::Command::new(&binary);
            command.args([
                format!("-datadir={}", stage.display()),
                format!("-conf={}", config.display()),
                format!("-rpcport={port}"),
                "-server=1".into(),
                "-disablewallet=1".into(),
                format!(
                    "-listen={}",
                    u8::from(plan.core_values.contains_key("listen"))
                ),
                if plan
                    .core_values
                    .get("privatebroadcast")
                    .is_some_and(|v| v == "1")
                {
                    "-networkactive=0".into()
                } else {
                    "-connect=0".into()
                },
                "-dnsseed=0".into(),
                "-listenonion=0".into(),
                "-rpcbind=127.0.0.1".into(),
                "-rpcallowip=127.0.0.1".into(),
                "-printtoconsole=0".into(),
            ]);
            if self.network != "main" {
                command.arg(match self.network.as_str() {
                    "test" => "-testnet",
                    "testnet4" => "-testnet4",
                    "signet" => "-signet",
                    "regtest" => "-regtest",
                    _ => bail!("invalid network"),
                });
            }
            let cookie = stage.join(match self.network.as_str() {
                "main" => ".cookie",
                "test" => "testnet3/.cookie",
                "testnet4" => "testnet4/.cookie",
                "signet" => "signet/.cookie",
                _ => "regtest/.cookie",
            });
            let logfile = OpenOptions::new()
                .create_new(true)
                .write(true)
                .mode(0o600)
                .open(stage.join("startup.log"))?;
            let mut child = ChildGuard(
                command
                    .stdout(logfile.try_clone()?)
                    .stderr(logfile)
                    .spawn()?,
            );
            let rpc = crate::Rpc::new(port, &cookie)?;
            let deadline = std::time::Instant::now() + std::time::Duration::from_secs(20);
            let info = loop {
                if child.0.try_wait()?.is_some() {
                    bail!("Core rejected candidate configuration; private startup log retained");
                }
                if let Ok(v) = rpc.call("getnetworkinfo", serde_json::json!([])) {
                    break v;
                }
                if std::time::Instant::now() > deadline {
                    bail!("Core candidate startup timed out");
                }
                std::thread::sleep(std::time::Duration::from_millis(100));
            };
            let parts = self
                .version
                .split('.')
                .map(str::parse::<u64>)
                .collect::<std::result::Result<Vec<_>, _>>()?;
            let expected = parts[0] * 10000 + parts[1] * 100 + parts.get(2).copied().unwrap_or(0);
            if info["version"].as_u64() != Some(expected) {
                bail!("preflight binary version does not match selected release");
            }
            if plan
                .core_values
                .get("privatebroadcast")
                .is_some_and(|v| v == "1")
                && info["networkactive"] != false
            {
                bail!("private broadcast preflight must have networking disabled")
            }
            let observed = rpc.call("getmempoolinfo", serde_json::json!([]))?;
            verify_observable(&plan.core_values, &observed)?;
            verify_network_observable(&plan.core_values, &info)?;
            if let Some(incoming) = plan.core_values.get("listen") {
                use std::net::TcpStream;
                TcpStream::connect_timeout(
                    &format!("127.0.0.1:{probe_port}").parse()?,
                    std::time::Duration::from_secs(1),
                )?;
                let onion = TcpStream::connect_timeout(
                    &format!("127.0.0.1:{}", probe_port + 1).parse()?,
                    std::time::Duration::from_millis(300),
                )
                .is_ok();
                if onion != incoming.split(',').any(|n| n == "tor") {
                    bail!("isolated onion listener does not match incoming selector");
                }
            }
            let indexes = rpc.call("getindexinfo", serde_json::json!([]))?;
            verify_auxiliary(
                &plan.core_values,
                &info,
                &indexes,
                &cookie.with_file_name("debug.log"),
                port,
            )?;
            let resources = verify_resources(
                &plan.core_values,
                &cookie.with_file_name("debug.log"),
                &rpc.call("getnettotals", serde_json::json!([]))?,
            )?;
            rpc.call("stop", serde_json::json!([]))?;
            let stop_deadline = std::time::Instant::now() + std::time::Duration::from_secs(10);
            while child.0.try_wait()?.is_none() {
                if std::time::Instant::now() > stop_deadline {
                    bail!("preflight Core did not stop cleanly");
                }
                std::thread::sleep(std::time::Duration::from_millis(100));
            }
            Ok(Preflight{plan_digest:digest(&serde_json::to_vec(plan)?),binary_path:binary,binary_digest,observed,networks:info["networks"].clone(),resources,indexes,verification:"fresh-data startup and actual getmempoolinfo/getnetworkinfo/getnettotals; resource receipts distinguish configuration logs from observable RPC; incoming TCP listeners checked on remapped loopback ports (external interfaces require post-restart integration); not full transaction-policy or transport behavior".into()})
        })();
        // Retain failed staging evidence privately. Successful preflight state has no reuse value.
        if result.is_ok() {
            fs::remove_dir_all(stage)?;
        }
        result
    }
}

impl Policy {
    pub fn entries(&self) -> Vec<Value> {
        self.entries.values().cloned().collect()
    }
    pub fn current(&self, path: &Path) -> Result<Values> {
        let native = parse_config(&read_config(path)?, &self.network)?;
        let mut input = Values::new();
        for (key, value) in native {
            let entry = self
                .entries
                .get(&key)
                .context("unknown option in managed file; manual review required")?;
            let value = if entry["type"] == "tor_proxy" {
                match value.as_str() {
                    "127.0.0.1:9050" => "1".into(),
                    "0" => "0".into(),
                    _ => bail!("unmanaged proxy endpoint refused"),
                }
            } else if entry["type"] == "decimal" {
                native_fee_to_input(&value)?
            } else {
                value
            };
            input.insert(key, value);
        }
        // Previously exposed in Core 30 even though Core ignores it. Preserve
        // the saved request for explicit removal in review, never accept a new
        // save of this option or treat it as an effective runtime setting.
        let mut effective = input.clone();
        self.remove_obsolete(&mut effective);
        self.validate(&effective)?;
        Ok(input)
    }
    fn remove_obsolete(&self, values: &mut Values) {
        if self.version.starts_with("30.") {
            values.remove("maxorphantx");
        }
    }
    pub fn current_effective(&self, path: &Path) -> Result<Values> {
        let mut values = self.current(path)?;
        self.remove_obsolete(&mut values);
        self.validate(&values)
    }
    pub fn recover(
        &self,
        path: &Path,
        binary: &Path,
        mut restart_and_check: impl FnMut() -> Result<()>,
    ) -> Result<Journal> {
        private_parent(path)?;
        let lock = OpenOptions::new()
            .create(true)
            .truncate(false)
            .read(true)
            .write(true)
            .mode(0o600)
            .open(path.with_extension("lock"))?;
        lock.lock()?;
        let journalpath = path.with_extension("transaction.json");
        let mut j: Journal = serde_json::from_slice(&fs::read(&journalpath)?)?;
        if j.version != self.version
            || j.network != self.network
            || j.binary_digest != digest(&fs::read(binary)?)
        {
            bail!("recovery cannot cross binary or data profile changes");
        }
        if matches!(j.phase.as_str(), "committed" | "rolled_back") {
            return Ok(j);
        }
        let current = read_config(path)?;
        if current != j.before && current != j.after {
            bail!("configuration changed outside transaction; manual review required");
        }
        j.phase = "rolling_back".into();
        atomic(&journalpath, &serde_json::to_vec_pretty(&j)?)?;
        atomic(path, j.before.as_bytes())?;
        j.phase = if restart_and_check().is_ok() {
            "rolled_back".into()
        } else {
            "recovery_failed".into()
        };
        atomic(&journalpath, &serde_json::to_vec_pretty(&j)?)?;
        Ok(j)
    }
}
fn native_fee_to_input(value: &str) -> Result<String> {
    let (whole, fraction) = value.split_once('.').unwrap_or((value, ""));
    if whole.is_empty()
        || !whole.bytes().all(|c| c.is_ascii_digit())
        || fraction.len() > 8
        || !fraction.bytes().all(|c| c.is_ascii_digit())
    {
        bail!("invalid Core fee in managed file");
    }
    let units = whole
        .parse::<u64>()?
        .checked_mul(100_000_000)
        .and_then(|v| v.checked_add(format!("{fraction:0<8}").parse::<u64>().ok()?))
        .context("fee overflow")?;
    let text = format!("{}.{:03}", units / 1000, units % 1000);
    Ok(text.trim_end_matches('0').trim_end_matches('.').into())
}

pub fn verify_network_observable(values: &Values, info: &Value) -> Result<()> {
    for network in ["ipv4", "ipv6", "onion"] {
        let row = info["networks"]
            .as_array()
            .context("missing Core networks")?
            .iter()
            .find(|row| row["name"] == network)
            .context("missing Core network")?;
        if let Some(selected) = values.get("onlynet") {
            let expected = !selected.split(',').any(|n| n == network);
            if row["limited"].as_bool() != Some(expected) {
                bail!(
                    "onlynet effective network mismatch for {network}: expected limited={expected}, observed {}",
                    row["limited"]
                );
            }
        }
        if network != "onion" {
            if let Some(proxy) = values.get("proxy") {
                let expected = if proxy == "0" { "" } else { "127.0.0.1:9050" };
                if row["proxy"].as_str() != Some(expected) {
                    bail!("Core effective proxy mismatch");
                }
            }
        }
    }
    Ok(())
}

pub fn verify_observable(values: &Values, mempool: &Value) -> Result<Vec<String>> {
    let mut checked = Vec::new();
    for (key, value) in values {
        let expected = match key.as_str() {
            "maxmempool" => Some((
                "maxmempool",
                serde_json::json!(
                    value
                        .parse::<u64>()?
                        .checked_mul(1_000_000)
                        .context("memory overflow")?
                ),
            )),
            "minrelaytxfee" => Some(("minrelaytxfee", serde_json::json!(value.parse::<f64>()?))),
            "datacarriersize" if values.get("datacarrier").map(String::as_str) != Some("0") => {
                Some((
                    "maxdatacarriersize",
                    serde_json::json!(value.parse::<u64>()?),
                ))
            }
            "permitbaremultisig" => Some(("permitbaremultisig", serde_json::json!(value == "1"))),
            "mempoolfullrbf" => Some(("fullrbf", serde_json::json!(value == "1"))),
            _ => None,
        };
        if let Some((field, wanted)) = expected {
            if !mempool[field].is_null() {
                if mempool[field] != wanted {
                    bail!("Core effective value mismatch for {key}");
                }
                checked.push(key.clone());
            }
        }
    }
    Ok(checked)
}

pub fn transaction_status(path: &Path) -> Result<Value> {
    let journal = path.with_extension("transaction.json");
    if !journal.exists() {
        return Ok(serde_json::json!({"phase":"none","needs_recovery":false}));
    }
    let j: Journal = serde_json::from_slice(&fs::read(journal)?)?;
    Ok(
        serde_json::json!({"phase":j.phase,"needs_recovery":!matches!(j.phase.as_str(),"committed"|"rolled_back"),"error":j.error}),
    )
}

/// Only whitelisted resource lines are returned; logs may contain other private data.
pub fn verify_resources(values: &Values, log: &Path, totals: &Value) -> Result<Vec<String>> {
    use std::io::{Read, Seek, SeekFrom};
    const KEYS: [&str; 9] = [
        "bantime",
        "maxconnections",
        "maxreceivebuffer",
        "maxsendbuffer",
        "peertimeout",
        "timeout",
        "maxuploadtarget",
        "dbcache",
        "rpcworkqueue",
    ];
    if !KEYS.iter().any(|key| values.contains_key(*key)) {
        return Ok(Vec::new());
    }
    let mut file = fs::File::open(log)?;
    let length = file.metadata()?.len();
    file.seek(SeekFrom::Start(length.saturating_sub(262144)))?;
    let mut bytes = Vec::new();
    file.read_to_end(&mut bytes)?;
    let log = String::from_utf8_lossy(&bytes);
    let mut evidence = Vec::new();
    for key in KEYS {
        if let Some(value) = values.get(key) {
            let expected = format!("Config file arg: {key}=\"{value}\"");
            if !log.lines().any(|line| line.ends_with(&expected)) {
                bail!("resource configuration not observed in Core startup log: {key}")
            }
            evidence.push(format!(
                "{key}={value}: Core startup configuration log (not RPC effective value)"
            ));
        }
    }
    if let Some(value) = values.get("maxconnections") {
        let actual = log
            .lines()
            .rev()
            .find_map(|line| {
                line.split_once("Using at most ")
                    .and_then(|(_, s)| s.split_whitespace().next())
                    .and_then(|s| s.parse::<u64>().ok())
            })
            .context("Core connection limit was not observed")?;
        if actual != value.parse::<u64>()? {
            bail!("Core clamped maxconnections to {actual}; request rejected")
        }
        evidence.push(format!("maxconnections={actual}: effective startup limit"));
    }
    if let Some(value) = values.get("maxuploadtarget") {
        let bytes = value
            .parse::<u64>()?
            .checked_mul(1_048_576)
            .context("upload target overflow")?;
        if totals["uploadtarget"]["target"].as_u64() != Some(bytes) {
            bail!("effective RPC upload target differs")
        }
        evidence.push(format!(
            "maxuploadtarget={bytes} bytes: actual getnettotals"
        ));
    }
    Ok(evidence)
}

pub fn verify_auxiliary(
    values: &Values,
    network: &Value,
    indexes: &Value,
    log: &Path,
    rpc_port: u16,
) -> Result<()> {
    for (key, name) in [
        ("txindex", "txindex"),
        ("txospenderindex", "txospenderindex"),
        ("blockfilterindex", "basic block filter index"),
    ] {
        if let Some(selected) = values.get(key) {
            if indexes.get(name).is_some() != (selected == "1") {
                bail!("configured index not reflected in getindexinfo: {key}")
            }
        }
    }
    for (key, name) in [
        ("peerblockfilters", "COMPACT_FILTERS"),
        ("peerbloomfilters", "BLOOM"),
    ] {
        if let Some(selected) = values.get(key) {
            let active = network["localservicesnames"]
                .as_array()
                .context("Core service names missing")?
                .iter()
                .any(|v| v == name);
            if active != (selected == "1") {
                bail!("Core service capability differs: {key}")
            }
        }
    }
    if let Some(selected) = values.get("asmap") {
        use std::io::{Read, Seek, SeekFrom};
        let mut file = fs::File::open(log)?;
        let length = file.metadata()?.len();
        file.seek(SeekFrom::Start(length.saturating_sub(262144)))?;
        let mut bytes = Vec::new();
        file.read_to_end(&mut bytes)?;
        let logs = String::from_utf8_lossy(&bytes);
        let latest = logs
            .lines()
            .rev()
            .find(|l| l.contains("for IP bucketing"))
            .context("asmap startup evidence absent")?;
        if latest.contains("Using asmap version") != (selected == "1") {
            bail!("actual asmap bucketing differs")
        }
    }
    if let Some(selected) = values.get("rest") {
        let response = reqwest::blocking::Client::builder()
            .no_proxy()
            .timeout(std::time::Duration::from_secs(3))
            .build()?
            .get(format!("http://127.0.0.1:{rpc_port}/rest/chaininfo.json"))
            .send()?;
        if response.status().is_success() != (selected == "1") {
            bail!("local REST availability differs")
        }
        if selected == "1" {
            let value: Value = response.json()?;
            if !value["chain"].is_string() {
                bail!("invalid REST chain response")
            }
        }
    }
    Ok(())
}
