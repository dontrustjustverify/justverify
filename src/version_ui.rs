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
    pub fn lines(&self, height: u16) -> Vec<String> {
        let mut lines=vec![format!("CORE VERSION | network: {} | mode: {}",self.network,if self.watch_only {"watch-only"} else {"node"}),"Up/Down select | P patches | N network | W wallet mode | D download | R recovery | Enter review | Esc back".into(),"Each version keeps separate Core data, electrs index and policy. Initial sync may be required.".into()];
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
