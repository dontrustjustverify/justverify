use justverify::policy::{Policy, Values, installation_defaults};
use std::path::Path;
fn policy(version: &str) -> Policy {
    Policy::load(
        &Path::new(env!("CARGO_MANIFEST_DIR")).join("catalog"),
        version,
        "regtest",
    )
    .unwrap()
}
#[test]
fn native_editor_converts_fees_and_rejects_unmanaged_or_ambiguous_input() {
    let p = policy("31.1");
    let dir = std::env::temp_dir().join(format!("jv-config-editor-{}", std::process::id()));
    std::fs::create_dir(&dir).unwrap();
    let file = dir.join("managed.conf");
    std::fs::write(&file, "txindex=1\n").unwrap();
    let values = p.config_values(&file, "# comment\n minrelaytxfee = 0.000001 # BTC/kvB\ndatacarrier=0\ndatacarriersize=83\ndebug=mempool\ndebug=mempoolrej\n").unwrap();
    assert_eq!(values["minrelaytxfee"], "0.1");
    assert_eq!(values["debug"], "mempool,mempoolrej");
    assert_eq!(values["datacarrier"], "0");
    assert!(!values.contains_key("txindex"));
    for text in [
        "rpcbind=0.0.0.0",
        "includeconf=other.conf",
        "blocknotify=echo hi",
        "datadir=/tmp/new",
        "[main]\ndbcache=450",
        "txindex=1\ntxindex=0",
        "listen=0",
        "onlynet=ipv4",
        "maxorphantx=100",
        "debug=unknown",
        "debug=mempool\ndebug=mempool",
        "debug=0\ndebug=mempool",
        "debugexclude=0",
        "datacarrier=0\u{1b}",
    ] {
        assert!(p.config_values(&file, text).is_err(), "accepted {text}");
    }
    std::fs::remove_dir_all(dir).unwrap();
}
#[test]
fn defaults_and_legacy_preferences_follow_version_semantics() {
    for version in ["22.0", "29.0", "30.2", "31.1"] {
        let p = policy(version);
        assert_eq!(
            p.validate(&installation_defaults()).unwrap()["datacarrier"],
            "0"
        );
        assert_eq!(
            p.validate(&installation_defaults()).unwrap()["datacarriersize"],
            "83"
        );
        let legacy = Values::from([("legacy_maxorphantx".into(), "120".into())]);
        let native = Values::from([("maxorphantx".into(), "120".into())]);
        let modern = version.starts_with("30.") || version.starts_with("31.");
        assert_eq!(p.validate(&legacy).is_ok(), modern);
        assert_eq!(p.validate(&native).is_ok(), !modern);
    }
}

#[test]
#[ignore = "Real verified Linux Core matrix required: JV_CORE_MATRIX"]
fn real_defaults_native_editor_and_legacy_roundtrip_all_releases() -> anyhow::Result<()> {
    use sha2::{Digest, Sha256};
    use std::{fs, os::unix::fs::PermissionsExt, path::PathBuf};
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let binaries = PathBuf::from(std::env::var("JV_CORE_MATRIX")?);
    let state = root
        .join(".state")
        .join(format!("config-editor-live-{}", std::process::id()));
    fs::create_dir_all(&state)?;
    fs::set_permissions(&state, fs::Permissions::from_mode(0o700))?;
    let releases: serde_json::Value =
        serde_json::from_slice(&fs::read(root.join("catalog/releases.json"))?)?;
    let mut results = Vec::new();
    for release in releases["releases"].as_array().unwrap() {
        if release["verification"] != "PASS" {
            continue;
        }
        let version = release["version"].as_str().unwrap();
        let p = policy(version);
        let binary = binaries
            .join(version)
            .join(format!("bitcoin-{version}/bin/bitcoind"));
        assert_eq!(
            format!("{:x}", Sha256::digest(fs::read(&binary)?)),
            release["arm64_binary_sha256"].as_str().unwrap()
        );
        let file = state.join(format!("{version}.conf"));
        let mut values = installation_defaults();
        values.insert("debug".into(), "mempool,mempoolrej".into());
        let modern = version.split('.').next().unwrap().parse::<u32>()? >= 30;
        values.insert(
            if modern {
                "legacy_maxorphantx"
            } else {
                "maxorphantx"
            }
            .into(),
            "120".into(),
        );
        let plan = p.preview(&file, values.clone())?;
        let receipt = p.preflight(&binary, &state, &plan)?;
        p.apply(&file, &plan, &receipt, || Ok(()))?;
        assert_eq!(p.current(&file)?, values);
        if modern {
            assert!(
                !fs::read_to_string(&file)?
                    .lines()
                    .any(|l| l.starts_with("maxorphantx="))
            );
        }
        let text = p
            .config_text(&file)?
            .replace("datacarrier=0", "datacarrier=1");
        let updated = p.config_values(&file, &text)?;
        let on_plan = p.preview(&file, updated.clone())?;
        let on_receipt = p.preflight(&binary, &state, &on_plan)?;
        p.apply(&file, &on_plan, &on_receipt, || Ok(()))?;
        assert_eq!(p.current(&file)?, updated);
        if modern {
            assert_eq!(on_receipt.observed["maxdatacarriersize"], 83);
        }
        results.push(serde_json::json!({"version":version,"status":"PASS","source_sha256":release["arm64_binary_sha256"],"startup_cases":2,"legacy_preference_only":modern}));
        fs::write(
            root.join("config-editor-matrix-result.json"),
            serde_json::to_vec_pretty(&results)?,
        )?;
        println!(
            "{version}: defaults off/83, native editor on/83, diagnostic categories and orphan semantics PASS"
        );
    }
    assert_eq!(results.len(), 32);
    Ok(())
}
