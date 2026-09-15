use anyhow::{Context, Result, bail};
use justverify::{
    Rpc,
    policy::{Policy, Values},
};
use serde_json::json;
use std::{
    fs,
    os::unix::fs::PermissionsExt,
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    time::{Duration, Instant},
};
struct Node {
    child: Option<Child>,
    binary: PathBuf,
    data: PathBuf,
    config: PathBuf,
    port: u16,
}
impl Node {
    fn rpc(&self) -> Rpc {
        Rpc::new(self.port, &self.data.join("regtest/.cookie")).unwrap()
    }
    fn stop(&mut self) {
        if let Some(mut p) = self.child.take() {
            let _ = self.rpc().call("stop", json!([]));
            let end = Instant::now() + Duration::from_secs(10);
            while p.try_wait().ok().flatten().is_none() {
                if Instant::now() > end {
                    let _ = p.kill();
                    break;
                }
                std::thread::sleep(Duration::from_millis(50));
            }
            let _ = p.wait();
        }
    }
    fn start(&mut self, fail: bool) -> Result<()> {
        self.stop();
        let log = fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(self.data.join("test-startup.log"))?;
        let mut c = Command::new(&self.binary);
        c.args([
            format!("-datadir={}", self.data.display()),
            format!("-conf={}", self.config.display()),
            format!("-rpcport={}", self.port),
            "-regtest".into(),
            "-server".into(),
            "-disablewallet".into(),
            "-connect=0".into(),
            "-listen=0".into(),
            "-printtoconsole=0".into(),
        ]);
        if fail {
            c.arg("-justverify-invalid-startup-option=1");
        }
        self.child = Some(
            c.stdout(Stdio::from(log.try_clone()?))
                .stderr(log)
                .spawn()?,
        );
        let end = Instant::now() + Duration::from_secs(10);
        loop {
            if self.child.as_mut().unwrap().try_wait()?.is_some() {
                bail!("actual Core startup failed");
            }
            if self.rpc().call("getblockchaininfo", json!([])).is_ok() {
                return Ok(());
            }
            if Instant::now() > end {
                bail!("startup timeout");
            }
            std::thread::sleep(Duration::from_millis(50));
        }
    }
}
impl Drop for Node {
    fn drop(&mut self) {
        self.stop();
    }
}
fn private(path: &Path) {
    fs::create_dir_all(path).unwrap();
    fs::set_permissions(path, fs::Permissions::from_mode(0o700)).unwrap();
}
#[test]
#[ignore = "Run explicitly with JV_CORE_BIN pointing to a signature-verified Core 31.1 binary"]
fn real_policy_apply_and_rollback() -> Result<()> {
    if let Ok(folder) = std::env::var("JV_POLICY_CRASH_CHILD") {
        let state = PathBuf::from(folder);
        let binary = PathBuf::from(std::env::var("JV_CORE_BIN")?);
        let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        let policy = Policy::load(&root.join("catalog"), "31.1", "regtest")?;
        let path = state.join("managed.conf");
        let mut values = policy.current(&path)?;
        values.insert("maxmempool".into(), "520".into());
        let plan = policy.preview(&path, values)?;
        let receipt = policy.preflight(&binary, &state.join("stage"), &plan)?;
        policy.apply(&path, &plan, &receipt, || {
            fs::write(state.join("crash-ready"), b"configuration persisted")?;
            loop {
                std::thread::park();
            }
        })?;
        bail!("crash worker must be killed by parent");
    }
    let binary = PathBuf::from(std::env::var("JV_CORE_BIN").context("JV_CORE_BIN required")?);
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let state = root
        .join(".state")
        .join(format!("policy-integration-{}", std::process::id()));
    private(&state);
    private(&state.join("stage"));
    private(&state.join("data"));
    let path = state.join("managed.conf");
    fs::write(&path, "")?;
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let port = listener.local_addr()?.port();
    drop(listener);
    let mut node = Node {
        child: None,
        binary: binary.clone(),
        data: state.join("data"),
        config: path.clone(),
        port,
    };
    node.start(false)?;
    let p = Policy::load(&root.join("catalog"), "31.1", "regtest")?;
    let values = Values::from([
        ("maxmempool".into(), "420".into()),
        ("minrelaytxfee".into(), "0.5".into()),
        ("datacarriersize".into(), "40".into()),
    ]);
    let plan = p.preview(&path, values.clone())?;
    let receipt = p.preflight(&binary, &state.join("stage"), &plan)?;
    assert_eq!(receipt.observed["maxmempool"], 420_000_000);
    assert_eq!(receipt.observed["maxdatacarriersize"], 40);
    let result = p.apply(&path, &plan, &receipt, || node.start(false))?;
    assert_eq!(result.phase, "committed");
    let info = node.rpc().call("getmempoolinfo", json!([]))?;
    assert_eq!(info["maxmempool"], 420_000_000);
    assert_eq!(info["minrelaytxfee"], json!(0.000005));
    // A second submission of a stale plan must not restart or overwrite the node.
    assert!(
        p.apply(&path, &plan, &receipt, || bail!(
            "must never restart stale preview"
        ))
        .is_err()
    );
    let mut next = values.clone();
    next.insert("maxmempool".into(), "500".into());
    let plan2 = p.preview(&path, next)?;
    let receipt2 = p.preflight(&binary, &state.join("stage"), &plan2)?;
    let mut starts = 0;
    let rolled = p.apply(&path, &plan2, &receipt2, || {
        starts += 1;
        node.start(starts == 1)
    })?;
    assert_eq!(rolled.phase, "rolled_back");
    assert_eq!(starts, 2);
    assert_eq!(
        node.rpc().call("getmempoolinfo", json!([]))?["maxmempool"],
        420_000_000
    );
    assert!(
        p.validate(&Values::from([("maxorphantx".into(), "100".into())]))
            .is_err()
    );
    assert!(
        p.validate(&Values::from([("limitancestorcount".into(), "25".into())]))
            .is_err()
    );
    assert!(
        p.validate(&Values::from([(
            "minrelaytxfee".into(),
            "1\nserver=0".into()
        )]))
        .is_err()
    );
    assert!(
        p.validate(&Values::from([("limitclustercount".into(), "65".into())]))
            .is_err()
    );
    assert!(
        p.validate(&Values::from([("maxmempool".into(), "1".into())]))
            .is_err()
    );
    // Kill a separate administrator process after durable write but before restart.
    let mut worker = Command::new(std::env::current_exe()?)
        .args([
            "--exact",
            "real_policy_apply_and_rollback",
            "--ignored",
            "--nocapture",
        ])
        .env("JV_POLICY_CRASH_CHILD", &state)
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()?;
    let deadline = Instant::now() + Duration::from_secs(30);
    while !state.join("crash-ready").exists() {
        if worker.try_wait()?.is_some() {
            bail!("crash worker exited early");
        }
        if Instant::now() > deadline {
            let _ = worker.kill();
            bail!("crash worker timeout");
        }
        std::thread::sleep(Duration::from_millis(50));
    }
    worker.kill()?;
    worker.wait()?;
    let journal: serde_json::Value =
        serde_json::from_slice(&fs::read(path.with_extension("transaction.json"))?)?;
    assert_eq!(journal["phase"], "restarting");
    assert!(
        p.recover(&path, &std::env::current_exe()?, || bail!(
            "wrong binary recovery must be refused"
        ))
        .is_err()
    );
    let recovered = p.recover(&path, &binary, || node.start(false))?;
    assert_eq!(recovered.phase, "rolled_back");
    assert_eq!(
        node.rpc().call("getmempoolinfo", json!([]))?["maxmempool"],
        420_000_000
    );
    let report = json!({"status":"PASS","core":"31.1","checks":["actual isolated preflight startup","exact fee conversion applied","maxmempool/datacarriersize observed via RPC","atomic managed config save","stale preview rejection","real startup failure followed by prior configuration recovery","removed and wallet-only policies rejected","input injection rejected","range conflict rejected","actual administrator process killed after config write","unfinished journal retained","cross-binary recovery rejected","prior config recovered after process crash"],"limitations":["not all policy behaviors","this test covers the library; Linux API/TUI evidence is recorded separately"]});
    fs::write(
        root.join("docs/evidence/policy-integration.json"),
        serde_json::to_vec_pretty(&report)?,
    )?;
    node.stop();
    fs::remove_dir_all(state)?;
    Ok(())
}

