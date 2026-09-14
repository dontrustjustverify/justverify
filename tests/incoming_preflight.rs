use anyhow::Result;
use justverify::policy::{Policy, Values};
use sha2::{Digest, Sha256};
use std::{fs, os::unix::fs::PermissionsExt, path::PathBuf};

#[test]
#[ignore = "Real verified Linux Core binaries required: JV_CORE_MATRIX"]
fn real_incoming_options_preflight_and_roundtrip() -> Result<()> {
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let binaries = PathBuf::from(std::env::var("JV_CORE_MATRIX")?);
    let state = root
        .join(".state")
        .join(format!("incoming-preflight-{}", std::process::id()));
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
        for incoming in [
            "none",
            "clearnet",
            "tor",
            "clearnet,tor",
            "i2p",
            "clearnet,i2p",
            "i2p,tor",
            "clearnet,i2p,tor",
        ] {
            let mut values = Values::from([("listen".into(), incoming.into())]);
            if version.starts_with("22.") && incoming.split(',').any(|n| n == "i2p") {
                assert!(
                    policy.validate(&values).is_err(),
                    "Core22 incoming-only must be rejected, not silently enabled for outbound"
                );
                values.insert("onlynet".into(), "i2p,ipv4,ipv6,onion".into());
            }
            let plan = policy.preview(&file, values)?;
            let receipt = policy.preflight(&binary, &state, &plan)?;
            policy.apply(&file, &plan, &receipt, || Ok(()))?;
            assert_eq!(policy.current(&file)?["listen"], incoming);
            println!("{version} incoming={incoming}: startup/listeners/file-roundtrip PASS");
        }
        tested += 1;
    }
    assert_eq!(tested, 32);
    // apply callback here tests only atomic file roundtrip; actual systemd
    // restart/transport acceptance is tested separately in the registered VM.
    Ok(())
}
