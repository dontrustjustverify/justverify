//! Conservative data isolation: an unverified version never opens another version's state.
use anyhow::{Context, Result, bail};
use serde::{Deserialize, Serialize};
use std::{
    fs::{self, OpenOptions},
    io::Write,
    os::unix::fs::{OpenOptionsExt, PermissionsExt},
    path::{Path, PathBuf},
};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Instance {
    #[serde(default, skip_serializing_if = "is_false")]
    pub watch_only: bool,
    pub core_version: String,
    pub network: String,
    pub electrs_version: String,
    pub core_data: PathBuf,
    pub electrs_data: PathBuf,
}

fn is_false(value: &bool) -> bool {
    !*value
}

fn valid_version(v: &str) -> bool {
    let parts: Vec<_> = v.split('.').collect();
    (2..=3).contains(&parts.len())
        && parts
            .iter()
            .all(|p| !p.is_empty() && p.bytes().all(|c| c.is_ascii_digit()))
}

pub fn instance(root: &Path, version: &str, network: &str, electrs: &str) -> Result<Instance> {
    instance_mode(root, version, network, electrs, false)
}
pub fn instance_mode(
    root: &Path,
    version: &str,
    network: &str,
    electrs: &str,
    watch_only: bool,
) -> Result<Instance> {
    if !valid_version(version) || !valid_version(electrs) {
        bail!("invalid version");
    }
    if !matches!(network, "main" | "test" | "testnet4" | "signet" | "regtest") {
        bail!("invalid network");
    }
    let releases: serde_json::Value =
        serde_json::from_str(include_str!("../catalog/releases.json"))?;
    let release = releases["releases"]
        .as_array()
        .context("invalid release catalog")?
        .iter()
        .find(|r| r["version"] == version)
        .context("unknown Core release")?;
    if release["availability"] != "OFFICIAL_BINARY_VERIFIED" {
        bail!("release unavailable: official binary missing or verification incomplete");
    }
    if !release["networks"]
        .as_array()
        .context("missing network support")?
        .iter()
        .any(|n| n == network)
    {
        bail!("network unsupported by this Core release");
    }
    if release["electrs"]["version"] != electrs || release["electrs"]["status"] != "PASS" {
        bail!("unverified Core/electrs combination");
    }
    let canonical = root
        .canonicalize()
        .context("private instance root must exist")?;
    if fs::metadata(&canonical)?.permissions().mode() & 0o077 != 0 {
        bail!("private instance root required");
    }
    let directory = if watch_only {
        format!("{version}-watch-only")
    } else {
        version.to_owned()
    };
    let folder = canonical.join(network).join(&directory);
    // Reject symlink paths even if the link happens to point inside the root.
    let mut component = canonical.clone();
    for part in [network, directory.as_str()] {
        component.push(part);
        if fs::symlink_metadata(&component).is_ok_and(|m| m.file_type().is_symlink()) {
            bail!("symlink instance path rejected");
        }
    }
    Ok(Instance {
        watch_only,
        core_version: version.into(),
        network: network.into(),
        electrs_version: electrs.into(),
        core_data: folder.join("core"),
        electrs_data: folder.join(format!("electrs-{electrs}")),
    })
}

pub fn prepare(target: &Instance) -> Result<()> {
    let folder = target
        .core_data
        .parent()
        .context("instance parent missing")?;
    let marker = folder.join("instance.json");
    if folder.exists() {
        if fs::symlink_metadata(folder)?.file_type().is_symlink() {
            bail!("symlink instance rejected");
        }
        let existing: Instance =
            serde_json::from_slice(&fs::read(&marker).context("unmarked existing data refused")?)?;
        if &existing != target {
            bail!("data compatibility not verified; create a separate instance");
        }
        for path in [&target.core_data, &target.electrs_data] {
            if fs::symlink_metadata(path)?.file_type().is_symlink() {
                bail!("linked data refused");
            }
        }
        return Ok(());
    }
    fs::create_dir_all(folder.parent().context("missing network parent")?)?;
    fs::create_dir(folder)?;
    fs::set_permissions(folder, fs::Permissions::from_mode(0o700))?;
    fs::create_dir(&target.core_data)?;
    fs::create_dir(&target.electrs_data)?;
    let mut file = OpenOptions::new()
        .write(true)
        .create_new(true)
        .mode(0o600)
        .open(&marker)?;
    file.write_all(&serde_json::to_vec_pretty(target)?)?;
    file.sync_all()?;
    fs::File::open(folder)?.sync_all()?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    fn root() -> PathBuf {
        let p = std::env::temp_dir().join(format!(
            "jv-data-test-{}-{}",
            std::process::id(),
            crate::now()
        ));
        fs::create_dir(&p).unwrap();
        fs::set_permissions(&p, fs::Permissions::from_mode(0o700)).unwrap();
        p
    }
    #[test]
    fn cross_version_data_isolation_and_existing_data_guard() {
        let r = root();
        let a = instance(&r, "31.1", "regtest", "0.11.1").unwrap();
        prepare(&a).unwrap();
        fs::write(a.core_data.join("sentinel"), b"preserve").unwrap();
        let b = instance(&r, "22.0", "regtest", "0.11.1").unwrap();
        prepare(&b).unwrap();
        assert_ne!(a.core_data, b.core_data);
        assert_eq!(fs::read(a.core_data.join("sentinel")).unwrap(), b"preserve");
        let mut forged = b.clone();
        forged.core_version = "31.1".into();
        assert!(prepare(&forged).is_err());
        assert!(instance(&r, "../22.0", "regtest", "0.11.1").is_err());
        let unmarked = instance(&r, "23.0", "regtest", "0.11.1").unwrap();
        fs::create_dir(unmarked.core_data.parent().unwrap()).unwrap();
        assert!(prepare(&unmarked).is_err());
        let linked = instance(&r, "24.0", "regtest", "0.11.1").unwrap();
        std::os::unix::fs::symlink(
            a.core_data.parent().unwrap(),
            linked.core_data.parent().unwrap(),
        )
        .unwrap();
        assert!(instance(&r, "24.0", "regtest", "0.11.1").is_err());
        fs::remove_dir_all(r).unwrap();
    }
}
