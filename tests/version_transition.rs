use anyhow::{Context, Result, bail};
use justverify::{
    Rpc,
    versions::{Runtime, Selection, Versions},
};
use serde_json::{Value, json};
use std::{
    fs,
    io::{BufRead, BufReader, Write},
    net::{TcpListener, TcpStream},
    os::unix::fs::PermissionsExt,
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    time::{Duration, Instant},
};
struct Services {
    core: Option<Child>,
    indexer: Option<Child>,
    active: Option<Selection>,
    rpc_port: u16,
    p2p_port: u16,
    electrum_port: u16,
    electrs: PathBuf,
    fail_version: Option<String>,
    fresh_start_heights: Vec<u64>,
    pause_marker: Option<PathBuf>,
}
fn port() -> u16 {
    TcpListener::bind("127.0.0.1:0")
        .unwrap()
        .local_addr()
        .unwrap()
        .port()
}
impl Services {
    fn rpc(&self) -> Rpc {
        Rpc::new(
            self.rpc_port,
            &self
                .active
                .as_ref()
                .unwrap()
                .instance
                .core_data
                .join("regtest/.cookie"),
        )
        .unwrap()
    }
    fn headers(&self) -> Result<u64> {
        let mut stream = TcpStream::connect(("127.0.0.1", self.electrum_port))?;
        stream.set_read_timeout(Some(Duration::from_secs(2)))?;
        stream
            .write_all(b"{\"id\":1,\"method\":\"blockchain.headers.subscribe\",\"params\":[]}\n")?;
        let mut line = String::new();
        BufReader::new(stream).read_line(&mut line)?;
        let reply: Value = serde_json::from_str(&line)?;
        reply["result"]["height"]
            .as_u64()
            .context("missing Electrum height")
    }
    fn finish(child: &mut Option<Child>) -> Result<()> {
        if let Some(mut process) = child.take() {
            let end = Instant::now() + Duration::from_secs(10);
            while process.try_wait()?.is_none() {
                if Instant::now() > end {
                    process.kill()?;
                    bail!("service did not stop gracefully");
                }
                std::thread::sleep(Duration::from_millis(50));
            }
            process.wait()?;
        }
        Ok(())
    }
}
impl Runtime for Services {
    fn stop(&mut self) -> Result<()> {
        if let Some(indexer) = &self.indexer {
            Command::new("kill")
                .args(["-TERM", &indexer.id().to_string()])
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .status()?;
        }
        Self::finish(&mut self.indexer)?;
        if self.core.is_some() {
            let _ = self.rpc().call("stop", json!([]));
        }
        Self::finish(&mut self.core)?;
        Ok(())
    }
    fn start_and_check(&mut self, selection: &Selection) -> Result<()> {
        if selection.instance.core_version == "22.0" {
            if let Some(marker) = &self.pause_marker {
                fs::write(marker, b"selection persisted and previous services stopped")?;
                loop {
                    std::thread::park();
                }
            }
        }
        self.active = Some(selection.clone());
        if !selection.policy_file.exists() {
            fs::write(&selection.policy_file, "")?;
        }
        let log = fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(selection.instance.core_data.join("transition-test.log"))?;
        let mut command = Command::new(&selection.binary);
        command.args([
            format!("-datadir={}", selection.instance.core_data.display()),
            format!("-conf={}", selection.policy_file.display()),
            format!("-rpcport={}", self.rpc_port),
            format!("-port={}", self.p2p_port),
            "-regtest".into(),
            "-server".into(),
            format!(
                "-disablewallet={}",
                if selection.instance.watch_only { 0 } else { 1 }
            ),
            "-connect=0".into(),
            "-listen=1".into(),
            format!("-bind=127.0.0.1:{}", self.p2p_port),
            "-printtoconsole=0".into(),
        ]);
        if self.fail_version.as_deref() == Some(&selection.instance.core_version) {
            command.arg("-justverify-invalid-start=1");
        }
        self.core = Some(command.stdout(log.try_clone()?).stderr(log).spawn()?);
        let end = Instant::now() + Duration::from_secs(15);
        let mut height = loop {
            if self.core.as_mut().unwrap().try_wait()?.is_some() {
                bail!("actual selected Core startup failed");
            }
            if let Ok(info) = self.rpc().call("getblockchaininfo", json!([])) {
                assert_eq!(info["chain"], "regtest");
                break info["blocks"].as_u64().unwrap();
            }
            if Instant::now() > end {
                bail!("Core readiness timeout");
            }
            std::thread::sleep(Duration::from_millis(50));
        };
        // Establish a real synchronized regtest fixture before testing index readiness.
        // The observed empty height proves that the older version did not reuse prior data.
        if height == 0 {
            self.fresh_start_heights.push(height);
            let descriptor =
                self.rpc().call("getdescriptorinfo", json!(["raw(51)"]))?["descriptor"]
                    .as_str()
                    .unwrap()
                    .to_owned();
            self.rpc()
                .call("generatetodescriptor", json!([1, descriptor]))?;
            height = 1;
        }
        let log = fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(selection.instance.electrs_data.join("transition-test.log"))?;
        self.indexer = Some(
            Command::new(&self.electrs)
                .args([
                    "--skip-default-conf-files".into(),
                    "--network=regtest".into(),
                    format!("--daemon-dir={}", selection.instance.core_data.display()),
                    format!(
                        "--cookie-file={}",
                        selection
                            .instance
                            .core_data
                            .join("regtest/.cookie")
                            .display()
                    ),
                    format!("--db-dir={}", selection.instance.electrs_data.display()),
                    format!("--daemon-rpc-addr=127.0.0.1:{}", self.rpc_port),
                    format!("--daemon-p2p-addr=127.0.0.1:{}", self.p2p_port),
                    format!("--electrum-rpc-addr=127.0.0.1:{}", self.electrum_port),
                    "--monitoring-addr=127.0.0.1:0".into(),
                    "--no-auto-reindex".into(),
                    "--log-filters=INFO".into(),
                ])
                .stdout(log.try_clone()?)
                .stderr(log)
                .spawn()?,
        );
        let end = Instant::now() + Duration::from_secs(20);
        loop {
            if self.indexer.as_mut().unwrap().try_wait()?.is_some() {
                bail!("actual electrs startup failed");
            }
            if self.headers().is_ok_and(|h| h == height) {
                return Ok(());
            }
            if Instant::now() > end {
                bail!("electrs readiness timeout");
            }
            std::thread::sleep(Duration::from_millis(100));
        }
    }
}
impl Drop for Services {
    fn drop(&mut self) {
        let _ = self.stop();
    }
}
fn private(path: &Path) {
    fs::create_dir_all(path).unwrap();
    fs::set_permissions(path, fs::Permissions::from_mode(0o700)).unwrap();
}
#[test]
#[ignore = "Explicit real Linux Core/electrs version transition; JV_CORE_MATRIX and JV_ELECTRS_BIN required"]
fn actual_version_switch_preserves_data_and_recovers_failure() -> Result<()> {
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let crash_child = std::env::var("JV_VERSION_CRASH_WORK").ok();
    let work = crash_child.as_ref().map(PathBuf::from).unwrap_or_else(|| {
        root.join(".state")
            .join(format!("version-transition-{}", std::process::id()))
    });
    private(&work);
    private(&work.join("data"));
    private(&work.join("control"));
    let versions = Versions::new(
        &root.join("catalog"),
        &PathBuf::from(std::env::var("JV_CORE_MATRIX")?),
        &work.join("data"),
        &work.join("control"),
    )?;
    let mut services = Services {
        core: None,
        indexer: None,
        active: None,
        rpc_port: port(),
        p2p_port: port(),
        electrum_port: port(),
        electrs: PathBuf::from(std::env::var("JV_ELECTRS_BIN")?),
        fail_version: None,
        fresh_start_heights: Vec::new(),
        pause_marker: None,
    };
    let first = versions.preview("31.1", "regtest")?;
    assert!(!first.existing_instance);
    assert_eq!(versions.apply(first, &mut services)?.phase, "committed");
    let previous = versions.active()?.unwrap();
    let descriptor = services
        .rpc()
        .call("getdescriptorinfo", json!(["raw(51)"]))?["descriptor"]
        .as_str()
        .unwrap()
        .to_owned();
    services
        .rpc()
        .call("generatetodescriptor", json!([3, descriptor]))?;
    assert_eq!(services.rpc().call("getblockcount", json!([]))?, 4);
    if crash_child.is_some() {
        services.pause_marker = Some(work.join("crash-ready"));
        versions.apply(versions.preview("22.0", "regtest")?, &mut services)?;
        bail!("crash child must be terminated by parent");
    }
    let down = versions.preview("22.0", "regtest")?;
    assert_ne!(down.target.instance.core_data, previous.instance.core_data);
    assert_ne!(
        down.target.instance.electrs_data,
        previous.instance.electrs_data
    );
    assert_eq!(versions.apply(down, &mut services)?.phase, "committed");
    assert_eq!(services.fresh_start_heights, vec![0, 0]);
    assert_eq!(services.rpc().call("getblockcount", json!([]))?, 1);
    let up = versions.preview("31.1", "regtest")?;
    assert!(up.existing_instance);
    assert_eq!(versions.apply(up, &mut services)?.phase, "committed");
    assert_eq!(services.rpc().call("getblockcount", json!([]))?, 4);
    assert_eq!(services.headers()?, 4);
    let wallet = versions.preview_mode("31.1", "regtest", true)?;
    assert_ne!(
        wallet.target.instance.core_data,
        previous.instance.core_data
    );
    assert_ne!(
        wallet.target.instance.electrs_data,
        previous.instance.electrs_data
    );
    assert_eq!(versions.apply(wallet, &mut services)?.phase, "committed");
    services.rpc().call("createwallet", json!({"wallet_name":"profile-test","disable_private_keys":true,"blank":true,"descriptors":true,"load_on_startup":true}))?;
    assert_eq!(
        services.rpc().call("getwalletinfo", json!([]))?["private_keys_enabled"],
        false
    );
    assert_eq!(
        versions
            .apply(versions.preview("31.1", "regtest")?, &mut services)?
            .phase,
        "committed"
    );
    assert_eq!(services.rpc().call("getblockcount", json!([]))?, 4);
    assert!(services.rpc().call("listwallets", json!([])).is_err());
    assert_eq!(
        versions
            .apply(
                versions.preview_mode("31.1", "regtest", true)?,
                &mut services
            )?
            .phase,
        "committed"
    );
    assert_eq!(
        services.rpc().call("listwallets", json!([]))?,
        json!(["profile-test"])
    );
    assert_eq!(
        versions
            .apply(versions.preview("31.1", "regtest")?, &mut services)?
            .phase,
        "committed"
    );
    let fail = versions.preview("22.0", "regtest")?;
    services.fail_version = Some("22.0".into());
    assert_eq!(versions.apply(fail, &mut services)?.phase, "rolled_back");
    assert_eq!(versions.active()?.unwrap(), previous);
    assert_eq!(services.rpc().call("getblockcount", json!([]))?, 4);
    assert_eq!(services.headers()?, 4);
    assert!(versions.preview("30.0", "regtest").is_err());
    assert!(versions.preview("22.0", "testnet4").is_err());
    services.stop()?;
    // A missing data directory must never be silently replaced with an empty chain.
    let folder = previous.instance.core_data.parent().unwrap();
    let missing = folder.with_extension("missing-test");
    fs::rename(folder, &missing)?;
    assert!(versions.active().is_err());
    assert!(!folder.exists());
    fs::rename(&missing, folder)?;
    // Replacing the root simulates a mount disappearing and an underlying directory appearing.
    fs::rename(work.join("data"), work.join("data-held"))?;
    private(&work.join("data"));
    assert!(versions.active().is_err());
    fs::remove_dir(work.join("data"))?;
    fs::rename(work.join("data-held"), work.join("data"))?;
    assert_eq!(versions.active()?.unwrap(), previous);
    let crash_work = work.join("crash");
    let shadow = work.join("crash-binaries");
    private(&shadow);
    for version in ["31.1", "22.0"] {
        std::os::unix::fs::symlink(
            PathBuf::from(std::env::var("JV_CORE_MATRIX")?).join(version),
            shadow.join(version),
        )?;
    }
    let mut child = Command::new(std::env::current_exe()?)
        .args([
            "--exact",
            "actual_version_switch_preserves_data_and_recovers_failure",
            "--ignored",
            "--nocapture",
        ])
        .env("JV_VERSION_CRASH_WORK", &crash_work)
        .env("JV_CORE_MATRIX", &shadow)
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()?;
    let deadline = Instant::now() + Duration::from_secs(40);
    while !crash_work.join("crash-ready").exists() {
        if child.try_wait()?.is_some() {
            bail!("version crash child exited before checkpoint");
        }
        if Instant::now() > deadline {
            child.kill()?;
            child.wait()?;
            bail!("version crash checkpoint timeout");
        }
        std::thread::sleep(Duration::from_millis(50));
    }
    child.kill()?;
    child.wait()?;
    let recovering = Versions::new(
        &root.join("catalog"),
        &shadow,
        &crash_work.join("data"),
        &crash_work.join("control"),
    )?;
    assert_eq!(recovering.active()?.unwrap().instance.core_version, "22.0");
    fs::remove_file(shadow.join("22.0"))?;
    services.fail_version = None;
    assert_eq!(recovering.recover(&mut services)?.phase, "rolled_back");
    assert_eq!(recovering.active()?.unwrap().instance.core_version, "31.1");
    assert_eq!(services.rpc().call("getblockcount", json!([]))?, 4);
    assert_eq!(services.headers()?, 4);
    services.stop()?;
    let report = json!({"status":"PASS","checks":["real Core31.1/electrs initial startup","real isolated downgrade to22.0","old Core gets fresh chain and separate index","return to31.1 preserves generated blocks and index","actual target startup failure restores previous separate data profile","withdrawn version and unsupported network rejected","missing active data refuses empty replacement","changed data root refuses fallback writes","actual transition process SIGKILL after selection write","recovery restores previous Core and electrs data after process death","missing target binary does not prevent restoring verified prior binary"],"limitations":["native service bridge and TUI not yet connected"]});
    fs::write(
        root.join("version-transition-result.json"),
        serde_json::to_vec_pretty(&report)?,
    )?;
    fs::remove_dir_all(work)?;
    Ok(())
}
