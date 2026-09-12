use crate::{clean, tui::request_with_timeout};
use crossterm::event::KeyCode;
use serde_json::{Value, json};
use std::{path::Path, sync::mpsc, time::Duration};

const SOCKET: &str = "/run/justverify-backup/control.sock";
const RESTORE_CONFIRMATION: &str = "RESTORE DEVICE IDENTITY";

#[derive(Default)]
pub struct BackupPage {
    state: Value,
    plan: Value,
    mode: char,
    input: String,
    first_passphrase: String,
    message: String,
    pending: Option<mpsc::Receiver<(String, Result<Value, String>)>>,
    authorized_request: Option<Value>,
}

impl BackupPage {
    fn start(&mut self, request: Value) {
        if self.pending.is_some() {
            return;
        }
        let action = request["action"].as_str().unwrap_or("").to_owned();
        let (send, receive) = mpsc::channel();
        self.pending = Some(receive);
        std::thread::spawn(move || {
            let result =
                request_with_timeout(Path::new(SOCKET), &request, Duration::from_secs(240))
                    .map_err(|error| clean(&format!("{error:#}")));
            let _ = send.send((action, result));
        });
    }

    fn reauthenticate(&mut self, request: Value) {
        self.authorized_request = Some(request);
        self.input.clear();
        self.mode = 'a';
    }

