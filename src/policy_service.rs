//! Unprivileged administrative API. Privilege is limited to one fixed restart helper.
use crate::policy::{Plan, Policy, Preflight, Values};
use anyhow::{Context, Result, bail};
use serde::Deserialize;
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::{
    collections::BTreeMap,
    fs,
    io::{BufRead, BufReader, Read, Write},
    os::unix::{fs::PermissionsExt, net::UnixListener},
    path::{Path, PathBuf},
    time::{Duration, Instant},
};
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Profile {
    #[serde(default, rename = "watch_only")]
    _watch_only: bool,
    version: String,
    network: String,
    binary: PathBuf,
    catalog: PathBuf,
    managed_config: PathBuf,
    staging: PathBuf,
    cookie: PathBuf,
    rpc_port: u16,
    #[serde(default)]
    p2p_backend_port: Option<u16>,
}
#[derive(Deserialize)]
#[serde(tag = "method", rename_all = "snake_case", deny_unknown_fields)]
enum Request {
    State,
    Preview { values: Values },
    PreviewConfig { config: String },
    Apply { token: String },
    Recover,
}
fn restart(profile: &Profile, policy: &Policy) -> Result<()> {
    let status = std::process::Command::new("/usr/bin/sudo")
        .args(["-n", "/usr/libexec/justverify-restart-core"])
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .status()?;
    if !status.success() {
        bail!("Core restart helper failed");
    }
    let rpc = crate::Rpc::new(profile.rpc_port, &profile.cookie)?;
    let deadline = Instant::now() + Duration::from_secs(20);
    while Instant::now() < deadline {
        if let Ok(v) = rpc.call("getblockchaininfo", json!([])) {
            if v["chain"] != profile.network {
                bail!("restarted Core network mismatch");
            }
            let values = policy.current_effective(&profile.managed_config)?;
            crate::policy::verify_observable(&values, &rpc.call("getmempoolinfo", json!([]))?)?;
            crate::policy::verify_network_observable(
                &values,
                &rpc.call("getnetworkinfo", json!([]))?,
            )?;
            crate::policy::verify_resources(
                &values,
                &profile.cookie.with_file_name("debug.log"),
                &rpc.call("getnettotals", json!([]))?,
            )?;
            crate::policy::verify_auxiliary(
                &values,
                &rpc.call("getnetworkinfo", json!([]))?,
                &rpc.call("getindexinfo", json!([]))?,
                &profile.cookie.with_file_name("debug.log"),
                profile.rpc_port,
            )?;
            crate::policy::verify_incoming_process(
                &values,
                &profile.network,
                &profile.binary,
                profile.p2p_backend_port,
            )?;
            return Ok(());
        }
        std::thread::sleep(Duration::from_millis(200));
    }
    bail!("Core did not become healthy after restart")
}
pub fn serve(profile_file: &Path, socket: &Path) -> Result<()> {
    let bytes = fs::read(profile_file)?;
    let profile: Profile = serde_json::from_slice(&bytes)?;
    let catalog: Value = serde_json::from_slice(&fs::read(profile.catalog.join("releases.json"))?)?;
    let release = catalog["releases"]
        .as_array()
        .context("bad release catalog")?
        .iter()
        .find(|v| v["version"] == profile.version)
        .context("unknown selected release")?;
    if format!("{:x}", Sha256::digest(fs::read(&profile.binary)?))
        != release["arm64_binary_sha256"]
            .as_str()
            .context("no verified executable hash")?
    {
        bail!("selected Core binary does not match verified ARM artifact");
    }
    let policy = Policy::load(&profile.catalog, &profile.version, &profile.network)?;
    for dir in [
        &profile.staging,
        profile
            .managed_config
            .parent()
            .context("missing config directory")?,
        socket.parent().context("missing socket directory")?,
    ] {
        if !dir.exists() {
            fs::create_dir_all(dir)?;
            fs::set_permissions(dir, fs::Permissions::from_mode(0o700))?;
        }
        if fs::metadata(dir)?.permissions().mode() & 0o077 != 0 {
            bail!("administrative state and sockets must be private");
        }
    }
    if socket.exists() {
        bail!("administrative socket already exists");
    }
    let listener = UnixListener::bind(socket)?;
    fs::set_permissions(socket, fs::Permissions::from_mode(0o600))?;
    let mut pending: BTreeMap<String, (Plan, Preflight, Instant)> = BTreeMap::new();
    for stream in listener.incoming() {
        let mut stream = stream?;
        stream.set_read_timeout(Some(Duration::from_secs(2)))?;
        stream.set_write_timeout(Some(Duration::from_secs(4)))?;
        let result = (|| -> Result<Value> {
            if fs::read(profile_file)? != bytes {
                bail!("active profile changed; restart administrative service");
            }
            let mut request = String::new();
            BufReader::new(stream.try_clone()?)
                .take(32768)
                .read_line(&mut request)?;
            if !request.ends_with('\n') {
                bail!("request too long or unterminated");
            }
            let command = match parse_request(&request)? {
                Request::PreviewConfig { config } => Request::Preview {
                    values: policy.config_values(&profile.managed_config, &config)?,
                },
                other => other,
            };
            pending.retain(|_, (_, _, time)| time.elapsed() < Duration::from_secs(300));
            match command {
                Request::State => Ok(
                    json!({"version":profile.version,"network":profile.network,"requested":policy.current(&profile.managed_config)?,"entries":policy.entries(),"config":policy.config_text(&profile.managed_config)?,"transaction":crate::policy::transaction_status(&profile.managed_config)?}),
                ),
                Request::Preview { values } => {
                    if profile.p2p_backend_port.is_none()
                        && values.get("maxuploadtarget").is_some_and(|v| v != "0")
                    {
                        bail!(
                            "finite upload limits require the dedicated electrs download backend; refresh the node profile first"
                        )
                    }
                    if pending.len() >= 8 {
                        bail!("too many pending previews; wait for expiry");
                    }
                    let plan = policy.preview(&profile.managed_config, values)?;
                    let receipt = policy.preflight(&profile.binary, &profile.staging, &plan)?;
                    let mut random = [0u8; 24];
                    fs::File::open("/dev/urandom")?.read_exact(&mut random)?;
                    let token = random
                        .iter()
                        .map(|b| format!("{b:02x}"))
                        .collect::<String>();
                    let response = json!({"token":token,"plan":plan,"preflight":receipt});
                    pending.insert(token, (plan, receipt, Instant::now()));
                    Ok(response)
                }
                Request::Apply { token } => {
                    let _operation = crate::version_service::operation_lock()?;
                    let (plan, receipt, _) = pending
                        .remove(&token)
                        .context("preview missing or expired")?;
                    Ok(serde_json::to_value(policy.apply(
                        &profile.managed_config,
                        &plan,
                        &receipt,
                        || restart(&profile, &policy),
                    )?)?)
                }
                Request::PreviewConfig { .. } => unreachable!(),
                Request::Recover => {
                    let _operation = crate::version_service::operation_lock()?;
                    Ok(serde_json::to_value(policy.recover(
                        &profile.managed_config,
                        &profile.binary,
                        || restart(&profile, &policy),
                    )?)?)
                }
            }
        })();
        let response = match result {
            Ok(value) => json!({"ok":true,"result":value}),
            Err(e) => json!({"ok":false,"error":crate::clean(&e.to_string())}),
        };
        let _ = stream.write_all(&serde_json::to_vec(&response)?);
    }
    Ok(())
}

fn parse_request(text: &str) -> Result<Request> {
    let value: Value = serde_json::from_str(text)?;
    let object = value.as_object().context("API request must be an object")?;
    let allowed: &[&str] = match value["method"].as_str() {
        Some("state" | "recover") => &["method"],
        Some("preview") => &["method", "values"],
        Some("preview_config") => &["method", "config"],
        Some("apply") => &["method", "token"],
        _ => bail!("unknown administrative method"),
    };
    if object.keys().any(|key| !allowed.contains(&key.as_str())) {
        bail!("unknown administrative request field");
    }
    Ok(serde_json::from_value(value)?)
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn rejects_fields_on_unit_requests() {
        assert!(parse_request(r#"{"method":"state","command":"/bin/sh"}"#).is_err());
        assert!(parse_request(r#"{"method":"recover","binary":"/bin/sh"}"#).is_err());
        assert!(parse_request(r#"{"method":"state"}"#).is_ok());
    }
}
