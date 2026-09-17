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
    guard_path: PathBuf,
    fail_stop: bool,
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
    fn guard(&mut self, blocked: bool) -> Result<()> {
        if blocked {
            fs::write(&self.guard_path, b"startup inhibited")?;
        } else if self.guard_path.exists() {
            fs::remove_file(&self.guard_path)?;
        }
        Ok(())
    }
    fn stop(&mut self) -> Result<()> {
        if self.fail_stop {
            bail!("injected service shutdown failure");
        }
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
#[ignore = "Real isolated Linux Core/electrs required; JV_CORE_MATRIX and JV_ELECTRS_BIN"]
fn actual_version_reset_and_recovery() -> Result<()> {
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let work = PathBuf::from(format!("/var/tmp/jv-version-reset-{}", std::process::id()));
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
        fail_stop: false,
        guard_path: work.join("guard"),
        fresh_start_heights: Vec::new(),
        pause_marker: None,
    };
    let first = versions.preview("31.1", "regtest")?;
    assert!(!first.destructive);
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
    let chain = previous.instance.core_data.join("regtest");
    let preserved = [
        chain.join("rpc-auth-fixture"),
        chain.join("i2p_private_key"),
        previous.instance.core_data.join("device-settings-fixture"),
    ];
    for path in &preserved {
        fs::write(path, b"fixture-preserve")?;
    }
    // Historical target-version data and an unrelated network stay untouched.
    let historical =
        justverify::storage::instance(&work.join("data"), "22.0", "regtest", "0.11.1")?;
    justverify::storage::prepare(&historical)?;
    fs::write(
        historical.core_data.join("old-chain-fixture"),
        b"historical-preserve",
    )?;
    let unrelated = work.join("data/signet");
    private(&unrelated);
    fs::write(unrelated.join("sentinel"), b"other-network")?;
    assert!(versions.preview("31.1", "regtest").is_err());
    assert!(versions.preview("22.0", "testnet4").is_err());
    assert!(versions.preview_mode("22.0", "regtest", true).is_err());
    assert!(versions.preview("30.0", "regtest").is_err());
    let cancelled = versions.preview("22.0", "regtest")?;
    assert!(cancelled.destructive);
    assert_eq!(
        cancelled.target.instance.core_data,
        previous.instance.core_data
    );
    assert_eq!(
        cancelled.target.instance.electrs_data,
        previous.instance.electrs_data
    );
    drop(cancelled);
    assert_eq!(services.rpc().call("getblockcount", json!([]))?, 4);
    fs::write(chain.join("wallet.dat"), b"wallet-preserve")?;
    assert!(versions.preview("22.0", "regtest").is_err());
    assert_eq!(fs::read(chain.join("wallet.dat"))?, b"wallet-preserve");
    fs::remove_file(chain.join("wallet.dat"))?;
    let stale = versions.preview("22.0", "regtest")?;
    let policy = fs::read(&previous.policy_file)?;
    fs::write(
        &previous.policy_file,
        b"datacarrier=1\ndatacarriersize=83\ntxindex=1\n",
    )?;
    assert!(versions.apply(stale, &mut services).is_err());
    assert_eq!(services.rpc().call("getblockcount", json!([]))?, 4);
    fs::write(&previous.policy_file, &policy)?;
    // Actual shutdown failure stops the transaction before the first deletion.
    let fail_stop = versions.preview("22.0", "regtest")?;
    services.fail_stop = true;
    assert_eq!(
        versions.apply(fail_stop, &mut services)?.phase,
        "stop_failed"
    );
    assert_eq!(services.rpc().call("getblockcount", json!([]))?, 4);
    services.fail_stop = false;
    assert_eq!(versions.recover(&mut services)?.phase, "rolled_back");
    assert_eq!(services.rpc().call("getblockcount", json!([]))?, 4);
    assert_eq!(
        versions
            .apply(versions.preview("22.0", "regtest")?, &mut services)?
            .phase,
        "committed"
    );
    assert_eq!(services.rpc().call("getblockcount", json!([]))?, 1);
    assert_eq!(services.headers()?, 1);
    assert_eq!(
        versions.active()?.unwrap().instance.core_data,
        previous.instance.core_data
    );
    assert_eq!(
        versions
            .apply(versions.preview("31.1", "regtest")?, &mut services)?
            .phase,
        "committed"
    );
    assert_eq!(services.rpc().call("getblockcount", json!([]))?, 1);
    assert_eq!(services.headers()?, 1);
    assert_eq!(services.fresh_start_heights, vec![0, 0, 0]);
    let watch = versions.preview_mode("31.1", "regtest", true)?;
    assert!(!watch.destructive);
    assert_eq!(versions.apply(watch, &mut services)?.phase, "committed");
    services.rpc().call("createwallet",json!({"wallet_name":"watch-fixture","disable_private_keys":true,"blank":true,"descriptors":true,"load_on_startup":true}))?;
    assert_eq!(
        services.rpc().call("getwalletinfo", json!([]))?["private_keys_enabled"],
        false
    );
    let watch_path = versions.active()?.unwrap().instance.core_data;
    assert!(versions.preview_mode("22.0", "regtest", true).is_err());
    assert_eq!(
        services.rpc().call("listwallets", json!([]))?,
        json!(["watch-fixture"])
    );
    assert_eq!(
        versions
            .apply(versions.preview("31.1", "regtest")?, &mut services)?
            .phase,
        "committed"
    );
    assert_eq!(services.rpc().call("getblockcount", json!([]))?, 1);
    assert!(
        watch_path
            .join("regtest/wallets/watch-fixture/wallet.dat")
            .is_file()
    );
    let fail = versions.preview("22.0", "regtest")?;
    services.fail_version = Some("22.0".into());
    assert_eq!(
        versions.apply(fail, &mut services)?.phase,
        "target_start_failed"
    );
    assert_eq!(versions.active()?.unwrap().instance.core_version, "22.0");
    assert!(services.guard_path.exists());
    services.fail_version = None;
    assert_eq!(versions.recover(&mut services)?.phase, "committed");
    assert_eq!(services.rpc().call("getblockcount", json!([]))?, 1);
    assert!(!services.guard_path.exists());
    for path in &preserved {
        assert_eq!(fs::read(path)?, b"fixture-preserve");
    }
    assert_eq!(
        fs::read(historical.core_data.join("old-chain-fixture"))?,
        b"historical-preserve"
    );
    assert_eq!(fs::read(unrelated.join("sentinel"))?, b"other-network");
    services.stop()?;
    // Symlinks and a replaced volume are rejected before active profile use.
    fs::rename(work.join("data"), work.join("data-held"))?;
    private(&work.join("data"));
    assert!(versions.active().is_err());
    fs::remove_dir(work.join("data"))?;
    fs::rename(work.join("data-held"), work.join("data"))?;
    let bad = chain.join("mempool.dat");
    if bad.exists() {
        fs::remove_file(&bad)?;
    }
    std::os::unix::fs::symlink(unrelated.join("sentinel"), &bad)?;
    assert!(versions.preview("31.1", "regtest").is_err());
    fs::remove_file(bad)?;
    fs::write(
        root.join("version-reset-result.json"),
        serde_json::to_vec_pretty(
            &json!({"status":"PASS","checks":["actual Core31.1/electrs startup","31.1 to22.0 to31.1 fresh genesis every time at identical paths","historical target and other network preserved","cancel/same/withdrawn/network/mode refusals do not delete","wallet data blocks before deletion","stale policy refuses deletion","actual live services survive injected shutdown failure","actual target Core startup failure never rolls back old binary","retry starts verified target and rebuilds electrs","auth/identity/device fixtures preserved","replaced root and linked chain file rejected"]}),
        )?,
    )?;
    fs::remove_dir_all(work)?;
    Ok(())
}