#[test]
#[ignore = "Run explicitly with JV_CORE_BIN pointing to signature-verified Core 31.1"]
fn real_native_editor_restart_and_failed_start_recovery() -> Result<()> {
    let binary = PathBuf::from(std::env::var("JV_CORE_BIN")?);
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let state = root
        .join(".state")
        .join(format!("native-editor-{}", std::process::id()));
    private(&state);
    private(&state.join("stage"));
    private(&state.join("data"));
    let file = state.join("managed.conf");
    fs::write(&file, "")?;
    let listener = std::net::TcpListener::bind("127.0.0.1:0")?;
    let port = listener.local_addr()?.port();
    drop(listener);
    let mut node = Node {
        child: None,
        binary: binary.clone(),
        data: state.join("data"),
        config: file.clone(),
        port,
    };
    node.start(false)?;
    let p = Policy::load(&root.join("catalog"), "31.1", "regtest")?;
    let text = "datacarrier=0\ndatacarriersize=83\nmaxmempool=333\nminrelaytxfee=0.000001\ndebug=mempoolrej\n";
    let mut values = p.config_values(&file, text)?;
    values.insert("legacy_maxorphantx".into(), "123".into());
    let plan = p.preview(&file, values.clone())?;
    let receipt = p.preflight(&binary, &state.join("stage"), &plan)?;
    assert_eq!(
        p.apply(&file, &plan, &receipt, || node.start(false))?.phase,
        "committed"
    );
    assert_eq!(
        node.rpc().call("getmempoolinfo", json!([]))?["maxmempool"],
        333_000_000
    );
    assert_eq!(
        node.rpc().call("getmempoolinfo", json!([]))?["maxdatacarriersize"],
        0
    );
    assert_eq!(p.current(&file)?, values);
    assert!(
        !fs::read_to_string(&file)?
            .lines()
            .any(|l| l.starts_with("maxorphantx="))
    );
    let edited = p
        .config_text(&file)?
        .replace("datacarrier=0", "datacarrier=1")
        .replace("maxmempool=333", "maxmempool=444");
    let plan = p.preview(&file, p.config_values(&file, &edited)?)?;
    let receipt = p.preflight(&binary, &state.join("stage"), &plan)?;
    let mut starts = 0;
    let rolled = p.apply(&file, &plan, &receipt, || {
        starts += 1;
        node.start(starts == 1)
    })?;
    assert_eq!(rolled.phase, "rolled_back");
    assert_eq!(starts, 2);
    assert_eq!(p.current(&file)?, values);
    assert_eq!(
        node.rpc().call("getmempoolinfo", json!([]))?["maxdatacarriersize"],
        0
    );
    let plan = p.preview(&file, p.config_values(&file, &edited)?)?;
    let receipt = p.preflight(&binary, &state.join("stage"), &plan)?;
    assert_eq!(
        p.apply(&file, &plan, &receipt, || node.start(false))?.phase,
        "committed"
    );
    assert_eq!(
        node.rpc().call("getmempoolinfo", json!([]))?["maxdatacarriersize"],
        83
    );
    assert_eq!(p.current(&file)?["legacy_maxorphantx"], "123");
    node.stop();
    println!(
        "PASS native editor: actual Core restart, fee/size RPC, legacy preference only, real failed start and recovery"
    );
    Ok(())
}