    pub fn load(&mut self) {
        if self.mode == '\0' {
            self.mode = ' ';
        }
        self.start(json!({"action":"state"}));
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
            Ok(value) => match action.as_str() {
                "state" => self.state = value,
                "create_preview" => {
                    self.plan = value;
                    self.mode = 'c';
                    self.input.clear();
                    self.first_passphrase.clear();
                    self.message.clear();
                }
                "create_apply" => {
                    self.message = format!(
                        "Encrypted backup saved: {} bytes. Copy it off the device and keep the passphrase separately.",
                        value["bytes"]
                    );
                    self.mode = ' ';
                    self.plan = Value::Null;
                    self.load();
                }
                "restore_preview" => {
                    self.plan = value;
                    self.mode = 'o';
                    self.input.clear();
                    self.message.clear();
                }
                "restore_apply" => {
                    self.message = "Restore committed. Services and this browser terminal will restart; reconnect with the restored owner password.".into();
                    self.mode = ' ';
                    self.plan = Value::Null;
                    self.state = Value::Null;
                }
                "recover" => {
                    self.message = format!("Restore recovery result: {}", value["phase"]);
                    self.mode = ' ';
                    self.load();
                }
                _ => self.message = "Unexpected backup response.".into(),
            },
            Err(error) => {
                self.message = error;
                self.input.clear();
                self.first_passphrase.clear();
                self.authorized_request = None;
                if matches!(
                    action.as_str(),
                    "create_apply" | "restore_apply" | "restore_preview" | "recover"
                ) {
                    self.mode = ' ';
                    self.plan = Value::Null;
                }
            }
        }
    }

    fn type_secret(input: &mut String, key: KeyCode) {
        match key {
            KeyCode::Backspace => {
                input.pop();
            }
            KeyCode::Char(character) if !character.is_control() && input.len() < 256 => {
                input.push(character)
            }
            _ => {}
        }
    }

    pub fn key(&mut self, key: KeyCode) -> bool {
        if key == KeyCode::Esc {
            if self.mode == ' ' && self.pending.is_none() {
                self.input.clear();
                self.first_passphrase.clear();
                return true;
            }
            if self.pending.is_none() {
                self.mode = ' ';
                self.plan = Value::Null;
                self.authorized_request = None;
                self.input.clear();
                self.first_passphrase.clear();
                self.message = "Backup review cancelled. No files changed.".into();
            }
            return false;
        }
        if self.pending.is_some() {
            return false;
        }
        match self.mode {
            'a' => match key {
                KeyCode::Enter if !self.input.is_empty() => {
                    if let Some(mut request) = self.authorized_request.take() {
                        request["password"] = json!(std::mem::take(&mut self.input));
                        self.start(request);
                    }
                }
                other => Self::type_secret(&mut self.input, other),
            },
            'c' => match key {
                KeyCode::Enter if self.input.chars().count() >= 16 => {
                    self.first_passphrase = std::mem::take(&mut self.input);
                    self.mode = 'd';
                }
                KeyCode::Enter => self.message = "Use at least 16 characters.".into(),
                other => Self::type_secret(&mut self.input, other),
            },
            'd' => match key {
                KeyCode::Enter if self.input == self.first_passphrase => {
                    let passphrase = std::mem::take(&mut self.input);
                    self.first_passphrase.clear();
                    self.reauthenticate(json!({"action":"create_apply","token":self.plan["token"],"passphrase":passphrase}));
                }
                KeyCode::Enter => {
                    self.input.clear();
                    self.first_passphrase.clear();
                    self.mode = 'c';
                    self.message = "Passphrases differed. Start again.".into();
                }
                other => Self::type_secret(&mut self.input, other),
            },
            'r' => match key {
                KeyCode::Enter if self.input.chars().count() >= 16 => {
                    let passphrase = std::mem::take(&mut self.input);
                    self.reauthenticate(
                        json!({"action":"restore_preview","passphrase":passphrase}),
                    );
                }
                KeyCode::Enter => {
                    self.message = "Use the backup passphrase (at least 16 characters).".into()
                }
                other => Self::type_secret(&mut self.input, other),
            },
            'o' => match key {
                KeyCode::Enter if self.input == RESTORE_CONFIRMATION => {
                    self.input.clear();
                    self.mode = 'p';
                    self.message.clear();
                }
                KeyCode::Enter => {
                    self.message =
                        "Exact restore confirmation does not match. No restore requested.".into()
                }
                KeyCode::Backspace => {
                    self.input.pop();
                }
                KeyCode::Char(character) if !character.is_control() && self.input.len() < 64 => {
                    self.input.push(character)
                }
                _ => {}
            },
            'p' => match key {
                KeyCode::Enter if self.input.chars().count() >= 16 => {
                    let passphrase = std::mem::take(&mut self.input);
                    self.reauthenticate(json!({
                        "action":"restore_apply",
                        "token":self.plan["token"],
                        "passphrase":passphrase,
                        "confirmation":RESTORE_CONFIRMATION
                    }));
                }
                KeyCode::Enter => self.message = "Use the backup passphrase again.".into(),
                other => Self::type_secret(&mut self.input, other),
            },
            'x' => {
                if key == KeyCode::Enter {
                    self.reauthenticate(json!({"action":"recover"}));
                }
            }
            _ => match key {
                KeyCode::Char('c' | 'C') => self.start(json!({"action":"create_preview"})),
                KeyCode::Char('r' | 'R') => {
                    self.mode = 'r';
                    self.input.clear();
                    self.message.clear();
                }
                KeyCode::Char('x' | 'X') => {
                    self.mode = 'x';
                    self.message.clear();
                }
                KeyCode::Char('l' | 'L') => self.load(),
                _ => {}
            },
        }
        false
    }

    pub fn lines(&self) -> Vec<String> {
        let mut lines = vec!["ENCRYPTED CONFIGURATION BACKUP — owner access required".into()];
        match self.mode {
            'a' => {
                lines.push("OWNER REAUTHENTICATION".into());
                lines.push("Current administrator password>".into());
                lines.push("*".repeat(self.input.chars().count()));
                lines.push("Operations may disconnect this terminal while services stop. Reconnect after completion.".into());
                lines.push("Enter authorizes this reviewed operation; Esc cancels.".into());
            }
            'c' | 'd' => {
                lines.push(
                    "CREATE BACKUP — settings and identities; blockchain data excluded".into(),
                );
                lines.push(format!(
                    "Destination: {}",
                    self.plan["destination"].as_str().unwrap_or("")
                ));
                lines.push(
                    "Keep the passphrase separately. Losing it makes the backup unusable.".into(),
                );
                lines.push(
                    if self.mode == 'c' {
                        "Passphrase (16+ characters)>"
                    } else {
                        "Repeat passphrase>"
                    }
                    .into(),
                );
                lines.push("*".repeat(self.input.chars().count()));
                lines.push("Enter continues; Esc cancels without changing files.".into());
            }
            'r' => {
                lines.push(
                    "REVIEW RESTORE — decrypt and verify the backup before any change".into(),
                );
                lines.push("Backup passphrase>".into());
                lines.push("*".repeat(self.input.chars().count()));
                lines.push("Enter verifies; Esc cancels.".into());
            }
            'o' => {
                lines.push(
                    "RESTORE REVIEW — current settings and identities will be replaced".into(),
                );
                lines.push(format!(
                    "Created {} | {} files",
                    self.plan["created_utc"], self.plan["files"]
                ));
                lines.push(
                    "Preserves device TLS plus P2P, Electrum and RPC onion identities.".into(),
                );
                lines.push("Blockchain data and Core/electrs downgrade are excluded.".into());
                lines.push(format!("Type exactly: {RESTORE_CONFIRMATION}"));
                lines.push(format!("> {}", self.input));
                lines.push("Enter accepts this review; Esc cancels.".into());
            }
            'p' => {
                lines.push("FINAL RESTORE AUTHENTICATION".into());
                lines.push("Backup passphrase again>".into());
                lines.push("*".repeat(self.input.chars().count()));
                lines.push("Enter restores and restarts services; Esc cancels.".into());
            }
            'x' => {
                lines.push("RECOVER INTERRUPTED RESTORE".into());
                lines.push("This restores the local pre-change rollback snapshot. Blockchain data is untouched.".into());
                lines.push("Enter recovers; Esc cancels.".into());
            }
            _ => {
                lines.push("C create | R review restore | X interrupted restore recovery | L refresh | Esc back".into());
                lines.push(format!(
                    "Backup file: {} | {}",
                    if self.state["exists"] == true {
                        "present"
                    } else {
                        "absent"
                    },
                    self.state["destination"]
                        .as_str()
                        .unwrap_or("/boot/firmware/justverify-backup.jvb")
                ));
                lines.push(format!(
                    "Restore state: {}",
                    self.state["restore_phase"].as_str().unwrap_or("unknown")
                ));
                lines.push("Includes settings, TLS identity, client authorization records and Tor identities.".into());
                lines.push("Does not include blockchain data, wallet private keys, logs, setup tokens or sessions.".into());
            }
        }
        if self.pending.is_some() {
            lines
                .push("Working... do not power off. Passphrases are never logged or saved.".into());
        }
        lines.push(self.message.clone());
        lines.into_iter().map(|line| clean(&line)).collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn secrets_are_masked_and_escape_clears_them() {
        let mut page = BackupPage {
            mode: 'c',
            plan: json!({"destination":"/test"}),
            ..Default::default()
        };
        for character in "abcdefghijklmnop".chars() {
            page.key(KeyCode::Char(character));
        }
        let display = page.lines().join("\n");
        assert!(display.contains("****************"));
        assert!(!display.contains("abcdefghijklmnop"));
        assert!(!page.key(KeyCode::Esc));
        assert!(page.input.is_empty() && page.first_passphrase.is_empty());
    }

    #[test]
    fn wrong_restore_phrase_never_starts_request() {
        let mut page = BackupPage {
            mode: 'o',
            plan: json!({"token":"test"}),
            ..Default::default()
        };
        for character in "RESTORE".chars() {
            page.key(KeyCode::Char(character));
        }
        page.key(KeyCode::Enter);
        assert!(page.pending.is_none());
        assert!(page.message.contains("No restore requested"));
    }
}
