use anyhow::{Context, Result};
use justverify::policy::{Policy, installation_defaults};
use sha2::{Digest, Sha256};
use std::{fs, os::unix::fs::PermissionsExt, path::PathBuf};

#[test]
fn fresh_defaults_and_legacy_choices_are_distinct() -> Result<()> {
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let state = root
        .join(".state")
        .join(format!("peer-defaults-{}", std::process::id()));
    fs::create_dir_all(&state)?;
    fs::set_permissions(&state, fs::Permissions::from_mode(0o700))?;
    let releases: serde_json::Value =
        serde_json::from_slice(&fs::read(root.join("catalog/releases.json"))?)?;
    for release in releases["releases"].as_array().unwrap() {
        if release["verification"] != "PASS" {
            continue;
        }
        for network in release["networks"].as_array().unwrap() {
            let policy = Policy::load(
                &root.join("catalog"),
                release["version"].as_str().unwrap(),
                network.as_str().unwrap(),
            )?;
            let file = state.join("managed.conf");
            let text = policy.installation_config()?;
            assert!(text.contains("# JustVerify incoming=none\n"));
            assert!(text.contains("i2psam=127.0.0.1:7656\ni2pacceptincoming=0\n"));
            assert!(!text.contains("=onion\n") || text.contains("onlynet=onion\n"));
            assert!(!text.contains("bind=0.0.0.0:") && !text.contains("bind=[::]:"));
            assert!(
                !text
                    .lines()
                    .any(|s| s.starts_with("bind=") && s.ends_with("=onion"))
            );
            fs::write(&file, &text)?;
            assert_eq!(
                policy.current(&file).context("fresh profile roundtrip")?,
                installation_defaults()
            );
            let entries = policy.entries();
            for key in ["listen", "onlynet"] {
                let entry = entries.iter().find(|e| e["key"] == key).unwrap();
                assert_eq!(entry["installation_default"], installation_defaults()[key]);
            }
            for old in [
                "datacarrier=0\ntxindex=1\n",
                "onlynet=onion\n",
                "onlynet=ipv4\n",
            ] {
                fs::write(&file, old)?;
                let values = policy.current(&file)?;
                policy.preview(&file, values.clone())?;
                assert_eq!(fs::read_to_string(&file)?, old);
                assert_eq!(
                    values.get("onlynet").map(String::as_str),
                    if old.contains("onlynet=onion") {
                        Some("onion")
                    } else if old.contains("onlynet=ipv4") {
                        Some("ipv4")
                    } else {
                        None
                    }
                );
            }
        }
    }
    fs::remove_dir_all(state)?;
    Ok(())
}

#[test]
#[ignore = "Real verified Linux Core binaries required: JV_CORE_MATRIX"]
fn real_new_network_defaults_preflight() -> Result<()> {
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let binaries = PathBuf::from(std::env::var("JV_CORE_MATRIX")?);
    let state = root
        .join(".state")
        .join(format!("peer-defaults-live-{}", std::process::id()));
    fs::create_dir_all(&state)?;
    fs::set_permissions(&state, fs::Permissions::from_mode(0o700))?;
    let releases: serde_json::Value =
        serde_json::from_slice(&fs::read(root.join("catalog/releases.json"))?)?;
    let mut count = 0;
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
        let plan = policy.preview(&file, installation_defaults())?;
        let receipt = policy.preflight(&binary, &state, &plan)?;
        policy.apply(&file, &plan, &receipt, || Ok(()))?;
        assert_eq!(
            policy.current(&file).context("fresh profile roundtrip")?,
            installation_defaults()
        );
        println!("{version}: actual isolated startup/RPC/listeners and saved defaults PASS");
        count += 1;
    }
    assert_eq!(count, 32);
    Ok(())
}
