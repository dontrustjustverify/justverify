use crate::{clean, tui::request_with_timeout};
use crossterm::event::KeyCode;
use serde_json::{Value, json};
use std::{path::Path, sync::mpsc, time::Duration};

#[derive(Default)]
pub struct StoragePage {
    state: Value,
    selected: usize,
    plan: Value,
    input: String,
    recovery: bool,
    message: String,
    pending: Option<mpsc::Receiver<(String, Result<Value, String>)>>,
}
impl StoragePage {
    fn start(&mut self, request: Value) {
        if self.pending.is_some() {
            return;
        }
        let (send, receive) = mpsc::channel();
        self.pending = Some(receive);
        std::thread::spawn(move || {
            let result = request_with_timeout(
                Path::new("/run/justverify-storage/api.sock"),
                &request,
                Duration::from_secs(240),
            )
            .map_err(|e| clean(&format!("{e:#}")));
            let _ = send.send((request["action"].as_str().unwrap_or("").to_owned(), result));
        });
    }
    pub fn load(&mut self) {
        self.start(json!({"action":"inventory"}));
    }
    pub fn poll(&mut self) {
        let Some(receiver) = &self.pending else {
            return;
        };
        let Ok((action, result)) = receiver.try_recv() else {
            return;
        };
        self.pending = None;
        match result {
            Ok(value) => {
                match action.as_str() {
                    "inventory" => {
                        self.state = value;
                        self.selected = self.selected.min(self.rows().len().saturating_sub(1));
                    }
                    "prepare_profile" => {
                        self.message="Version selection ready. Esc returns; V selects Core version and network.".into();
                    }
                    "preview" => {
                        self.plan = value;
                        self.input.clear();
                        self.recovery = false;
                        self.message.clear();
                    }
                    _ => {
                        self.message = if value["profile_ready"] == false {
                            "Volume committed; version service preparation failed. B retries preparation without formatting.".into()
                        } else {
                            format!(
                                "Volume result: {}. Esc then V selects the initial node profile. B retries profile preparation.",
                                value["phase"]
                            )
                        };
                        self.plan = Value::Null;
                        self.input.clear();
                        self.load();
                    }
                }
            }
            Err(error) => {
                self.message = format!(
                    "{error} Keep the plan ID. R reviews saved recovery; do not repeat formatting."
                )
            }
        }
    }
    fn rows(&self) -> &[Value] {
        self.state["devices"]
            .as_array()
            .map(Vec::as_slice)
            .unwrap_or(&[])
    }
    pub fn key(&mut self, key: KeyCode) -> bool {
        if key == KeyCode::Esc {
            if !self.plan.is_null() && self.pending.is_none() {
                self.plan = Value::Null;
                self.input.clear();
                return false;
            }
            return true;
        }
        if self.pending.is_some() {
            return false;
        }
        if !self.plan.is_null() {
            match key {
                KeyCode::Char(c) if !c.is_control() && self.input.len() < 256 => self.input.push(c),
                KeyCode::Backspace => {
                    self.input.pop();
                }
                KeyCode::Enter if self.recovery => {
                    self.start(json!({"action":"recover","id":self.plan["id"]}))
                }
                KeyCode::Enter => {
                    if self.plan["confirmation"].as_str() == Some(&self.input) {
                        self.start(json!({"action":"apply","id":self.plan["id"],"confirmation":self.input}));
                    } else {
                        self.message =
                            "Exact erasure confirmation does not match. No format requested."
                                .into();
                    }
                }
                _ => {}
            }
        } else {
            match key {
                KeyCode::Down => {
                    self.selected = (self.selected + 1).min(self.rows().len().saturating_sub(1))
                }
                KeyCode::Up => self.selected = self.selected.saturating_sub(1),
                KeyCode::Char('l' | 'L') => self.load(),
                KeyCode::Char('b' | 'B') => self.start(json!({"action":"prepare_profile"})),
                KeyCode::Char('r' | 'R') => {
                    if let Some(plan) = self.state["plans"].as_array().and_then(|rows| {
                        rows.iter().find(|p| {
                            ["formatting", "formatted", "mounted"]
                                .contains(&p["phase"].as_str().unwrap_or(""))
                        })
                    }) {
                        self.plan = plan.clone();
                        self.recovery = true;
                        self.input.clear();
                    } else {
                        self.message =
                            "No interrupted volume operation found. L refreshes saved state."
                                .into();
                    }
                }
                KeyCode::Enter => {
                    if let Some(row) = self.rows().get(self.selected).cloned() {
                        if row["review_action"] == "REVIEW_NEW" {
                            self.start(json!({"action":"preview","name":row["name"],"identity_digest":row["identity_digest"]}));
                        } else {
                            self.message="Selected device is preserved. Initial formatting is unavailable for this device.".into();
                        }
                    }
                }
                _ => {}
            }
        }
        false
    }
    pub fn lines(&self, height: u16) -> Vec<String> {
        let mut lines = vec!["STORAGE SETUP — owner access required".into()];
        if !self.plan.is_null() {
            lines.push(
                if self.recovery {
                    "RECOVER VOLUME — Enter checks UUID and resumes; never reformats"
                } else {
                    "ERASE DEVICE — all contents, including unrecognized data, will be lost"
                }
                .into(),
            );
            lines.push(format!(
                "Device {} | {} bytes | serial {}",
                self.plan["device"]["name"],
                self.plan["device"]["size_bytes"],
                self.plan["device"]["serial"]
            ));
            lines.push(format!(
                "Destination {} | phase {}",
                self.plan["mount"], self.plan["phase"]
            ));
            lines.push(format!(
                "Plan ID: {}",
                self.plan["id"].as_str().unwrap_or("")
            ));
            if !self.recovery {
                lines.push(format!(
                    "Type exactly: {}",
                    self.plan["confirmation"].as_str().unwrap_or("")
                ));
                lines.push(format!("> {}", self.input));
            }
            lines.push("Esc cancels this review. Existing node data is never moved.".into());
        } else {
            if self.state["factory_volume"]["source"] == "single-os-image" {
                lines.push(
                    "Included NVMe data is ready. Esc then V selects Core and network.".into(),
                );
            }
            lines.push(
                "Up/Down select | Enter review | R recovery | B profile | L refresh | Esc back"
                    .into(),
            );
            let count = usize::from(height.saturating_sub(10)).max(1);
            let start = self.selected.saturating_sub(count.saturating_sub(1));
            for (i, row) in self.rows().iter().enumerate().skip(start).take(count) {
                lines.push(format!(
                    "{} {} | {} bytes | {}",
                    if i == self.selected { ">" } else { " " },
                    row["name"].as_str().unwrap_or("?"),
                    row["size_bytes"],
                    row["reason"].as_str().unwrap_or("")
                ));
            }
            lines.push(
                "Enter only prepares a plan. Formatting requires exact device confirmation.".into(),
            );
        }
        if self.pending.is_some() {
            lines.push("Working... leaving the screen does not cancel the root operation.".into());
        }
        lines.push(self.message.clone());
        lines.into_iter().map(|line| clean(&line)).collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn wrong_confirmation_and_escape_never_start_mutation() {
        let mut page = StoragePage::default();
        page.plan = json!({"confirmation":"ERASE disk-123","id":"example"});
        for c in "ERASE disk-124".chars() {
            page.key(KeyCode::Char(c));
        }
        page.key(KeyCode::Enter);
        assert!(page.pending.is_none());
        assert!(page.message.contains("No format requested"));
        assert!(!page.key(KeyCode::Esc));
        assert!(page.plan.is_null());
        assert!(page.input.is_empty());
        assert!(page.pending.is_none());
    }
    #[test]
    fn protected_device_enter_does_not_request_a_preview() {
        let mut page = StoragePage::default();
        page.state = json!({"devices":[{"name":"/dev/system","review_action":"NONE","reason":"SYSTEM_DEVICE"}]});
        page.key(KeyCode::Enter);
        assert!(page.pending.is_none());
        assert!(page.message.contains("preserved"));
    }
}