#[test]
#[ignore = "Full pinned Linux Core/electrs matrix; isolated regtest only"]
fn actual_version_reset_catalog_matrix() -> Result<()> {
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let work = PathBuf::from(format!("/var/tmp/jv-reset-matrix-{}", std::process::id()));
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
        fail_stop: false,
        guard_path: work.join("guard"),
        fresh_start_heights: Vec::new(),
        pause_marker: None,
    };
    assert_eq!(
        versions
            .apply(versions.preview("31.1", "regtest")?, &mut services)?
            .phase,
        "committed"
    );
    let original = versions.active()?.unwrap().instance;
    let catalog: Value = serde_json::from_slice(&fs::read(root.join("catalog/releases.json"))?)?;
    let mut tested = Vec::new();
    for release in catalog["releases"].as_array().unwrap() {
        if release["availability"] != "OFFICIAL_BINARY_VERIFIED" {
            continue;
        }
        let version = release["version"].as_str().unwrap();
        if versions.active()?.unwrap().instance.core_version == version {
            continue;
        }
        assert_eq!(
            versions
                .apply(versions.preview(version, "regtest")?, &mut services)?
                .phase,
            "committed"
        );
        let actual = versions.active()?.unwrap().instance;
        assert_eq!(actual.core_data, original.core_data);
        assert_eq!(actual.electrs_data, original.electrs_data);
        assert_eq!(services.rpc().call("getblockcount", json!([]))?, 1);
        assert_eq!(services.headers()?, 1);
        tested.push(version.to_string());
        println!("PASS Core {version}: fresh chain, retained paths, actual electrs index");
    }
    assert_eq!(services.fresh_start_heights.len(), tested.len() + 1);
    services.stop()?;
    fs::write(
        root.join("version-reset-matrix-result.json"),
        serde_json::to_vec_pretty(
            &json!({"status":"PASS","network":"regtest","versions":tested,"electrs":"0.11.1","every_start_observed_genesis":true,"same_paths":true}),
        )?,
    )?;
    fs::remove_dir_all(work)?;
    Ok(())
}
