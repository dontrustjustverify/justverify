//! Compact node overview, independently implemented from the user's terminal reference.
use crate::{Snapshot, clean, field, now};
use ratatui::{
    Frame,
    layout::{Constraint, Direction, Layout, Rect},
    style::{Color, Style},
    widgets::{Block, Paragraph, Wrap},
};
use serde_json::Value;
fn value(v: &Value) -> String {
    if v.is_null() {
        "N/A".into()
    } else {
        clean(
            v.as_str()
                .map(str::to_owned)
                .unwrap_or_else(|| v.to_string())
                .as_str(),
        )
    }
}
fn pane(f: &mut Frame, area: Rect, title: &str, lines: Vec<String>, mono: bool) {
    let style = if mono {
        Style::default()
    } else {
        Style::default().fg(Color::Gray).bg(Color::Black)
    };
    let border = if mono {
        Style::default()
    } else {
        Style::default().fg(Color::Cyan)
    };
    f.render_widget(
        Paragraph::new(lines.join("\n"))
            .style(style)
            .block(
                Block::bordered()
                    .title(title.to_owned())
                    .border_style(border),
            )
            .wrap(Wrap { trim: false }),
        area,
    );
}
fn usage_bar(value: f64) -> String {
    let filled = ((value.clamp(0.0, 100.0) / 100.0) * 10.0).round() as usize;
    format!("{}{}", "█".repeat(filled), "░".repeat(10 - filled))
}
pub fn draw(f: &mut Frame, s: &Snapshot, mono: bool) {
    let area = f.area();
    let fields = |m: &str, k| {
        if s.rpc.get(m).is_none_or(|sample| sample.updated == 0) {
            "대기".into()
        } else {
            field(s, m, k)
        }
    };
    let age = now().saturating_sub(s.rpc.get("getblockchaininfo").map_or(0, |x| x.updated));
    let online = age <= 15
        && s.rpc
            .get("getblockchaininfo")
            .is_some_and(|x| x.error.is_none());
    let mut chain = vec![
        format!(
            "{} | {}",
            fields("getnetworkinfo", "subversion"),
            fields("getblockchaininfo", "chain")
        ),
        format!(
            "블록 {} / 헤더 {}",
            fields("getblockchaininfo", "blocks"),
            fields("getblockchaininfo", "headers")
        ),
        format!(
            "IBD {} | 검증 {}",
            fields("getblockchaininfo", "initialblockdownload"),
            fields("getblockchaininfo", "verificationprogress")
        ),
        format!(
            "체인 {} B | prune {}",
            fields("getblockchaininfo", "size_on_disk"),
            fields("getblockchaininfo", "pruned")
        ),
        format!(
            "Core {} | 수집 {}초 전",
            if online {
                "연결됨"
            } else {
                "연결 안 됨 / STALE"
            },
            age
        ),
    ];
    if !online {
        chain.insert(
            0,
            "Core 연결 안 됨 · S 기기 설정에서 초기 설정 / L 진단".into(),
        );
    }
    let network = vec![
        format!(
            "피어 {} | in {} / out {}",
            fields("getnetworkinfo", "connections"),
            fields("getnetworkinfo", "connections_in"),
            fields("getnetworkinfo", "connections_out")
        ),
        format!(
            "수신 {} B / 송신 {} B",
            fields("getnettotals", "totalbytesrecv"),
            fields("getnettotals", "totalbytessent")
        ),
        format!(
            "mempool {} tx / {} vB",
            fields("getmempoolinfo", "size"),
            fields("getmempoolinfo", "bytes")
        ),
        format!(
            "메모리 {} / {} B",
            fields("getmempoolinfo", "usage"),
            fields("getmempoolinfo", "maxmempool")
        ),
        format!(
            "6블록 추정 {} sat/vB",
            crate::display_fee(s, "estimatesmartfee", "feerate")
        ),
        format!(
            "최저 {} / relay {} sat/vB",
            crate::display_fee(s, "getmempoolinfo", "mempoolminfee"),
            crate::display_fee(s, "getmempoolinfo", "minrelaytxfee")
        ),
    ];
    let mut blocks = Vec::new();
    if let Some(recent) = s.rpc.get("recentblocks") {
        if recent.error.is_some() || now().saturating_sub(recent.updated) > 15 {
            blocks.push("STALE: 현재 블록 상태를 확인할 수 없습니다".into());
        }
        for b in recent.value.as_array().into_iter().flatten() {
            let hash = value(&b["hash"]);
            blocks.push(format!(
                "#{}  ·  {} (추정)",
                value(&b["height"]),
                b["miner"]["name"]
                    .as_str()
                    .map(crate::clean)
                    .unwrap_or_else(|| "알 수 없음".into())
            ));
            blocks.push(format!(
                "{} tx · {}초 전 · {}",
                value(&b["nTx"]),
                now().saturating_sub(b["time"].as_u64().unwrap_or(now())),
                hash.chars().take(12).collect::<String>()
            ));
            blocks.push(String::new());
        }
    }
    if blocks.is_empty() {
        blocks.push("블록 정보를 기다리고 있습니다.".into());
    }
    let mut peers = vec!["방향  연결 주소 / 클라이언트".into()];
    if let Some(p) = s.rpc.get("getpeerinfo") {
        if p.error.is_some() || now().saturating_sub(p.updated) > 15 {
            peers.push("STALE: 이전 피어 정보".into());
        }
        for p in p.value.as_array().into_iter().flatten().take(5) {
            peers.push(format!(
                "{} {}",
                if p["inbound"] == true { "IN " } else { "OUT" },
                value(&p["addr"])
            ));
            peers.push(format!("    {}", value(&p["subver"])));
        }
    }
    let cpu = s.host["cpu_percent"]
        .as_str()
        .and_then(|x| x.parse::<f64>().ok())
        .unwrap_or(0.0);
    let system = vec![
        format!(
            "CPU [{}] {}%",
            usage_bar(cpu),
            value(&s.host["cpu_percent"])
        ),
        format!(
            "CPU {}% | RAM {} / {} MiB",
            value(&s.host["cpu_percent"]),
            value(&s.host["used_memory_mib"]),
            value(&s.host["total_memory_mib"])
        ),
        format!(
            "가동 {}초 | swap {} MiB",
            value(&s.host["uptime"]),
            value(&s.host["swap_mib"])
        ),
        format!(
            "electrs {} / 높이 {}",
            value(&s.host["electrs"]["state"]),
            value(&s.host["electrs"]["height"])
        ),
        format!("Tor {}", value(&s.host["tor"]["state"])),
        format!("I2P {}", value(&s.host["i2p"]["state"])),
    ];
    let rows = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(3),
            Constraint::Min(1),
            Constraint::Length(3),
        ])
        .split(area);
    pane(
        f,
        rows[0],
        " JustVerify / 비트코인코어 ",
        vec![format!(
            "{}  |  실시간 노드 현황",
            value(&s.host["hostname"])
        )],
        mono,
    );
    if area.width >= 90 && area.height >= 30 {
        let columns = Layout::default()
            .direction(Direction::Horizontal)
            .constraints([Constraint::Percentage(52), Constraint::Percentage(48)])
            .split(rows[1]);
        let left = Layout::default()
            .constraints([Constraint::Length(8), Constraint::Min(1)])
            .split(columns[0]);
        let right = Layout::default()
            .constraints([
                Constraint::Length(8),
                Constraint::Min(5),
                Constraint::Length(7),
            ])
            .split(columns[1]);
        pane(f, left[0], " 노드 요약 ", chain, mono);
        pane(f, left[1], " 최근 블록 ", blocks, mono);
        pane(f, right[0], " 네트워크 · Mempool · 수수료 ", network, mono);
        pane(f, right[1], " 피어 요약 [P 전체 목록] ", peers, mono);
        pane(f, right[2], " 시스템 · 서비스 ", system, mono);
    } else {
        let sections = Layout::default()
            .constraints([
                Constraint::Length(6),
                Constraint::Length(4),
                Constraint::Min(4),
                Constraint::Length(4),
            ])
            .split(rows[1]);
        pane(
            f,
            sections[0],
            " 노드 요약 ",
            chain.into_iter().take(4).collect(),
            mono,
        );
        pane(
            f,
            sections[1],
            " 네트워크 · Mempool ",
            network.into_iter().skip(2).take(2).collect(),
            mono,
        );
        pane(f, sections[2], " 최근 블록 ", blocks, mono);
        pane(
            f,
            sections[3],
            " 시스템 · 서비스 ",
            vec![
                format!(
                    "CPU [{}] {}%",
                    usage_bar(cpu),
                    value(&s.host["cpu_percent"])
                ),
                format!(
                    "electrs {} / Tor {}",
                    value(&s.host["electrs"]["state"]),
                    value(&s.host["tor"]["state"])
                ),
            ],
            mono,
        );
    }
    pane(
        f,
        rows[2],
        " 메뉴 ",
        vec![if area.width < 65 {
            "V 버전  M 정책  P 피어  C 지갑  S 설정".into()
        } else {
            "비트코인코어: V 버전 · M 정책 · P 피어  |  C 지갑 연결  |  S 기기 설정  |  Esc 현황"
                .into()
        }],
        mono,
    );
}
