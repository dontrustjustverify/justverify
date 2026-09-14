use anyhow::Result;
use justverify::policy::{Policy, Values};
use sha2::{Digest, Sha256};
use std::{fs, os::unix::fs::PermissionsExt, path::PathBuf};

#[test]
#[ignore = "Real verified Linux Core binaries required: JV_CORE_MATRIX"]
fn real_outgoing_options_preflight_and_roundtrip() -> Result<()> {
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let binaries = PathBuf::from(std::env::var("JV_CORE_MATRIX")?);
    let state = root
        .join(".state")
        .join(format!("outgoing-preflight-{}", std::process::id()));
    fs::create_dir_all(&state)?;
    fs::set_permissions(&state, fs::Permissions::from_mode(0o700))?;
    let releases: serde_json::Value =
        serde_json::from_slice(&fs::read(root.join("catalog/releases.json"))?)?;
    let mut tested = 0;
    for release in releases["releases"].as_array().unwrap() {
        if release["verification"] != "PASS" {
            continue;
        }
        let version = release["version"].as_str().unwrap();
        let policy = Policy::load(&root.join("catalog"), version, "regtest")?;
        let binary = binaries
            .join(version)
            .join(format!("bitcoin-{version}/bin/bitcoind"));
        assert_eq!(
            format!("{:x}", Sha256::digest(fs::read(&binary)?)),
            release["arm64_binary_sha256"].as_str().unwrap()
        );
        let file = state.join(format!("{version}.conf"));
        for (networks, proxy) in [
            ("ipv4,ipv6", "0"),
            ("onion", "0"),
            ("ipv4,ipv6,onion", "1"),
            ("i2p", "0"),
            ("i2p,onion", "0"),
            ("i2p,ipv4,ipv6,onion", "1"),
        ] {
            let values = Values::from([
                ("onlynet".into(), networks.into()),
                ("proxy".into(), proxy.into()),
            ]);
            let plan = policy.preview(&file, values)?;
            let receipt = policy.preflight(&binary, &state, &plan)?;
            println!("{version} {networks} proxy={proxy}: {}", receipt.networks);
            policy.apply(&file, &plan, &receipt, || Ok(()))?;
            let current = policy.current(&file)?;
            assert_eq!(current["onlynet"], networks);
            assert_eq!(current["proxy"], proxy);
        }
        tested += 1;
    }
    assert_eq!(tested, 32);
    // apply callback here tests only atomic file roundtrip; actual systemd
    // restart/transport acceptance is tested separately in the registered VM.
    Ok(())
}
