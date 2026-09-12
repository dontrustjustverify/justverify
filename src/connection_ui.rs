use serde_json::Value;
#[derive(Default)]
pub struct ElectrumQr {
    value: Value,
    error: String,
    lan: bool,
}
impl ElectrumQr {
    pub fn load(&mut self) {
        self.load_mode(false);
    }
    pub fn load_lan(&mut self) {
        self.load_mode(true);
    }
    fn load_mode(&mut self, lan: bool) {
        self.lan = lan;
        self.value = Value::Null;
        self.error = "Selected Electrum endpoint unavailable".into();
        let mut command = std::process::Command::new("/opt/justverify/venv/bin/python");
        command.arg("/opt/justverify/web/electrum_qr.py");
        if lan {
            command.arg("--lan");
        }
        if let Ok(output) = command.output() {
            if let Ok(reply) = serde_json::from_slice::<Value>(&output.stdout) {
                if reply["ok"] == true {
                    self.value = reply["result"].clone();
                    self.error.clear();
                }
            }
        }
    }
    pub fn lines(&self, width: u16, height: u16) -> Vec<String> {
        let mut lines = vec![format!(
            "{} ELECTRUM — L LAN/TLS | T Tor | Esc back",
            if self.lan { "LAN" } else { "TOR" }
        )];
        if self.value.is_null() {
            lines.push(self.error.clone());
            return lines;
        }
        lines.push(self.value["payload"].as_str().unwrap_or("").into());
        if self.lan {
            lines.push("Electrum TLS port 50002. Select SSL/TLS in the wallet.".into());
            lines.push("Trust the device certificate; do not disable verification.".into());
            let fingerprint = self.value["certificate_sha256"].as_str().unwrap_or("");
            lines.push(format!(
                "Certificate SHA256: {}",
                fingerprint.get(..32).unwrap_or("")
            ));
            lines.push(format!(
                "                    {}",
                fingerprint.get(32..).unwrap_or("")
            ));
        } else {
            lines.push("Electrum TCP over Tor; TLS: no. No RPC credentials.".into());
            lines.push("Use a Tor SOCKS proxy on the wallet device.".into());
        }
        lines.push("Address text only; app auto-import/camera not verified.".into());
        let Some(matrix) = self.value["matrix"].as_array() else {
            return lines;
        };
        let size = matrix.len();
        if usize::from(width) < size + 2 || usize::from(height) < size.div_ceil(2) + lines.len() + 2
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
        lines
    }
}
