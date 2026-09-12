//! Background official download and signed-artifact installation; no service restart.
use anyhow::{Context, Result, bail};
use serde_json::{Value, json};
use std::{
    fs,
    io::Write,
    path::{Path, PathBuf},
    process::{Command, Stdio},
    sync::{Arc, Mutex},
    time::{Duration, Instant},
};
pub struct Downloads {
    status: Arc<Mutex<Value>>,
    state: PathBuf,
}
impl Downloads {
    pub fn new(state: &Path) -> Result<Self> {
        let path = state.join("download-status.json");
        let mut value = if path.exists() {
            serde_json::from_slice::<Value>(&fs::read(&path)?)?
        } else {
            json!({"phase":"idle"})
        };
        if matches!(value["phase"].as_str(), Some("downloading" | "installing")) {
            value["phase"] = json!("interrupted");
            crate::policy::atomic(&path, &serde_json::to_vec_pretty(&value)?)?;
        }
        Ok(Self {
            status: Arc::new(Mutex::new(value)),
            state: state.into(),
        })
    }
    pub fn status(&self) -> Value {
        self.status.lock().unwrap().clone()
    }
    pub fn start(&self, catalog: &Path, version: &str) -> Result<Value> {
        let manifest: Value = serde_json::from_slice(&fs::read(catalog.join("releases.json"))?)?;
        let release = manifest["releases"]
            .as_array()
            .context("bad catalog")?
            .iter()
            .find(|r| r["version"] == version)
            .context("unknown version")?;
        if release["availability"] != "OFFICIAL_BINARY_VERIFIED" {
            bail!("upstream artifact is unavailable or unverified");
        }
        let mut status = self.status.lock().unwrap();
        if matches!(status["phase"].as_str(), Some("downloading" | "installing")) {
            bail!("another download is running");
        }
        let initial = json!({"version":version,"phase":"downloading"});
        crate::policy::atomic(
            &self.state.join("download-status.json"),
            &serde_json::to_vec_pretty(&initial)?,
        )?;
        *status = initial.clone();
        drop(status);
        let shared = Arc::clone(&self.status);
        let state = self.state.clone();
        let version = version.to_owned();
        std::thread::spawn(move || {
            let publish = |phase: &str| -> Result<()> {
                let value = json!({"version":version,"phase":phase});
                crate::policy::atomic(
                    &state.join("download-status.json"),
                    &serde_json::to_vec_pretty(&value)?,
                )?;
                *shared.lock().unwrap() = value;
                Ok(())
            };
            let outcome = (|| -> Result<()> {
                let log = fs::OpenOptions::new()
                    .create(true)
                    .append(true)
                    .open(state.join("download.log"))?;
                let mut process = Command::new("/usr/bin/python3")
                    .args([
                        "-I",
                        "/opt/justverify/scripts/fetch_core.py",
                        &version,
                        "aarch64-linux-gnu",
                        "--cache-root",
                        "/var/lib/justverify/downloads",
                        "--evidence-dir",
                        "/var/lib/justverify/downloads/evidence",
                    ])
                    .stdout(log.try_clone()?)
                    .stderr(log)
                    .spawn()?;
                let deadline = Instant::now() + Duration::from_secs(600);
                let result = loop {
                    if let Some(status) = process.try_wait()? {
                        break status;
                    }
                    if Instant::now() > deadline {
                        process.kill()?;
                        process.wait()?;
                        bail!("official download deadline exceeded");
                    }
                    std::thread::sleep(Duration::from_millis(250));
                };
                if !result.success() {
                    bail!("official signature/checksum download failed");
                }
                publish("installing")?;
                let _lock = crate::version_service::operation_lock()?;
                let mut child = Command::new("/usr/bin/sudo")
                    .args(["-n", "/usr/libexec/justverify-install-core"])
                    .stdin(Stdio::piped())
                    .stdout(Stdio::null())
                    .stderr(Stdio::null())
                    .spawn()?;
                child
                    .stdin
                    .take()
                    .unwrap()
                    .write_all(&serde_json::to_vec(&json!({"version":version}))?)?;
                if !child.wait()?.success() {
                    bail!("verified binary installation failed");
                }
                Ok(())
            })();
            let phase = if outcome.is_ok() {
                "complete"
            } else {
                "failed"
            };
            if publish(phase).is_err() {
                *shared.lock().unwrap() =
                    json!({"version":version,"phase":"failed","error":"status persistence failed"});
            }
        });
        Ok(initial)
    }
}
