//! Version transitions preserve each version's data and policy. No in-place downgrade.
use crate::{
    policy::Policy,
    storage::{Instance, instance_mode, prepare},
};
use anyhow::{Context, Result, bail};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::{
    fs::{self, OpenOptions},
    os::unix::fs::{MetadataExt, OpenOptionsExt, PermissionsExt},
    path::{Path, PathBuf},
};
fn hash(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
#[serde(deny_unknown_fields)]
pub struct Selection {
    pub instance: Instance,
    pub binary: PathBuf,
    pub binary_sha256: String,
    pub policy_file: PathBuf,
}
#[derive(Serialize)]
pub struct Preview {
    pub previous: Option<Selection>,
    pub target: Selection,
    pub existing_instance: bool,
    pub explanation: String,
    revision: String,
    policy_revision: String,
}
#[derive(Serialize, Deserialize)]
pub struct Journal {
    pub phase: String,
    pub previous: Option<Selection>,
    pub target: Selection,
    pub error: Option<String>,
}
/// Implementations stop both Core/electrs; start must verify their actual network,
/// version and readiness. A failed start may leave children, so stop is called again.
pub trait Runtime {
    fn stop(&mut self) -> Result<()>;
    fn start_and_check(&mut self, selection: &Selection) -> Result<()>;
}
pub struct Versions {
    catalog: PathBuf,
    binaries: PathBuf,
    data: PathBuf,
    state: PathBuf,
    data_identity: (u64, u64),
}
impl Versions {
    pub fn new(catalog: &Path, binaries: &Path, data: &Path, state: &Path) -> Result<Self> {
        for path in [data, state] {
            let m = fs::symlink_metadata(path)?;
            if !m.is_dir() || m.file_type().is_symlink() || m.permissions().mode() & 0o077 != 0 {
                bail!("version state and data roots must be private real directories");
            }
        }
        Ok(Self {
            catalog: catalog.canonicalize()?,
            binaries: binaries.canonicalize()?,
            data: data.canonicalize()?,
            state: state.canonicalize()?,
            data_identity: (fs::metadata(data)?.dev(), fs::metadata(data)?.ino()),
        })
    }
    fn selection(&self, version: &str, network: &str, watch_only: bool) -> Result<Selection> {
        let metadata = fs::symlink_metadata(&self.data)?;
        if metadata.file_type().is_symlink()
            || (metadata.dev(), metadata.ino()) != self.data_identity
        {
            bail!("data root changed or mount disappeared; refusing system-disk fallback");
        }
        let target = instance_mode(&self.data, version, network, "0.11.1", watch_only)?;
        let binary = self
            .binaries
            .join(version)
            .join(format!("bitcoin-{version}/bin/bitcoind"));
        let manifest: Value =
            serde_json::from_slice(&fs::read(self.catalog.join("releases.json"))?)?;
        let release = manifest["releases"]
            .as_array()
            .context("bad catalog")?
            .iter()
            .find(|v| v["version"] == version)
            .context("unknown version")?;
        let digest =
            hash(&fs::read(&binary).context("selected verified binary must be downloaded first")?);
        if release["arm64_binary_sha256"] != digest {
            bail!("version artifact hash mismatch");
        }
        let policy_file = target.core_data.parent().unwrap().join("managed.conf");
        Ok(Selection {
            instance: target,
            binary,
            binary_sha256: digest,
            policy_file,
        })
    }
    fn validate_selection(&self, selection: &Selection, allow_new: bool) -> Result<()> {
        if &self.selection(
            &selection.instance.core_version,
            &selection.instance.network,
            selection.instance.watch_only,
        )? != selection
        {
            bail!("selection paths or verified artifact changed");
        }
        if !allow_new && !selection.instance.core_data.parent().unwrap().exists() {
            bail!("previously selected data directory is missing; refusing empty replacement");
        }
        prepare(&selection.instance)?;
        Ok(())
    }
    fn active_bytes(&self) -> Result<Vec<u8>> {
        match fs::read(self.state.join("active.json")) {
            Ok(bytes) => Ok(bytes),
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(Vec::new()),
            Err(e) => Err(e.into()),
        }
    }
    pub fn active(&self) -> Result<Option<Selection>> {
        let bytes = self.active_bytes()?;
        if bytes.is_empty() {
            return Ok(None);
        }
        let active: Selection = serde_json::from_slice(&bytes)?;
        self.validate_selection(&active, false)?;
        Ok(Some(active))
    }
    pub fn recovery_status(&self) -> Result<Value> {
        let path = self.state.join("transition.json");
        if !path.exists() {
            return Ok(serde_json::json!({"needs_recovery":false,"phase":"none"}));
        }
        let journal: Journal = serde_json::from_slice(&fs::read(path)?)?;
        Ok(
            serde_json::json!({"needs_recovery":self.unfinished()?,"phase":journal.phase,"previous":journal.previous,"target":journal.target,"error":journal.error}),
        )
    }
    pub fn preview(&self, version: &str, network: &str) -> Result<Preview> {
        self.preview_mode(version, network, false)
    }
    pub fn preview_mode(&self, version: &str, network: &str, watch_only: bool) -> Result<Preview> {
        let previous = self.active()?;
        let target = self.selection(version, network, watch_only)?;
        let existing_instance = target.instance.core_data.parent().unwrap().exists();
        if existing_instance {
            prepare(&target.instance)?;
        }
        if previous.as_ref() == Some(&target) {
            bail!("version and network already selected");
        }
        for selection in previous.iter().chain(std::iter::once(&target)) {
            if crate::policy::transaction_status(&selection.policy_file)?["needs_recovery"] == true
            {
                bail!("finish interrupted policy recovery before changing versions");
            }
        }
        let policy = Policy::load(&self.catalog, version, network)?;
        let mut values = policy.current(&target.policy_file)?;
        if !target.policy_file.exists() {
            // New installations include the local mempool explorer. Existing
            // profiles retain their explicit index choice and chain data.
            values.insert("txindex".into(), "1".into());
        }
        let plan = policy.preview(&target.policy_file, values)?;
        // A new binary is exercised on fresh private data before any active service is stopped.
        policy.preflight(&target.binary, &self.state, &plan)?;
        Ok(Preview { previous,target,existing_instance,revision:hash(&self.active_bytes()?),policy_revision:plan.revision,
            explanation:if existing_instance {"Resume this exact version's separate Core data and electrs index; active data is preserved."}else{"Start a fresh version/network/wallet-mode-specific Core data directory and electrs index, with txindex=1 for the included mempool explorer. Existing chain data is preserved. Initial synchronization and additional disk space are required."}.into() })
    }
    fn persist<T: Serialize>(&self, name: &str, value: &T) -> Result<()> {
        crate::policy::atomic(&self.state.join(name), &serde_json::to_vec_pretty(value)?)
    }
    fn lock(&self) -> Result<fs::File> {
        let file = OpenOptions::new()
            .create(true)
            .truncate(false)
            .read(true)
            .write(true)
            .mode(0o600)
            .open(self.state.join("transition.lock"))?;
        file.lock()?;
        Ok(file)
    }
    fn unfinished(&self) -> Result<bool> {
        let path = self.state.join("transition.json");
        if !path.exists() {
            return Ok(false);
        }
        let journal: Journal = serde_json::from_slice(&fs::read(path)?)?;
        Ok(!matches!(
            journal.phase.as_str(),
            "committed" | "rolled_back" | "stop_failed"
        ))
    }
    pub fn apply(&self, preview: Preview, runtime: &mut impl Runtime) -> Result<Journal> {
        let _lock = self.lock()?;
        if self.unfinished()? {
            bail!("unfinished version transition requires recovery");
        }
        if hash(&self.active_bytes()?) != preview.revision || self.active()? != preview.previous {
            bail!("stale version preview");
        }
        self.validate_selection(&preview.target, true)?;
        let new_policy = !preview.target.policy_file.exists();
        if new_policy {
            crate::policy::atomic(&preview.target.policy_file, b"")?;
        }
        let policy = Policy::load(
            &self.catalog,
            &preview.target.instance.core_version,
            &preview.target.instance.network,
        )?;
        if policy
            .preview(
                &preview.target.policy_file,
                policy.current(&preview.target.policy_file)?,
            )?
            .revision
            != preview.policy_revision
        {
            bail!("target policy changed after preflight");
        }
        for selection in preview
            .previous
            .iter()
            .chain(std::iter::once(&preview.target))
        {
            if crate::policy::transaction_status(&selection.policy_file)?["needs_recovery"] == true
            {
                bail!("policy recovery is pending; version switch refused");
            }
        }
        if new_policy {
            crate::policy::atomic(&preview.target.policy_file, b"txindex=1\n")?;
        }
        let mut journal = Journal {
            phase: "stopping".into(),
            previous: preview.previous,
            target: preview.target,
            error: None,
        };
        self.persist("transition.json", &journal)?;
        if runtime.stop().is_err() {
            journal.phase = "stop_failed".into();
            journal.error = Some("services did not stop; active selection was not changed".into());
            self.persist("transition.json", &journal)?;
            return Ok(journal);
        }
        journal.phase = "starting".into();
        self.persist("transition.json", &journal)?;
        self.persist("active.json", &journal.target)?;
        if runtime.start_and_check(&journal.target).is_ok() {
            journal.phase = "committed".into();
            self.persist("transition.json", &journal)?;
            Ok(journal)
        } else {
            journal.error = Some(
                "target services failed readiness; recovering untouched prior data profile".into(),
            );
            self.restore(journal, runtime)
        }
    }
    fn restore(&self, mut journal: Journal, runtime: &mut impl Runtime) -> Result<Journal> {
        if let Some(previous) = &journal.previous {
            self.validate_selection(previous, false)?;
        }
        journal.phase = "recovering".into();
        self.persist("transition.json", &journal)?;
        if runtime.stop().is_err() {
            journal.phase = "recovery_failed".into();
        } else if let Some(previous) = &journal.previous {
            self.persist("active.json", previous)?;
            journal.phase = if runtime.start_and_check(previous).is_ok() {
                "rolled_back"
            } else {
                "recovery_failed"
            }
            .into();
        } else {
            match fs::remove_file(self.state.join("active.json")) {
                Ok(()) => {}
                Err(e) if e.kind() == std::io::ErrorKind::NotFound => {}
                Err(e) => return Err(e.into()),
            }
            fs::File::open(&self.state)?.sync_all()?;
            journal.phase = "rolled_back".into();
        }
        self.persist("transition.json", &journal)?;
        Ok(journal)
    }
    pub fn recover(&self, runtime: &mut impl Runtime) -> Result<Journal> {
        let _lock = self.lock()?;
        let journal: Journal =
            serde_json::from_slice(&fs::read(self.state.join("transition.json"))?)?;
        if !self.unfinished()? {
            return Ok(journal);
        }
        // Do not execute or require a healthy target artifact to recover the prior profile.
        // Equality binds this selector to the journal; restore independently verifies the old artifact.
        let bytes = self.active_bytes()?;
        let active: Option<Selection> = if bytes.is_empty() {
            None
        } else {
            Some(serde_json::from_slice(&bytes)?)
        };
        if active.as_ref() != Some(&journal.target) && active != journal.previous {
            bail!("active selection changed outside transition");
        }
        self.restore(journal, runtime)
    }
}
