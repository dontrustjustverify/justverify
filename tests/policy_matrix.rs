use anyhow::Result;
use justverify::policy::{Policy, Values};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::{fs, os::unix::fs::PermissionsExt, path::PathBuf};

#[test]
#[ignore = "Explicit Linux ARM matrix; JV_CORE_MATRIX points to verified extracted releases"]
fn real_common_policy_preflight_all_supported_releases() -> Result<()> {
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let binaries = PathBuf::from(std::env::var("JV_CORE_MATRIX")?);
    let catalog = root.join("catalog");
    let manifest: Value = serde_json::from_slice(&fs::read(catalog.join("releases.json"))?)?;
    let state = root
        .join(".state")
        .join(format!("policy-matrix-{}", std::process::id()));
    fs::create_dir_all(&state)?;
    fs::set_permissions(&state, fs::Permissions::from_mode(0o700))?;
    let mut results = Vec::new();
    for release in manifest["releases"].as_array().unwrap() {
        let version = release["version"].as_str().unwrap();
        if release["verification"] != "PASS" {
            results.push(json!({"version":version,"status":release["verification"],"scope":"upstream artifact unavailable; not omitted"}));
            continue;
        }
        let binary = binaries
            .join(version)
            .join(format!("bitcoin-{version}/bin/bitcoind"));
        assert_eq!(
            format!("{:x}", Sha256::digest(fs::read(&binary)?)),
            release["arm64_binary_sha256"].as_str().unwrap()
        );
        let policy = Policy::load(&catalog, version, "regtest")?;
        let values = Values::from([
            ("maxmempool".into(), "420".into()),
            ("minrelaytxfee".into(), "0.501".into()),
            ("incrementalrelayfee".into(), "0.5".into()),
            ("dustrelayfee".into(), "3".into()),
            ("mempoolexpiry".into(), "123".into()),
            ("persistmempool".into(), "1".into()),
            ("datacarrier".into(), "1".into()),
            ("datacarriersize".into(), "42".into()),
        ]);
        let plan = policy.preview(&state.join(format!("{version}.conf")), values)?;
        let receipt = policy.preflight(&binary, &state, &plan)?;
        assert_eq!(receipt.observed["maxmempool"], 420_000_000);
        assert_eq!(receipt.observed["minrelaytxfee"], json!(0.00000501));
        let result = json!({"version":version,"status":"PASS","binary_sha256":release["arm64_binary_sha256"],"scope":"real isolated regtest startup with eight common settings; RPC maxmempool/minrelaytxfee checked","receipt":receipt});
        println!("Core {version}: common policy preflight PASS");
        results.push(result);
        fs::write(
            root.join("policy-matrix-result.json"),
            serde_json::to_vec_pretty(&results)?,
        )?;
    }
    assert_eq!(results.iter().filter(|v| v["status"] == "PASS").count(), 32);
    fs::remove_dir_all(state)?;
    Ok(())
}
