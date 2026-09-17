use anyhow::Result;
use serde_json::{Value, json};
use std::{collections::BTreeMap, path::Path};
#[derive(Default)]
pub struct VersionsPage {
    pub state: Value,
    pub selected: usize,
    pub expanded: bool,
    pub network: String,
    pub watch_only: bool,
    pub preview: Value,
    pub message: String,
    pub confirm_delete: bool,
}
impl VersionsPage {
    pub fn load(&mut self, socket: &Path) -> Result<()> {
        self.state = crate::tui::request(socket, &json!({"method":"state"}))?;
        if self.network.is_empty() {
            self.watch_only = self.state["active"]["instance"]["watch_only"] == true;
            self.network = self.state["active"]["instance"]["network"]
                .as_str()
                .unwrap_or("main")
                .into();
        }
        self.selected = self.entries().len().saturating_sub(1);
        Ok(())
    }
    pub fn entries(&self) -> Vec<Value> {
        let all = self.state["releases"]
            .as_array()
            .cloned()
            .unwrap_or_default();
        if self.expanded {
            return all;
        }
        let mut latest: BTreeMap<u64, Value> = BTreeMap::new();
        for release in all {
            let number: Vec<u64> = release["version"]
                .as_str()
                .unwrap_or("")
                .split('.')
                .filter_map(|p| p.parse().ok())
                .collect();
            if let Some(major) = number.first() {
                latest.insert(*major, release);
            }
        }
        latest.into_values().collect()
    }
    pub fn version(&self) -> Option<String> {
        self.entries()
            .get(self.selected)?
            .get("version")?
            .as_str()
            .map(str::to_owned)
    }
    pub fn cycle_network(&mut self) {
        let names = ["main", "test", "testnet4", "signet", "regtest"];
        self.network = names
            [(names.iter().position(|n| *n == self.network).unwrap_or(0) + 1) % names.len()]
        .into();
    }
    pub fn cancel(&mut self, socket: &Path) {
        if let Some(token) = self.preview["token"].as_str() {
            let _ = crate::tui::request(socket, &json!({"method":"cancel","token":token}));
        }
        self.preview = Value::Null;
        self.confirm_delete = false;
    }
    pub fn review_lines(&self) -> Vec<String> {
        let p = &self.preview["preview"];
        let mut lines = vec![
            "버전 변경 확인 | Esc 취소".into(),
            format!(
                "Core {} → {} | {} | {}",
                p["previous"]["instance"]["core_version"],
                p["target"]["instance"]["core_version"],
                self.network,
                if self.watch_only {
                    "watch-only"
                } else {
                    "node"
                }
            ),
            p["explanation"].as_str().unwrap_or("").into(),
        ];
        for (key, label) in [
            ("delete_scope", "삭제 대상 (현재/대상 프로필의 동일 경로)"),
            ("preserved", "보존 대상"),
            ("warnings", "주의"),
        ] {
            lines.push(label.into());
            if let Some(items) = p[key].as_array() {
                for item in items {
                    lines.push(item.as_str().unwrap_or("").into());
                }
            }
        }
        if p["destructive"] == true {
            lines.push(format!(
                "{} 취소    {} 데이터 삭제 후 버전 변경",
                if self.confirm_delete { " " } else { ">" },
                if self.confirm_delete { ">" } else { " " }
            ));
            lines.push(
                "Left/Right 선택 · Space 실행 · Up/Down 스크롤 · Enter는 삭제하지 않습니다".into(),
            );
        } else {
            lines.push("Enter 적용 · Esc 취소".into());
        }
        lines.push(self.message.clone());
        lines
    }
    pub fn lines(&self, height: u16) -> Vec<String> {
        let mut lines=vec![format!("CORE VERSION | network: {} | mode: {}",self.network,if self.watch_only {"watch-only"} else {"node"}),"Up/Down select | P patches | N network | W wallet mode | D download | R recovery | Enter review | Esc back".into(),"Different versions reset the current chain/index paths after explicit review. Selection/download changes no data.".into()];
        if self.state["transition"]["needs_recovery"] == true {
            lines.push(format!(
                "INTERRUPTED VERSION CHANGE: {}. R reviews recovery.",
                self.state["transition"]["phase"]
            ));
        }
        if let Some(error) = self.state["active_error"].as_str() {
            lines.push(crate::clean(error));
        }
        if self.state["active"].is_null()
            && self.state["active_error"].is_null()
            && self.state["transition"]["needs_recovery"] != true
        {
            lines.push(
                "FIRST PROFILE: choose Core version and network, then Enter to review and start."
                    .into(),
            );
        }
        let entries = self.entries();
        let count = usize::from(height.saturating_sub(8)).max(1);
        let start = self.selected.saturating_sub(count - 1);
        for (i, entry) in entries.iter().enumerate().skip(start).take(count) {
            lines.push(format!(
                "{} {:8} {} | {}",
                if i == self.selected { ">" } else { " " },
                entry["version"].as_str().unwrap_or("?"),
                entry["availability"].as_str().unwrap_or("unknown"),
                if entry["downloaded"] == true {
                    "local artifact; checked on review"
                } else {
                    "download required"
                }
            ));
        }
        if let Some(selected) = entries.get(self.selected) {
            lines.push(format!(
                "Support: {}",
                selected["support_status"].as_str().unwrap_or("unknown")
            ));
        }
        lines.push(format!(
            "Download: {} {}",
            self.state["download"]["version"].as_str().unwrap_or(""),
            self.state["download"]["phase"].as_str().unwrap_or("idle")
        ));
        lines.push(self.message.clone());
        lines
    }
}
