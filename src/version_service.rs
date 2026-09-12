//! Unprivileged version API; root bridge accepts only fixed action/version/network identifiers.
use crate::{
    Rpc,
    versions::{Preview, Runtime, Selection, Versions},
};
use anyhow::{Context, Result, bail};
use serde::Deserialize;
use serde_json::{Value, json};
use std::{
    collections::BTreeMap,
    fs,
    io::{BufRead, BufReader, Read, Write},
    os::unix::{
        fs::{OpenOptionsExt, PermissionsExt},
        net::UnixListener,
    },
    path::{Path, PathBuf},
    process::{Command, Stdio},
    time::{Duration, Instant},
};
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Config {
    catalog: PathBuf,
    binaries: PathBuf,
    data: PathBuf,
    state: PathBuf,
    #[serde(default)]
    allow_initial_selection: bool,
}
struct Native;
fn bridge(request: Value) -> Result<()> {
    let mut child = Command::new("/usr/bin/sudo")
        .args(["-n", "/usr/libexec/justverify-profile"])
        .stdin(Stdio::piped())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()?;
    child
        .stdin
        .take()
        .unwrap()
        .write_all(&serde_json::to_vec(&request)?)?;
    if !child.wait()?.success() {
        bail!("fixed profile bridge failed; check service state");
    }
    Ok(())
}
fn network(network: &str) -> Result<(u16, &'static str)> {
    Ok(match network {
        "main" => (8332, ""),
        "test" => (18332, "testnet3"),
        "testnet4" => (48332, "testnet4"),
        "signet" => (38332, "signet"),
        "regtest" => (18443, "regtest"),
        _ => bail!("unsupported network"),
    })
}
impl Runtime for Native {
    fn stop(&mut self) -> Result<()> {
        bridge(json!({"action":"stop"}))
    }
    fn start_and_check(&mut self, selection: &Selection) -> Result<()> {
        bridge(
            json!({"action":"activate","version":selection.instance.core_version,"network":selection.instance.network,"watch_only":selection.instance.watch_only}),
        )?;
        let (port, sub) = network(&selection.instance.network)?;
        let rpc = Rpc::new(
            port,
            &selection.instance.core_data.join(sub).join(".cookie"),
        )?;
        let parts: Vec<u64> = selection
            .instance
            .core_version
            .split('.')
            .map(str::parse)
            .collect::<std::result::Result<_, _>>()?;
        let expected = parts[0] * 10000 + parts[1] * 100 + parts.get(2).copied().unwrap_or(0);
        let end = Instant::now() + Duration::from_secs(25);
        while Instant::now() < end {
            if let (Ok(chain), Ok(info)) = (
                rpc.call("getblockchaininfo", json!([])),
                rpc.call("getnetworkinfo", json!([])),
            ) {
                if chain["chain"] != selection.instance.network || info["version"] != expected {
                    bail!("running Core does not match selected version/network");
                }
                if !Command::new("/usr/bin/systemctl")
                    .args([
                        "is-active",
                        "--quiet",
                        "justverify-electrs",
                        "justverify-manager",
                        "justverify-policy",
                    ])
                    .status()?
                    .success()
                {
                    bail!("dependent services not active");
                }
                // During IBD the indexer intentionally waits. Do not label this as fully indexed.
                if chain["initialblockdownload"] == true {
                    return Ok(());
                }
                if crate::electrs_height(50001).is_ok_and(|h| chain["blocks"].as_u64() == Some(h)) {
                    return Ok(());
                }
            }
            std::thread::sleep(Duration::from_millis(200));
        }
        bail!("selected services did not become ready")
    }
}
pub fn operation_lock() -> Result<fs::File> {
    let file = fs::OpenOptions::new()
        .create(true)
        .truncate(false)
        .read(true)
        .write(true)
        .mode(0o600)
        .open("/var/lib/justverify/config/operations.lock")?;
    file.lock()?;
    Ok(file)
}
pub fn serve(config_path: &Path, socket: &Path) -> Result<()> {
    let bytes = fs::read(config_path)?;
    let config: Config = serde_json::from_slice(&bytes)?;
    let versions = Versions::new(
        &config.catalog,
        &config.binaries,
        &config.data,
        &config.state,
    )?;
    let downloads = crate::download::Downloads::new(&config.state)?;
    let parent = socket.parent().context("socket parent required")?;
    if fs::metadata(parent)?.permissions().mode() & 0o077 != 0 {
        bail!("version socket must be private");
    }
    let listener = UnixListener::bind(socket)?;
    fs::set_permissions(socket, fs::Permissions::from_mode(0o600))?;
    let mut previews: BTreeMap<String, (Preview, Instant)> = BTreeMap::new();
    for stream in listener.incoming() {
        let mut stream = stream?;
        stream.set_read_timeout(Some(Duration::from_secs(3)))?;
        stream.set_write_timeout(Some(Duration::from_secs(3)))?;
        let result = (|| -> Result<Value> {
            if fs::read(config_path)? != bytes {
                bail!("version service configuration changed; restart required");
            }
            let mut text = String::new();
            BufReader::new(stream.try_clone()?)
                .take(4096)
                .read_line(&mut text)?;
            if !text.ends_with('\n') {
                bail!("invalid request framing");
            }
            let request: Value = serde_json::from_str(&text)?;
            let object = request.as_object().context("object required")?;
            let method = request["method"].as_str().context("method required")?;
            let allowed = match method {
                "state" | "recover" => vec!["method"],
                "preview" => vec!["method", "version", "network", "watch_only"],
                "apply" => vec!["method", "token"],
                "download" => vec!["method", "version"],
                _ => bail!("unknown method"),
            };
            if object.keys().any(|k| !allowed.contains(&k.as_str())) {
                bail!("unknown request field");
            }
            previews.retain(|_, (_, time)| time.elapsed() < Duration::from_secs(300));
            match method {
                "download" => downloads.start(
                    &config.catalog,
                    request["version"].as_str().context("version required")?,
                ),
                "state" => {
                    let download = downloads.status();
                    let mut catalog: Value =
                        serde_json::from_slice(&fs::read(config.catalog.join("releases.json"))?)?;
                    for release in catalog["releases"].as_array_mut().context("bad catalog")? {
                        let version = release["version"].as_str().context("bad version")?;
                        release["downloaded"] = json!(
                            config
                                .binaries
                                .join(version)
                                .join(format!("bitcoin-{version}/bin/bitcoind"))
                                .is_file()
                        );
                    }
                    let (active, active_error) = match versions.active() {
                        Ok(active) => (active, None),
                        Err(error) => (None, Some(crate::clean(&error.to_string()))),
                    };
                    Ok(
                        json!({"active":active,"active_error":active_error,"transition":versions.recovery_status()?,"download":download,"releases":catalog["releases"],"scope":"a committed selection may still be synchronizing; index readiness is shown separately"}),
                    )
                }
                "preview" => {
                    if versions.active()?.is_none() && !config.allow_initial_selection {
                        bridge(json!({"action":"check_initial"}))
                            .context("initial setup requires an enrolled owner and a newly provisioned empty volume")?;
                    }
                    if previews.len() >= 4 {
                        bail!("too many previews; wait for expiry");
                    }
                    let watch_only = match request.get("watch_only") {
                        Some(v) => v.as_bool().context("watch_only must be boolean")?,
                        None => false,
                    };
                    let preview = versions.preview_mode(
                        request["version"].as_str().context("version required")?,
                        request["network"].as_str().context("network required")?,
                        watch_only,
                    )?;
                    let mut random = [0u8; 24];
                    fs::File::open("/dev/urandom")?.read_exact(&mut random)?;
                    let token: String = random.iter().map(|b| format!("{b:02x}")).collect();
                    let response = json!({"token":token,"preview":preview});
                    previews.insert(token, (preview, Instant::now()));
                    Ok(response)
                }
                "apply" => {
                    let token = request["token"].as_str().context("token required")?;
                    let (preview, _) = previews
                        .remove(token)
                        .context("preview missing or expired")?;
                    let _lock = operation_lock()?;
                    if versions.active()?.is_none() && !config.allow_initial_selection {
                        bridge(json!({"action":"check_initial"})).context(
                            "initial volume changed after preview; existing data preserved",
                        )?;
                    }
                    Ok(serde_json::to_value(versions.apply(preview, &mut Native)?)?)
                }
                "recover" => {
                    let _lock = operation_lock()?;
                    Ok(serde_json::to_value(versions.recover(&mut Native)?)?)
                }
                _ => unreachable!(),
            }
        })();
        let response = match result {
            Ok(value) => json!({"ok":true,"result":value}),
            Err(error) => json!({"ok":false,"error":crate::clean(&error.to_string())}),
        };
        let _ = stream.write_all(&serde_json::to_vec(&response)?);
    }
    Ok(())
}
