use crate::{Snapshot, clean, main_lines, policy::Values};
use anyhow::{Context, Result, bail};
use crossterm::event::{self, Event, KeyCode, KeyModifiers};
use ratatui::{
    style::{Color, Style},
    widgets::{Block, Paragraph, Wrap},
};
use serde_json::{Value, json};
use std::{
    io::{Read, Write},
    os::unix::net::UnixStream,
    path::Path,
    time::Duration,
};
pub(crate) fn request(socket: &Path, value: &Value) -> Result<Value> {
    request_with_timeout(socket, value, Duration::from_secs(50))
}
pub(crate) fn request_with_timeout(
    socket: &Path,
    value: &Value,
    timeout: Duration,
) -> Result<Value> {
    let mut stream = UnixStream::connect(socket).context("management service unavailable")?;
    stream.set_read_timeout(Some(timeout))?;
    stream.set_write_timeout(Some(Duration::from_secs(2)))?;
    stream.write_all(format!("{}\n", value).as_bytes())?;
    let mut bytes = Vec::new();
    stream.take(2 * 1024 * 1024).read_to_end(&mut bytes)?;
    let reply: Value = serde_json::from_slice(&bytes)?;
    if reply["ok"] != true {
        bail!(
            "{}",
            clean(reply["error"].as_str().unwrap_or("policy service failed"))
        );
    }
    Ok(reply["result"].clone())
}
fn snapshot(socket: &Path) -> Result<Snapshot> {
    let mut stream = UnixStream::connect(socket)?;
    stream.set_read_timeout(Some(Duration::from_secs(3)))?;
    stream.write_all(b"snapshot\n")?;
    let mut bytes = Vec::new();
    stream.take(2 * 1024 * 1024).read_to_end(&mut bytes)?;
    Ok(serde_json::from_slice(&bytes)?)
}
#[derive(Default)]
struct Editor {
    state: Value,
    values: Values,
    selected: usize,
    input: Option<String>,
    preview: Value,
    message: String,
}
impl Editor {
    fn load(&mut self, socket: &Path) -> Result<()> {
        self.state = request(socket, &json!({"method":"state"}))?;
        self.values = serde_json::from_value(self.state["requested"].clone())?;
        self.input = None;
        Ok(())
    }
    fn entries(&self) -> &[Value] {
        self.state["entries"]
            .as_array()
            .map(Vec::as_slice)
            .unwrap_or(&[])
    }
    fn key(&self) -> Option<String> {
        self.entries()
            .get(self.selected)
            .and_then(|v| v["key"].as_str())
            .map(str::to_owned)
    }
    fn lines(&self, height: u16) -> Vec<String> {
        let mut lines = vec![
            format!(
                "MEMPOOL / RELAY / NETWORK | Core {} | {}",
                self.state["version"], self.state["network"]
            ),
            "Up/Down select | Enter edit | D default | A review | R recovery | Esc back".into(),
            "Fee input: sat/vB; defaults below: Core native units. Changes are staged.".into(),
        ];
        if self.state["transaction"]["needs_recovery"] == true {
            lines.push(
                "INTERRUPTED CHANGE: press R to review recovery before applying more changes."
                    .into(),
            );
        }
        let count = usize::from(height.saturating_sub(11)).max(1);
        let start = self.selected.saturating_sub(count.saturating_sub(1));
        for (i, entry) in self.entries().iter().enumerate().skip(start).take(count) {
            let key = entry["key"].as_str().unwrap_or("");
            lines.push(format!(
                "{} {:24} {:14} default {}{}",
                if i == self.selected { ">" } else { " " },
                key,
                self.values
                    .get(key)
                    .map(String::as_str)
                    .unwrap_or("[default]"),
                entry["default"].as_str().unwrap_or("N/A"),
                if entry["ignored_or_wallet_only"] == true {
                    " [read-only]"
                } else {
                    ""
                }
            ));
        }
        if let Some(entry) = self.entries().get(self.selected) {
            let range = match (
                entry["range"]["min"].as_i64(),
                entry["range"]["max"].as_i64(),
            ) {
                (Some(min), Some(max)) => format!("Accepted {min}..{max} | "),
                _ => String::new(),
            };
            lines.push(format!(
                "{range}{}: {}",
                entry["unit"].as_str().unwrap_or(""),
                clean(entry["description"].as_str().unwrap_or(""))
            ));
        }
        if let Some(input) = &self.input {
            lines.push(format!("VALUE> {input}  [Enter stage; Esc cancel]"));
        }
        lines.push(self.message.clone());
        lines
    }
}
pub fn run(socket: &Path, policy_socket: &Path, no_color: bool) -> Result<()> {
    let mut terminal = ratatui::init();
    let mut page = ' ';
    let mut scroll = 0u16;
    let mut editor = Editor::default();
    let mut electrum_qr = crate::connection_ui::ElectrumQr::default();
    let mut clients = crate::client_ui::ClientsPage::default();
    let mut storage = crate::storage_ui::StoragePage::default();
    let mut backup = crate::backup_ui::BackupPage::default();
    let mut versions = crate::version_ui::VersionsPage::default();
    let version_socket = Path::new("/run/justverify-versions/control.sock");
    let result = (|| -> Result<()> {
        loop {
            let size = terminal.size()?;
            let overview = if page == ' ' {
                snapshot(socket).ok()
            } else {
                None
            };
            let lines = if page == 'h' {
                vec![
                    "기기 설정".into(),
                    "".into(),
                    "S 저장장치 · 노드 초기 설정".into(),
                    "B 백업 · 복구".into(),
                    "L 서비스 진단".into(),
                    "Esc 비트코인코어".into(),
                ]
            } else if page == 'q' {
                electrum_qr.lines(size.width, size.height)
            } else if page == 'c' {
                clients.lines(size.width, size.height)
            } else if page == 's' {
                {
                    storage.poll();
                    storage.lines(size.height)
                }
            } else if page == 'b' {
                backup.poll();
                backup.lines()
            } else if page == 'v' {
                if let Ok(state) = request(version_socket, &json!({"method":"state"})) {
                    versions.state = state;
                }
                versions.lines(size.height)
            } else if page == 'j' {
                vec!["RECOVER INTERRUPTED VERSION CHANGE — Enter recovers; Esc cancels".into(),
                    format!("Phase: {} | target Core {}",versions.state["transition"]["phase"],versions.state["transition"]["target"]["instance"]["core_version"]),
                    format!("Previous Core {} | network {}",versions.state["transition"]["previous"]["instance"]["core_version"],versions.state["transition"]["previous"]["instance"]["network"]),
                    "Recovery restarts the previous binary with its separate data. Target data is preserved.".into(),
                    "If there was no previous profile, recovery leaves node services stopped.".into(), versions.message.clone()]
            } else if page == 'w' {
                vec!["REVIEW VERSION CHANGE — Enter applies; Esc cancels".into(),
                     format!("Core {} | network {} | mode {}",versions.preview["preview"]["target"]["instance"]["core_version"],versions.network,if versions.watch_only {"watch-only"} else {"node"}),
                     clean(versions.preview["preview"]["explanation"].as_str().unwrap_or("")),
                     "Core and electrs restart together. Full synchronization may take substantial time and disk space.".into(),versions.message.clone()]
            } else if page == 'm' {
                editor.lines(size.height)
            } else if page == 'r' {
                vec![
                    "RECOVER INTERRUPTED POLICY CHANGE".into(),
                    "Restore the previous configuration and restart the same Core binary.".into(),
                    "Node data is preserved. Binary/profile changes block this recovery.".into(),
                    "Enter recovers; Esc cancels.".into(),
                ]
            } else if page == 'a' {
                let mut lines = vec![
                    "REVIEW POLICY CHANGE — Enter applies and restarts Core; Esc cancels".into(),
                ];
                if let Some(changes) = editor.preview["plan"]["changes"].as_array() {
                    lines.extend(changes.iter().map(|v| clean(v.as_str().unwrap_or(""))));
                }
                lines.push(
                    "Preflight: actual isolated Core startup and observable values checked.".into(),
                );
                lines.push(
                    "Other policy effects require behavior evidence; this is local relay policy."
                        .into(),
                );
                lines.push(editor.message.clone());
                lines
            } else {
                match snapshot(socket) {
                    Ok(s) => match page {
                        'p' => s
                            .rpc
                            .get("getpeerinfo")
                            .and_then(|x| x.value.as_array())
                            .map(|peers| {
                                peers
                                    .iter()
                                    .map(|p| {
                                        format!(
                                            "{} {} {}",
                                            clean(&p["addr"].to_string()),
                                            clean(&p["subver"].to_string()),
                                            p["inbound"]
                                        )
                                    })
                                    .collect()
                            })
                            .unwrap_or_else(|| vec!["Peers N/A".into()]),
                        'l' => s
                            .rpc
                            .iter()
                            .map(|(name, x)| {
                                format!(
                                    "{name}: {} @{}",
                                    x.error.as_deref().unwrap_or("OK"),
                                    x.updated
                                )
                            })
                            .collect(),
                        'e' => vec![
                            format!("Electrs: {}", s.host["electrs"]),
                            format!("Tor: {}", s.host["tor"]),
                            "RPC: internal cookie, loopback only".into(),
                            "Wallet LAN/Tor provisioning: not configured".into(),
                        ],
                        _ => main_lines(&s),
                    },
                    Err(_) => vec![
                        "JustVerify | management daemon UNAVAILABLE".into(),
                        "비트코인코어: V 버전 | S 기기 설정 | C 지갑 연결 | Esc 현황 | Ctrl-C 종료"
                            .into(),
                    ],
                }
            };
            terminal.draw(|frame| {
                if let Some(s) = &overview {
                    crate::dashboard::draw(frame, s, no_color);
                    return;
                }
                let style = if page == 'q' || (page == 'c' && clients.is_qr()) {
                    Style::default().fg(Color::Black).bg(Color::White)
                } else if no_color {
                    Style::default()
                } else {
                    Style::default().fg(Color::Cyan).bg(Color::Black)
                };
                frame.render_widget(
                    Paragraph::new(lines.join("\n"))
                        .style(style)
                        .block(Block::bordered().title(match page {
                            'v' | 'j' | 'w' => " JustVerify / 비트코인코어 / 버전 ",
                            'p' => " JustVerify / 비트코인코어 / 피어 ",
                            'm' | 'a' | 'r' => " JustVerify / 비트코인코어 / 정책 ",
                            'c' | 'q' => " JustVerify / 지갑 연결 ",
                            's' | 'h' | 'b' | 'l' => " JustVerify / 기기 설정 ",
                            _ => " JustVerify / 비트코인코어 ",
                        }))
                        .wrap(Wrap { trim: false })
                        .scroll((scroll, 0)),
                    frame.area(),
                );
            })?;
            if !event::poll(Duration::from_secs(2))? {
                continue;
            }
            let Event::Key(key) = event::read()? else {
                continue;
            };
            if key.code == KeyCode::Char('c') && key.modifiers.contains(KeyModifiers::CONTROL) {
                break;
            }
            // Function keys are navigation, never text inserted into an editor.
            if let KeyCode::F(n) = key.code {
                match n {
                    1 => page = ' ',
                    2 => {
                        page = 'v';
                        if let Err(e) = versions.load(version_socket) {
                            versions.message = clean(&e.to_string());
                        }
                    }
                    3 => {
                        page = 'm';
                        if let Err(e) = editor.load(policy_socket) {
                            editor.message = clean(&e.to_string());
                        }
                    }
                    4 => page = 'p',
                    5 => {
                        page = 'c';
                        clients.load();
                    }
                    6 => page = 'h',
                    7 => {
                        page = 'q';
                        electrum_qr.load();
                    }
                    8 => {
                        page = 's';
                        storage.load();
                    }
                    9 => {
                        page = 'b';
                        backup.load();
                    }
                    10 => page = 'l',
                    _ => {}
                }
                scroll = 0;
                continue;
            }
            if page == 'q' {
                if matches!(key.code, KeyCode::Char('l' | 'L')) {
                    electrum_qr.load_lan();
                }
                if matches!(key.code, KeyCode::Char('t' | 'T')) {
                    electrum_qr.load();
                }
                if key.code == KeyCode::Esc {
                    page = ' ';
                }
                continue;
            }
            if page == 'c' {
                if clients.is_menu() && matches!(key.code, KeyCode::Char('q' | 'Q')) {
                    page = 'q';
                    scroll = 0;
                    electrum_qr.load();
                    continue;
                }
                if clients.is_menu()
                    && (key.code == KeyCode::Char('e') || key.code == KeyCode::Char('E'))
                {
                    page = 'e';
                    continue;
                }
                if clients.key(key.code) {
                    page = ' ';
                    scroll = 0;
                }
                continue;
            }
            if page == 's' {
                if storage.key(key.code) {
                    page = ' ';
                    scroll = 0;
                }
                continue;
            }
            if page == 'b' {
                if backup.key(key.code) {
                    page = ' ';
                    scroll = 0;
                }
                continue;
            }
            if page == 'v' || page == 'w' || page == 'j' {
                if page == 'j' {
                    match key.code {
                        KeyCode::Esc => page = 'v',
                        KeyCode::Enter => {
                            versions.message =
                                match request(version_socket, &json!({"method":"recover"})) {
                                    Ok(value) => format!("Recovery result: {}", value["phase"]),
                                    Err(error) => clean(&error.to_string()),
                                };
                            let _ = versions.load(version_socket);
                            page = 'v';
                        }
                        _ => {}
                    }
                } else if page == 'w' {
                    match key.code {
                        KeyCode::Esc => {
                            page = 'v';
                            versions.preview = Value::Null;
                        }
                        KeyCode::Enter => {
                            let result = request(
                                version_socket,
                                &json!({"method":"apply","token":versions.preview["token"]}),
                            );
                            versions.message = match result {
                                Ok(value) => format!("Version result: {}", value["phase"]),
                                Err(error) => clean(&error.to_string()),
                            };
                            let _ = versions.load(version_socket);
                            page = 'v';
                            versions.preview = Value::Null;
                        }
                        _ => {}
                    }
                } else {
                    match key.code {
                        KeyCode::Down => {
                            versions.selected = (versions.selected + 1)
                                .min(versions.entries().len().saturating_sub(1))
                        }
                        KeyCode::Up => versions.selected = versions.selected.saturating_sub(1),
                        KeyCode::Char('r' | 'R') => page = 'j',
                        KeyCode::Char('p' | 'P') => {
                            versions.expanded = !versions.expanded;
                            versions.selected = 0;
                        }
                        KeyCode::Char('n' | 'N') => versions.cycle_network(),
                        KeyCode::Char('w' | 'W') => versions.watch_only = !versions.watch_only,
                        KeyCode::Char('d' | 'D') => {
                            if let Some(version) = versions.version() {
                                versions.message=match request(version_socket,&json!({"method":"download","version":version})) {Ok(_)=>"Official download started; signature verification required.".into(),Err(error)=>clean(&error.to_string())};
                            }
                        }
                        KeyCode::Enter => {
                            if let Some(version) = versions.version() {
                                match request(
                                    version_socket,
                                    &json!({"method":"preview","version":version,"network":versions.network,"watch_only":versions.watch_only}),
                                ) {
                                    Ok(value) => {
                                        versions.preview = value;
                                        versions.message.clear();
                                        page = 'w';
                                    }
                                    Err(error) => versions.message = clean(&error.to_string()),
                                }
                            }
                        }
                        KeyCode::Esc => {
                            page = ' ';
                            scroll = 0;
                        }
                        _ => {}
                    }
                }
                continue;
            }
            if editor.input.is_some() && page == 'm' {
                match key.code {
                    KeyCode::Esc => editor.input = None,
                    KeyCode::Backspace => {
                        editor.input.as_mut().unwrap().pop();
                    }
                    KeyCode::Char(c)
                        if !c.is_control()
                            && !key
                                .modifiers
                                .intersects(KeyModifiers::CONTROL | KeyModifiers::ALT) =>
                    {
                        if editor.input.as_ref().unwrap().len() < 64 {
                            editor.input.as_mut().unwrap().push(c);
                        }
                    }
                    KeyCode::Enter => {
                        if let Some(k) = editor.key() {
                            let input = editor.input.take().unwrap();
                            if input.is_empty() {
                                editor.values.remove(&k);
                            } else {
                                editor.values.insert(k, input);
                            }
                            editor.message = "Staged; press A to validate and review.".into();
                        }
                    }
                    _ => {}
                }
                continue;
            }
            if page == 'r' {
                match key.code {
                    KeyCode::Esc => page = 'm',
                    KeyCode::Enter => {
                        let result = request(policy_socket, &json!({"method":"recover"}));
                        let message = match result {
                            Ok(v) => format!("Recovery result: {}", v["phase"]),
                            Err(e) => clean(&e.to_string()),
                        };
                        let _ = editor.load(policy_socket);
                        editor.message = message;
                        page = 'm';
                    }
                    _ => {}
                }
                continue;
            }
            if page == 'a' {
                match key.code {
                    KeyCode::Esc => {
                        page = 'm';
                        editor.preview = Value::Null;
                    }
                    KeyCode::Enter => {
                        let token = editor.preview["token"]
                            .as_str()
                            .context("missing preview token")?;
                        match request(policy_socket, &json!({"method":"apply","token":token})) {
                            Ok(v) => {
                                editor.message = format!("Configuration result: {}", v["phase"]);
                                let message = editor.message.clone();
                                if let Err(e) = editor.load(policy_socket) {
                                    editor.message = clean(&e.to_string());
                                } else {
                                    editor.message = message;
                                }
                            }
                            Err(e) => editor.message = clean(&e.to_string()),
                        };
                        page = 'm';
                        editor.preview = Value::Null;
                    }
                    _ => {}
                }
                continue;
            }
            if page == 'm' {
                match key.code {
                    KeyCode::Down => {
                        editor.selected =
                            (editor.selected + 1).min(editor.entries().len().saturating_sub(1))
                    }
                    KeyCode::Up => editor.selected = editor.selected.saturating_sub(1),
                    KeyCode::Enter => {
                        if editor
                            .entries()
                            .get(editor.selected)
                            .is_some_and(|v| v["ignored_or_wallet_only"] == true)
                        {
                            editor.message =
                                "This option does not control this node's relay policy.".into();
                        } else if let Some(k) = editor.key() {
                            editor.input = Some(editor.values.get(&k).cloned().unwrap_or_default());
                        }
                    }
                    KeyCode::Char('d' | 'D') => {
                        if let Some(k) = editor.key() {
                            editor.values.remove(&k);
                            editor.message = "Core default staged; press A to review.".into();
                        }
                    }
                    KeyCode::Char('r' | 'R') => {
                        match request(policy_socket, &json!({"method":"state"})) {
                            Ok(state) => {
                                editor.state = state;
                                if editor.state["transaction"]["needs_recovery"] == true {
                                    page = 'r';
                                } else {
                                    editor.message =
                                        "No interrupted change requires recovery.".into();
                                }
                            }
                            Err(e) => editor.message = clean(&e.to_string()),
                        }
                    }
                    KeyCode::Char('a' | 'A') => {
                        match request(
                            policy_socket,
                            &json!({"method":"preview","values":editor.values}),
                        ) {
                            Ok(v) => {
                                editor.preview = v;
                                page = 'a';
                                editor.message.clear();
                            }
                            Err(e) => editor.message = clean(&e.to_string()),
                        }
                    }
                    KeyCode::Esc => {
                        page = ' ';
                        scroll = 0;
                    }
                    _ => {}
                }
                continue;
            }
            match key.code {
                KeyCode::Char('q' | 'Q') => {
                    page = 'q';
                    scroll = 0;
                    electrum_qr.load();
                }
                KeyCode::Char('s' | 'S') => {
                    if page == 'h' {
                        page = 's';
                        storage.load();
                    } else {
                        page = 'h';
                    }
                    scroll = 0;
                }
                KeyCode::Char('b' | 'B') => {
                    page = 'b';
                    scroll = 0;
                    backup.load();
                }
                KeyCode::Char('v' | 'V') => {
                    page = 'v';
                    scroll = 0;
                    if let Err(error) = versions.load(version_socket) {
                        versions.message = clean(&error.to_string());
                    }
                }
                KeyCode::Char('m' | 'M') => {
                    page = 'm';
                    scroll = 0;
                    if let Err(e) = editor.load(policy_socket) {
                        editor.message = clean(&e.to_string());
                    }
                }
                KeyCode::Char('p' | 'P') => {
                    page = 'p';
                    scroll = 0;
                }
                KeyCode::Char('l' | 'L') => {
                    page = 'l';
                    scroll = 0;
                }
                KeyCode::Char('c' | 'C') => {
                    page = 'c';
                    clients.load();
                    scroll = 0;
                }
                KeyCode::Esc => {
                    page = ' ';
                    scroll = 0;
                }
                KeyCode::Down => scroll = scroll.saturating_add(1),
                KeyCode::Up => scroll = scroll.saturating_sub(1),
                _ => {}
            }
        }
        Ok(())
    })();
    ratatui::restore();
    result
}
