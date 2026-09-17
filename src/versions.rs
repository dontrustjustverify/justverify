//! Reviewed version changes reset only registered chain data, keeping its paths.
use crate::{
    policy::Policy,
    storage::{Instance, instance_mode, prepare, registered},
};
use anyhow::{Context, Result, bail};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::{
    fs::{self, OpenOptions},
    io::Write,
    os::unix::fs::{MetadataExt, OpenOptionsExt, PermissionsExt},
    path::{Path, PathBuf},
    process::{Command, Stdio},
    time::{Duration, Instant},
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
    pub destructive: bool,
    pub explanation: String,
    pub warnings: Vec<String>,
    pub delete_scope: Vec<String>,
    pub preserved: Vec<String>,
    #[serde(skip)]
    revision: String,
    #[serde(skip)]
    policy_revision: String,
    #[serde(skip)]
    marker_revision: String,
    #[serde(skip)]
    reset: Option<Value>,
    #[serde(skip)]
    created: Instant,
}
#[derive(Serialize, Deserialize)]
pub struct Journal {
    pub phase: String,
    pub previous: Option<Selection>,
    pub target: Selection,
    pub error: Option<String>,
    #[serde(default)]
    pub reset: Option<Value>,
    #[serde(default)]
    pub deletion_started: bool,
    #[serde(default)]
    policy_revision: String,
}
/// stop must prove all writers exited; guard must survive daemon death/reboot.
pub trait Runtime {
    fn guard(&mut self, blocked: bool) -> Result<()>;
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
            if fs::symlink_metadata(path)?.file_type().is_symlink()
                || !path.is_dir()
                || fs::metadata(path)?.permissions().mode() & 0o077 != 0
            {
                bail!("private real version state/data roots required");
            }
        }
        let m = fs::metadata(data)?;
        Ok(Self {
            catalog: catalog.canonicalize()?,
            binaries: binaries.canonicalize()?,
            data: data.canonicalize()?,
            state: state.canonicalize()?,
            data_identity: (m.dev(), m.ino()),
        })
    }
    fn root_check(&self) -> Result<()> {
        let m = fs::symlink_metadata(&self.data)?;
        if !m.is_dir() || (m.dev(), m.ino()) != self.data_identity {
            bail!("data volume changed or missing; no fallback writes allowed");
        }
        Ok(())
    }
    fn artifact(&self, instance: Instance) -> Result<Selection> {
        self.root_check()?;
        registered(&self.data, &instance)?;
        let version = &instance.core_version;
        let binary = self
            .binaries
            .join(version)
            .join(format!("bitcoin-{version}/bin/bitcoind"));
        let releases: Value =
            serde_json::from_slice(&fs::read(self.catalog.join("releases.json"))?)?;
        let release = releases["releases"]
            .as_array()
            .context("invalid catalog")?
            .iter()
            .find(|r| r["version"] == version.as_str())
            .context("unknown version")?;
        // This digest pins the executable from the official archive whose checksum
        // and trusted signer were verified by the existing download pipeline.
        let binary_sha256 =
            hash(&fs::read(&binary).context("download and verify the target binary first")?);
        if release["arm64_binary_sha256"] != binary_sha256 {
            bail!("official verified binary checksum mismatch");
        }
        let policy_file = instance.core_data.parent().unwrap().join("managed.conf");
        Ok(Selection {
            instance,
            binary,
            binary_sha256,
            policy_file,
        })
    }
    fn validate_selection(&self, selection: &Selection, allow_new: bool) -> Result<()> {
        if self.artifact(selection.instance.clone())? != *selection {
            bail!("registered selection or artifact changed");
        }
        if !allow_new && !selection.instance.core_data.parent().unwrap().exists() {
            bail!("registered data missing; refusing empty replacement");
        }
        prepare(&selection.instance)
    }
    fn active_bytes(&self) -> Result<Vec<u8>> {
        match fs::read(self.state.join("active.json")) {
            Ok(b) => Ok(b),
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
        if !self.state.join("transition.json").exists() {
            return Ok(json!({"needs_recovery":false,"phase":"none"}));
        }
        let j = self.journal()?;
        Ok(
            json!({"needs_recovery":self.unfinished()?,"phase":j.phase,"previous":j.previous,"target":j.target,"error":j.error,"deletion_started":j.deletion_started,"destructive":j.reset.is_some()}),
        )
    }
    fn worker(&self, action: &str, instance: &Instance, receipt: Option<&Value>) -> Result<Value> {
        self.root_check()?;
        registered(&self.data, instance)?;
        let mut child = Command::new("python3")
            .args(["-I", "-c", include_str!("../scripts/chain_reset.py")])
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .spawn()?;
        child.stdin.take().unwrap().write_all(&serde_json::to_vec(
            &json!({"parent_pid":std::process::id(),"action":action,"root":self.data,"instance":instance,"receipt":receipt}),
        )?)?;
        let out = child.wait_with_output()?;
        let response: Value =
            serde_json::from_slice(&out.stdout).context("chain storage worker failed")?;
        if !out.status.success() || response["ok"] != true {
            bail!(
                "{}",
                response["error"]
                    .as_str()
                    .unwrap_or("chain storage check failed")
            );
        }
        Ok(response["result"].clone())
    }
    fn marker_hash(&self, selection: &Selection) -> Result<String> {
        let path = selection
            .instance
            .core_data
            .parent()
            .unwrap()
            .join("instance.json");
        if !path.exists() {
            return Ok(hash(b""));
        }
        if fs::symlink_metadata(&path)?.file_type().is_symlink() {
            bail!("linked profile marker refused");
        }
        Ok(hash(&fs::read(path)?))
    }
    fn profiles(&self) -> Result<std::collections::BTreeMap<String, Instance>> {
        let path = self.state.join("profiles.json");
        if !path.exists() {
            return Ok(Default::default());
        }
        if fs::symlink_metadata(&path)?.file_type().is_symlink() {
            bail!("linked profile registry refused");
        }
        Ok(serde_json::from_slice(&fs::read(path)?)?)
    }
    fn profile_key(network: &str, watch: bool) -> String {
        format!("{network}:{}", if watch { "watch-only" } else { "node" })
    }
    fn remember(&self, instance: &Instance) -> Result<()> {
        let mut profiles = self.profiles()?;
        profiles.insert(
            Self::profile_key(&instance.network, instance.watch_only),
            instance.clone(),
        );
        self.persist("profiles.json", &profiles)
    }
    pub fn preview(&self, version: &str, network: &str) -> Result<Preview> {
        self.preview_mode(version, network, false)
    }
    pub fn preview_mode(&self, version: &str, network: &str, watch_only: bool) -> Result<Preview> {
        let _lock = self.lock()?;
        if self.unfinished()? {
            bail!("interrupted version operation requires recovery");
        }
        let previous = self.active()?;
        let mut instance = instance_mode(&self.data, version, network, "0.11.1", watch_only)?;
        let destructive = previous
            .as_ref()
            .is_some_and(|p| p.instance.core_version != version);
        if let Some(p) = &previous {
            if destructive {
                if p.instance.network != network || p.instance.watch_only != watch_only {
                    bail!("change network or node mode separately; no implicit chain deletion");
                }
                instance = p.instance.clone();
                instance.core_version = version.into();
                instance.data_id = Some(
                    p.instance
                        .core_data
                        .parent()
                        .unwrap()
                        .file_name()
                        .unwrap()
                        .to_str()
                        .context("invalid data identity")?
                        .into(),
                );
            } else if p.instance.network == network && p.instance.watch_only == watch_only {
                bail!("same version and mode already selected; no data change");
            }
        }
        if !destructive {
            if let Some(saved) = self
                .profiles()?
                .get(&Self::profile_key(network, watch_only))
            {
                if saved.core_version != version {
                    bail!(
                        "that network/mode is registered with a different binary; explicit separate review required"
                    );
                }
                registered(&self.data, saved)?;
                prepare(saved)?;
                instance = saved.clone();
            }
        }
        let target = self.artifact(instance)?;
        let existing_instance = target.instance.core_data.parent().unwrap().exists();
        if existing_instance && !destructive {
            prepare(&target.instance)?;
        }
        for s in previous.iter().chain(std::iter::once(&target)) {
            if crate::policy::transaction_status(&s.policy_file)?["needs_recovery"] == true {
                bail!("finish interrupted policy operation first");
            }
        }
        let policy = Policy::load(&self.catalog, version, network)?;
        // Validate CURRENT settings against TARGET catalog. Never silently drop
        // removed settings, or inherit an old target-version policy directory.
        let mut values = policy.current(&target.policy_file)?;
        if !target.policy_file.exists() {
            values.extend(crate::policy::installation_defaults());
        }
        let plan = policy.preview(&target.policy_file, values)?;
        let reset = if destructive {
            Some(self.worker("prepare", &target.instance, None)?)
        } else {
            None
        };
        policy.preflight(&target.binary, &self.state, &plan)?;
        let delete_scope = reset
            .as_ref()
            .map(|r| {
                r["allowlist"]
                    .as_array()
                    .unwrap()
                    .iter()
                    .map(|v| v.as_str().unwrap().into())
                    .collect()
            })
            .unwrap_or_default();
        let preserved = vec![
            "지갑·watch-only 정보: 지갑 데이터가 있는 버전 전환은 삭제 전에 차단합니다.".into(),
            "RPC 인증정보, Tor/I2P 개인키, 기기·접속 설정".into(),
            "다른 네트워크, 무관한 프로필, 과거 버전별 폴더".into(),
        ];
        let warnings = if destructive {
            vec!["Bitcoin 전체 IBD와 electrs 인덱싱이 필요합니다. 재시작 중에는 노드·Electrs·멤풀을 사용할 수 없으며 동기화 중에는 이용이 제한됩니다.".into(),"삭제 후 즉시 되돌릴 수 없습니다. 삭제가 시작된 뒤 실패해도 이전 바이너리로 자동 복귀하지 않습니다.".into(),"Core와 electrs의 현재 디렉토리 경로를 그대로 사용합니다. 과거 대상 버전 폴더는 재사용하거나 정리하지 않습니다.".into()]
        } else {
            vec![
                "네트워크·노드 모드 변경은 기존 프로필을 보존하며 체인 데이터를 초기화하지 않습니다."
                    .into(),
            ]
        };
        let marker_revision = self.marker_hash(&target)?;
        Ok(Preview { previous,target,existing_instance,destructive,delete_scope,preserved,warnings,revision:hash(&self.active_bytes()?),policy_revision:plan.revision,marker_revision,reset,created:Instant::now(),explanation:if destructive {"현재 프로필에서 아래 체인·인덱스 데이터만 삭제한 뒤, 검증된 대상 버전을 시작하고 처음부터 동기화합니다."} else {"체인 데이터를 삭제하지 않고 별도의 네트워크·노드 모드 프로필을 선택합니다."}.into() })
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
    fn journal(&self) -> Result<Journal> {
        let j: Journal = serde_json::from_slice(&fs::read(self.state.join("transition.json"))?)?;
        if !matches!(
            j.phase.as_str(),
            "stopping"
                | "stop_failed"
                | "resetting"
                | "reset_failed"
                | "activating"
                | "starting"
                | "target_start_failed"
                | "committed"
                | "recovering"
                | "restoring_previous"
                | "rolled_back"
                | "recovery_failed"
        ) {
            bail!("invalid version journal phase");
        }
        if j.deletion_started
            && (j.reset.is_none()
                || !matches!(
                    j.phase.as_str(),
                    "resetting"
                        | "reset_failed"
                        | "activating"
                        | "starting"
                        | "target_start_failed"
                        | "committed"
                ))
        {
            bail!("inconsistent irreversible version journal");
        }
        Ok(j)
    }
    fn unfinished(&self) -> Result<bool> {
        if !self.state.join("transition.json").exists() {
            return Ok(false);
        }
        Ok(!matches!(
            self.journal()?.phase.as_str(),
            "committed" | "rolled_back"
        ))
    }
    pub fn apply(&self, preview: Preview, runtime: &mut impl Runtime) -> Result<Journal> {
        let _lock = self.lock()?;
        if self.unfinished()? {
            bail!("unfinished version transition requires recovery");
        }
        if preview.created.elapsed() >= Duration::from_secs(300)
            || hash(&self.active_bytes()?) != preview.revision
            || self.active()? != preview.previous
        {
            bail!("stale or expired version preview");
        }
        if self.artifact(preview.target.instance.clone())? != preview.target
            || self.marker_hash(&preview.target)? != preview.marker_revision
        {
            bail!("target binary or registered profile changed; review again");
        }
        let policy = Policy::load(
            &self.catalog,
            &preview.target.instance.core_version,
            &preview.target.instance.network,
        )?;
        let mut values = policy.current(&preview.target.policy_file)?;
        if !preview.target.policy_file.exists() {
            values.extend(crate::policy::installation_defaults());
        }
        if policy
            .preview(&preview.target.policy_file, values)?
            .revision
            != preview.policy_revision
        {
            bail!("policy changed after target preparation");
        }
        for s in preview
            .previous
            .iter()
            .chain(std::iter::once(&preview.target))
        {
            if crate::policy::transaction_status(&s.policy_file)?["needs_recovery"] == true {
                bail!("pending policy recovery");
            }
        }
        if let Some(reset) = &preview.reset {
            self.worker("validate", &preview.target.instance, Some(reset))?;
        } else {
            self.validate_selection(&preview.target, true)?;
            if !preview.target.policy_file.exists() {
                crate::policy::atomic(
                    &preview.target.policy_file,
                    b"datacarrier=0\ndatacarriersize=83\ntxindex=1\n",
                )?;
            }
        }
        if let Some(previous) = &preview.previous {
            self.remember(&previous.instance)?;
        }
        let mut j = Journal {
            phase: "stopping".into(),
            previous: preview.previous,
            target: preview.target,
            error: None,
            reset: preview.reset,
            deletion_started: false,
            policy_revision: preview.policy_revision,
        };
        self.persist("transition.json", &j)?;
        if j.reset.is_some() {
            runtime.guard(true)?;
        }
        if runtime.stop().is_err() {
            j.error = Some(
                "service shutdown not confirmed; no data deleted; recover the existing runtime"
                    .into(),
            );
            j.phase = "stop_failed".into();
            self.persist("transition.json", &j)?;
            if j.reset.is_some() {
                runtime.guard(false)?;
            }
            return Ok(j);
        }
        self.finish(j, runtime)
    }
    fn finish(&self, mut j: Journal, runtime: &mut impl Runtime) -> Result<Journal> {
        if let Some(reset) = &j.reset {
            // Persist the point of no automatic rollback BEFORE the first unlink.
            if !j.deletion_started {
                self.worker("validate", &j.target.instance, Some(reset))?;
                j.deletion_started = true;
                j.phase = "resetting".into();
                self.persist("transition.json", &j)?;
            }
            if matches!(j.phase.as_str(), "resetting" | "reset_failed") {
                runtime.guard(true)?; // root-owned irreversible checkpoint precedes unlink
                if self
                    .worker("reset", &j.target.instance, Some(reset))
                    .is_err()
                {
                    j.phase = "reset_failed".into();
                    j.error=Some("chain reset incomplete; services remain blocked; resume the same reviewed scope".into());
                    self.persist("transition.json", &j)?;
                    return Ok(j);
                }
                j.phase = "activating".into();
                self.persist("transition.json", &j)?;
            }
            if j.phase == "activating" {
                runtime.guard(true)?;
            } // root checks the chain scope is empty
            // Rebinding the binary metadata does not rename or recreate datadirs.
            if self.artifact(j.target.instance.clone())? != j.target {
                bail!("prepared target artifact changed");
            }
            crate::policy::atomic(
                &j.target
                    .instance
                    .core_data
                    .parent()
                    .unwrap()
                    .join("instance.json"),
                &serde_json::to_vec_pretty(&j.target.instance)?,
            )?;
        }
        self.persist("active.json", &j.target)?;
        self.remember(&j.target.instance)?;
        j.phase = "starting".into();
        self.persist("transition.json", &j)?;
        if runtime.start_and_check(&j.target).is_ok() {
            j.phase = "committed".into();
            j.error = None;
            self.persist("transition.json", &j)?;
            if j.reset.is_some() {
                runtime.guard(false)?;
            }
            Ok(j)
        } else if j.deletion_started {
            let _ = runtime.stop();
            j.phase = "target_start_failed".into();
            j.error=Some("target startup failed after chain reset; old binary rollback forbidden; retry target through recovery".into());
            self.persist("transition.json", &j)?;
            Ok(j)
        } else {
            self.restore(j, runtime)
        }
    }
    fn restore(&self, mut j: Journal, runtime: &mut impl Runtime) -> Result<Journal> {
        if j.deletion_started {
            bail!("previous binary rollback is forbidden after deletion");
        }
        j.phase = "recovering".into();
        self.persist("transition.json", &j)?;
        runtime.stop()?;
        if let Some(previous) = &j.previous {
            self.validate_selection(previous, false)?;
            self.persist("active.json", previous)?;
            if j.reset.is_some() {
                runtime.guard(false)?;
            }
            j.phase = "restoring_previous".into();
            self.persist("transition.json", &j)?;
            j.phase = if runtime.start_and_check(previous).is_ok() {
                "rolled_back"
            } else {
                "recovery_failed"
            }
            .into();
        } else {
            if self.state.join("active.json").exists() {
                fs::remove_file(self.state.join("active.json"))?;
                fs::File::open(&self.state)?.sync_all()?;
            }
            j.phase = "rolled_back".into();
        }
        self.persist("transition.json", &j)?;
        Ok(j)
    }
    pub fn recover(&self, runtime: &mut impl Runtime) -> Result<Journal> {
        let _lock = self.lock()?;
        let j = self.journal()?;
        if !self.unfinished()? && j.phase != "stop_failed" {
            if j.phase == "committed" && j.reset.is_some() {
                runtime.guard(false)?;
            }
            return Ok(j);
        }
        self.root_check()?;
        let active: Option<Selection> = if self.active_bytes()?.is_empty() {
            None
        } else {
            Some(serde_json::from_slice(&self.active_bytes()?)?)
        };
        if active.as_ref() != Some(&j.target) && active != j.previous {
            bail!("active registration changed outside reviewed transition");
        }
        if j.deletion_started {
            let previous = j
                .previous
                .as_ref()
                .context("missing reset source registration")?;
            if j.target.instance.core_data != previous.instance.core_data
                || j.target.instance.electrs_data != previous.instance.electrs_data
                || j.target.instance.network != previous.instance.network
                || j.target.instance.watch_only != previous.instance.watch_only
            {
                bail!("invalid reset journal scope");
            }
            let marker: Instance = serde_json::from_slice(&fs::read(
                j.target
                    .instance
                    .core_data
                    .parent()
                    .unwrap()
                    .join("instance.json"),
            )?)?;
            let marker_valid = match j.phase.as_str() {
                "resetting" | "reset_failed" => marker == previous.instance,
                "activating" => marker == previous.instance || marker == j.target.instance,
                "starting" | "target_start_failed" | "committed" => marker == j.target.instance,
                _ => false,
            };
            if !marker_valid {
                bail!("registered profile changed during reset");
            }
            if self.artifact(j.target.instance.clone())? != j.target {
                bail!("prepared target artifact changed");
            }
            let policy = Policy::load(
                &self.catalog,
                &j.target.instance.core_version,
                &j.target.instance.network,
            )?;
            if policy
                .preview(
                    &j.target.policy_file,
                    policy.current(&j.target.policy_file)?,
                )?
                .revision
                != j.policy_revision
            {
                bail!("target policy changed; recovery requires operator repair");
            }
            self.worker("validate", &j.target.instance, j.reset.as_ref())?;
            runtime.guard(true)?;
            runtime.stop()?;
            self.finish(j, runtime)
        } else {
            self.restore(j, runtime)
        }
    }
}
