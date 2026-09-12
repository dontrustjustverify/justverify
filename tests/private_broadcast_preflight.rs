use anyhow::Result;
use justverify::policy::{Policy, Values};
use sha2::{Digest, Sha256};
use std::{fs, os::unix::fs::PermissionsExt, path::PathBuf};

#[test]
#[ignore = "Real verified Linux Core binaries required: JV_CORE_MATRIX"]
fn real_private_broadcast_isolated_preflight() -> Result<()> {
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let binaries = PathBuf::from(std::env::var("JV_CORE_MATRIX")?);
    let state = root.join(".state").join(format!(
        "private-broadcast-preflight-{}",
        std::process::id()
    ));
    fs::create_dir_all(&state)?;
    fs::set_permissions(&state, fs::Permissions::from_mode(0o700))?;
    let releases: serde_json::Value =
        serde_json::from_slice(&fs::read(root.join("catalog/releases.json"))?)?;
    let version = "31.1";
    let release = releases["releases"]
        .as_array()
        .unwrap()
        .iter()
        .find(|r| r["version"] == version)
        .unwrap();
    let binary = binaries
        .join(version)
        .join(format!("bitcoin-{version}/bin/bitcoind"));
    assert_eq!(
        format!("{:x}", Sha256::digest(fs::read(&binary)?)),
        release["arm64_binary_sha256"].as_str().unwrap()
    );
    for network in ["main", "testnet4", "signet"] {
        let policy = Policy::load(&root.join("catalog"), version, network)?;
        let file = state.join(format!("{network}.conf"));
        let plan = policy.preview(
            &file,
            Values::from([("privatebroadcast".into(), "1".into())]),
        )?;
        policy.preflight(&binary, &state, &plan)?;
        println!(
            "31.1 {network}: privatebroadcast startup PASS with networking disabled; transport NOT TESTED"
        );
    }
    Ok(())
}
