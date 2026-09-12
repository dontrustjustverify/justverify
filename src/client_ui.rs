use crate::clean;
use crossterm::event::KeyCode;
use serde_json::{Value, json};
use std::{
    io::Write,
    process::{Command, Stdio},
};
#[derive(Default)]
pub struct ClientsPage {
    rows: Vec<Value>,
    selected: usize,
    label: Option<String>,
    issued: Value,
    issued_qr: bool,
    revoke: bool,
    grant: Value,
    message: String,
    remote_open: bool,
    remote_state: Value,
    remote_plan: Value,
    remote_password: String,
}
impl ClientsPage {
    pub fn is_menu(&self) -> bool {
        !self.remote_open
            && self.label.is_none()
            && self.issued.is_null()
            && !self.revoke
            && self.grant.is_null()
    }
    pub fn is_qr(&self) -> bool {
        self.issued_qr
    }

    fn request(value: Value) -> Result<Value, String> {
        let mut child = Command::new("/opt/justverify/venv/bin/python")
            .arg("/opt/justverify/web/manage_clients.py")
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .spawn()
            .map_err(|_| "Client management unavailable".to_owned())?;
        child
            .stdin
            .take()
            .unwrap()
            .write_all(value.to_string().as_bytes())
            .map_err(|_| "Client request failed".to_owned())?;
        let output = child
            .wait_with_output()
            .map_err(|_| "Client request failed".to_owned())?;
        let response: Value = serde_json::from_slice(&output.stdout)
            .map_err(|_| "Invalid client response".to_owned())?;
        if response["ok"] != true {
            return Err(clean(
                response["error"]
                    .as_str()
                    .unwrap_or("Client operation failed"),
            ));
        }
        Ok(response["result"].clone())
    }
    pub fn load(&mut self) {
        match Self::request(json!({"action":"list"})) {
            Ok(value) => {
                self.rows = value.as_array().cloned().unwrap_or_default();
                self.selected = self.selected.min(self.rows.len().saturating_sub(1));
            }
            Err(error) => self.message = error,
        }
        if let Ok(state) =
            Self::request(json!({"action":"remote_rpc","request":{"action":"state"}}))
        {
            self.remote_state = state;
        }
    }
    pub fn key(&mut self, key: KeyCode) -> bool {
        if self.remote_open {
            if !self.remote_plan.is_null() {
                match key {
                    KeyCode::Esc => {
                        self.remote_plan = Value::Null;
                        self.remote_password.clear();
                    }
                    KeyCode::Backspace => {
                        self.remote_password.pop();
                    }
                    KeyCode::Char(c) if !c.is_control() && self.remote_password.len() < 256 => {
                        self.remote_password.push(c)
                    }
                    KeyCode::Enter if self.remote_password.len() >= 12 => {
                        let password = std::mem::take(&mut self.remote_password);
                        let result = Self::request(
                            json!({"action":"remote_rpc","request":{"action":"apply","token":self.remote_plan["token"],"password":password}}),
                        );
                        self.remote_plan = Value::Null;
                        match result {
                            Ok(state) => {
                                self.remote_state = state;
                                self.message = "Remote RPC setting applied.".into();
                            }
                            Err(error) => self.message = error,
                        }
                        if let Ok(state) = Self::request(
                            json!({"action":"remote_rpc","request":{"action":"state"}}),
                        ) {
                            self.remote_state = state;
                        }
                    }
                    _ => {}
                }
            } else {
                match key {
                    KeyCode::Esc => self.remote_open = false,
                    KeyCode::Char('e' | 'E' | 'd' | 'D') => {
                        match Self::request(
                            json!({"action":"remote_rpc","request":{"action":"preview","enabled":matches!(key,KeyCode::Char('e'|'E'))}}),
                        ) {
                            Ok(plan) => {
                                self.remote_plan = plan;
                                self.remote_password.clear();
                                self.message.clear();
                            }
                            Err(error) => self.message = error,
                        }
                    }
                    KeyCode::Char('l' | 'L') => {
                        match Self::request(
                            json!({"action":"remote_rpc","request":{"action":"state"}}),
                        ) {
                            Ok(state) => self.remote_state = state,
                            Err(error) => self.message = error,
                        }
                    }
                    _ => {}
                }
            }
            return false;
        }
        if !self.issued.is_null() {
            if self.issued_qr {
                if key == KeyCode::Esc {
                    self.issued_qr = false;
                }
            } else if key == KeyCode::Esc {
                self.issued = Value::Null;
            } else if matches!(key, KeyCode::Char('q' | 'Q'))
                && self.issued["quick_connect"]["matrix"].is_array()
            {
                self.issued_qr = true;
            }
            return false;
        }
        if !self.grant.is_null() {
            match key {
                KeyCode::Esc => self.grant = Value::Null,
                KeyCode::Enter => {
                    if let Some(row) = self.rows.get(self.selected) {
                        self.message = match Self::request(
                            json!({"action":if self.grant["transactions"] == true {"grant_transactions"} else {"grant_watch_only"},"id":row["id"],"profile_hash":self.grant["profile_hash"]}),
                        ) {
                            Ok(_) => if self.grant["transactions"] == true {
                                "Transaction permission granted."
                            } else {
                                "Wallet permission granted."
                            }
                            .into(),
                            Err(error) => error,
                        };
                    }
                    self.grant = Value::Null;
                    self.load();
                }
                _ => {}
            }
            return false;
        }
        if self.revoke {
            match key {
                KeyCode::Esc => self.revoke = false,
                KeyCode::Enter => {
                    if let Some(row) = self.rows.get(self.selected) {
                        self.message =
                            match Self::request(json!({"action":"revoke","id":row["id"]})) {
                                Ok(_) => "Client revoked.".into(),
                                Err(error) => error,
                            };
                    }
                    self.revoke = false;
                    self.load();
                }
                _ => {}
            }
            return false;
        }
        if let Some(label) = &mut self.label {
            match key {
                KeyCode::Esc => self.label = None,
                KeyCode::Backspace => {
                    label.pop();
                }
                KeyCode::Char(c) if !c.is_control() && label.len() < 64 => label.push(c),
                KeyCode::Enter => {
                    let name = label.clone();
                    match Self::request(json!({"action":"create","label":name})) {
                        Ok(value) => {
                            self.issued = value;
                            self.label = None;
                            self.load();
                        }
                        Err(error) => self.message = error,
                    }
                }
                _ => {}
            }
            return false;
        }
        match key {
            KeyCode::Char('o' | 'O') => {
                self.remote_open = true;
                self.message.clear();
                match Self::request(json!({"action":"remote_rpc","request":{"action":"state"}})) {
                    Ok(state) => self.remote_state = state,
                    Err(error) => self.message = error,
                }
            }
            KeyCode::Esc => return true,
            KeyCode::Char('a' | 'A') => self.label = Some(String::new()),
            KeyCode::Char('r' | 'R') => {
                if !self.rows.is_empty() {
                    self.revoke = true;
                }
            }
            KeyCode::Char('w' | 'W' | 't' | 'T') => {
                if let Some(row) = self.rows.get(self.selected) {
                    match Self::request(
                        json!({"action":if matches!(key, KeyCode::Char('t' | 'T')) {"preview_transactions"} else {"preview_watch_only"},"id":row["id"]}),
                    ) {
                        Ok(value) => self.grant = value,
                        Err(error) => self.message = error,
                    }
                }
            }
            KeyCode::Char('l' | 'L') => self.load(),
            KeyCode::Up => self.selected = self.selected.saturating_sub(1),
            KeyCode::Down => {
                self.selected = (self.selected + 1).min(self.rows.len().saturating_sub(1))
            }
            _ => {}
        }
        false
    }
    pub fn lines(&self, width: u16, height: u16) -> Vec<String> {
        if self.issued_qr {
            let host = self.remote_state["onion_host"].as_str().unwrap_or("");
            let mut lines = vec![
                "FULLY NODED QUICK CONNECT — sensitive one-time QR".into(),
                format!("{}:8332 | btcrpc client import", host),
                "Anyone who sees this QR can use this client's granted permissions.".into(),
                "Remote RPC must be enabled. Esc returns and keeps credentials visible.".into(),
            ];
            let Some(matrix) = self.issued["quick_connect"]["matrix"].as_array() else {
                return vec!["Quick Connect QR unavailable. Esc returns.".into()];
            };
            let size = matrix.len();
            if usize::from(width) < size + 2
                || usize::from(height) < size.div_ceil(2) + lines.len() + 2
            {
                lines.push("Enlarge the terminal to display the complete QR.".into());
                return lines;
            }
            for row in (0..size).step_by(2) {
                let mut line = String::new();
                for col in 0..size {
                    let top = matrix[row][col] == true;
                    let bottom = row + 1 < size && matrix[row + 1][col] == true;
                    line.push(match (top, bottom) {
                        (true, true) => '█',
                        (true, false) => '▀',
                        (false, true) => '▄',
                        _ => ' ',
                    });
                }
                lines.push(line);
            }
            return lines;
        }
        let mut lines = vec!["RPC CLIENTS — W grants an assigned watch-only wallet".into()];
        if self.remote_open {
            lines.push("REMOTE RPC — authenticated clients through Tor".into());
            if self.remote_state.is_object() {
                lines.push(format!(
                    "Saved: {} | Listener: {} | Recovery: {}",
                    self.remote_state["stored_enabled"],
                    self.remote_state["running"],
                    self.remote_state["needs_recovery"]
                ));
                lines.push(match self.remote_state["onion_host"].as_str() {
                    Some(host) => format!(
                        "Tor endpoint: http://{}:{}/rpc",
                        host, self.remote_state["onion_port"]
                    ),
                    None => "Tor endpoint: public address unavailable".into(),
                });
            }
            if self.remote_plan.is_null() {
                lines.push("E enable | D disable | L refresh | Esc back".into());
                lines.push("Listener status does not prove external Tor reachability.".into());
            } else {
                lines.push(format!(
                    "REVIEW: remote RPC {}",
                    if self.remote_plan["enabled"] == true {
                        "ENABLE"
                    } else {
                        "DISABLE"
                    }
                ));
                lines.push("Existing RPC clients keep their individual permissions.".into());
                lines.push("Disabling cannot undo transactions already broadcast.".into());
                lines.push("Administrator password; Enter applies, Esc cancels (120s).".into());
                lines.push(format!(
                    "Password> {}",
                    "*".repeat(self.remote_password.chars().count())
                ));
            }
            lines.push(self.message.clone());
        } else if !self.issued.is_null() {
            lines.extend([
                "NEW CLIENT — private credentials, displayed once. Esc hides.".into(),
                "HTTPS endpoint: https://justverify.local/rpc".into(),
                match self.remote_state["onion_host"].as_str() {
                    Some(host) => format!(
                        "Tor RPC: http://{}:{}/rpc ({})",
                        host,
                        self.remote_state["onion_port"],
                        if self.remote_state["running"] == true {
                            "enabled"
                        } else {
                            "disabled"
                        }
                    ),
                    None => "Tor RPC: public address unavailable".into(),
                },
                if self.issued["quick_connect"]["matrix"].is_array() {
                    "Q Fully Noded sensitive Quick Connect QR; Esc hides credentials."
                } else {
                    "Quick Connect QR unavailable; Esc hides credentials."
                }
                .into(),
                format!("Username: {}", self.issued["id"].as_str().unwrap_or("")),
                format!(
                    "Password: {}",
                    self.issued["password"].as_str().unwrap_or("")
                ),
                "Authenticate the node's TLS certificate before using these credentials.".into(),
                "Scope: allowlisted node queries. No wallet or administrative methods.".into(),
            ]);
        } else if !self.grant.is_null() {
            lines.extend([
                format!(
                    "GRANT {} to {}?",
                    if self.grant["transactions"] == true {
                        "TRANSACTIONS"
                    } else {
                        "WATCH-ONLY"
                    },
                    self.rows[self.selected]["label"]
                ),
                format!(
                    "Core {} | {} | wallet {}",
                    self.grant["version"], self.grant["network"], self.grant["wallet"]
                ),
                if self.grant["transactions"] == true {
                    "Allows coin locking, PSBT funding and signed transaction broadcast."
                } else {
                    "Allows public descriptor import and wallet queries in this profile."
                }
                .into(),
                "No private keys or signing. Enter confirms; Esc cancels.".into(),
            ]);
        } else if self.revoke {
            lines.push(format!(
                "REVOKE {}? Enter confirms; Esc cancels.",
                self.rows[self.selected]["label"]
            ));
        } else {
            lines.push(
                "A add | W wallet | T transactions | R revoke | O remote RPC | E Electrum/Tor | Q QR | L refresh | Esc back".into(),
            );
            let count = usize::from(height.saturating_sub(8)).max(1);
            let start = self.selected.saturating_sub(count.saturating_sub(1));
            for (i, row) in self.rows.iter().enumerate().skip(start).take(count) {
                lines.push(format!(
                    "{} {} | {}",
                    if i == self.selected { ">" } else { " " },
                    row["label"].as_str().unwrap_or(""),
                    if row["revoked"] == true {
                        "revoked"
                    } else if row["transaction_profiles"]
                        .as_array()
                        .is_some_and(|profiles| profiles.contains(&row["wallet_profile"]))
                    {
                        "watch-only + transactions"
                    } else {
                        row["scope"].as_str().unwrap_or("node-read")
                    }
                ));
            }
            if let Some(label) = &self.label {
                lines.push(format!("Client name> {label} [Enter creates; Esc cancels]"));
            }
            lines.push(self.message.clone());
        }
        lines.into_iter().map(|line| clean(&line)).collect()
    }
}
