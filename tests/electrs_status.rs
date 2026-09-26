use justverify::{
    Sample, Snapshot,
    electrs_status::{Status, parse_metrics},
};
use serde_json::{Value, json};

fn sample(value: Value) -> Sample {
    Sample {
        value,
        updated: 100,
        error: None,
    }
}
fn core() -> Snapshot {
    let mut s = Snapshot::default();
    s.rpc.insert(
        "getblockchaininfo".into(),
        sample(json!({"blocks":100,"bestblockhash":"tip","initialblockdownload":false})),
    );
    s
}
#[test]
fn readiness_requires_functional_index_and_matching_fresh_tip() {
    let mut status = Status::default();
    status.progress = sample(json!({"height":100,"db_error":false}));
    status.electrum = sample(json!({"height":100,"tip":"tip","index_ready":false}));
    assert_eq!(status.view(&core(), 50001, 101)["state"], "FINALIZING");
    status.electrum.value["index_ready"] = json!(true);
    assert_eq!(status.view(&core(), 50001, 101)["state"], "READY");
    status.electrum.value["tip"] = json!("different-chain");
    assert_eq!(status.view(&core(), 50001, 101)["wallet_ready"], false);
    status.electrum.value["tip"] = json!("tip");
    assert_eq!(status.view(&core(), 50001, 116)["wallet_ready"], false);
    status.progress.value["db_error"] = json!(true);
    assert_eq!(status.view(&core(), 50001, 101)["state"], "INDEX_ERROR");
}
#[test]
fn timeout_retains_height_with_age_and_does_not_hide_real_outage() {
    let mut status = Status::default();
    status.progress = sample(json!({"height":42,"db_error":false}));
    status.electrum.error = Some("Electrum response delayed".into());
    let v = status.view(&core(), 50001, 101);
    assert_eq!(v["state"], "INDEXING");
    assert_eq!(v["height"], 42);
    assert_eq!(v["wallet_ready"], false);
    status.progress.error = Some("Index metrics unavailable".into());
    let v = status.view(&core(), 50001, 110);
    assert_eq!(v["state"], "STALE");
    assert_eq!(v["height"], 42);
    assert_eq!(v["height_updated"], 100);
    assert_eq!(v["height_stale"], true);
    status.electrum.error = Some("Electrum connection unavailable".into());
    assert_eq!(status.view(&core(), 50001, 110)["state"], "UNAVAILABLE");
    // A restart/reindex can legitimately lower the observed height.
    status.progress = sample(json!({"height":3,"db_error":false}));
    assert_eq!(status.view(&core(), 50001, 110)["height"], 3);
}
#[test]
fn progress_validation_rejects_invalid_duplicate_or_missing_gauges() {
    assert_eq!(
        parse_metrics("electrs_index_height{type=\"tip\"} 123\n").unwrap()["height"],
        123
    );
    for value in ["NaN", "inf", "-1", "1.5", "4294967296"] {
        assert!(parse_metrics(&format!("electrs_index_height{{type=\"tip\"}} {value}\n")).is_err());
    }
    assert!(
        parse_metrics(
            "electrs_index_height{type=\"tip\"} 1\nelectrs_index_height{type=\"tip\"} 2\n"
        )
        .is_err()
    );
    assert!(parse_metrics("# no index yet\n").is_err());
}

#[test]
fn unknown_target_is_not_complete_and_ibd_uses_headers() {
    let mut status = Status::default();
    status.progress = sample(json!({"height":0,"db_error":false}));
    let mut chain = core();
    chain.rpc.get_mut("getblockchaininfo").unwrap().value =
        json!({"blocks":0,"headers":0,"initialblockdownload":true});
    let view = status.view(&chain, 50001, 101);
    assert_eq!(view["state"], "CORE_SYNCING");
    assert!(!justverify::electrs_status::progress_text(&view).contains("100"));
    chain.rpc.get_mut("getblockchaininfo").unwrap().value =
        json!({"blocks":50,"headers":100,"initialblockdownload":true});
    status.progress.value["height"] = json!(50);
    let view = status.view(&chain, 50001, 101);
    assert_eq!(view["target_height"], 100);
    assert_eq!(view["state"], "CORE_SYNCING");
    assert_eq!(
        justverify::electrs_status::progress_text(&view),
        "50.00% (50/100)"
    );
    assert_eq!(view["wallet_ready"], false);
}

#[test]
fn verified_rpc_tip_overrides_older_metrics_and_headers_after_ibd() {
    let mut chain = core();
    chain.rpc.get_mut("getblockchaininfo").unwrap().value["headers"] = json!(101);
    let mut status = Status::default();
    status.progress = sample(json!({"height":99,"db_error":false}));
    status.electrum = sample(json!({"height":100,"tip":"tip","index_ready":true}));
    status.electrum.updated = 101;
    let view = status.view(&chain, 50001, 102);
    assert_eq!(view["state"], "READY");
    assert_eq!(view["height"], 100);
    assert_eq!(view["target_height"], 100);
    assert_eq!(
        justverify::electrs_status::progress_text(&view),
        "100.00% (100/100)"
    );
    status.electrum.value["tip"] = json!("fork");
    assert_ne!(status.view(&chain, 50001, 102)["state"], "READY");
    status.electrum.value["tip"] = json!("tip");
    status.electrum.error = Some("Electrum response delayed".into());
    assert_ne!(status.view(&chain, 50001, 102)["state"], "READY");
}

#[test]
fn dead_listener_is_not_hidden_by_live_metrics_or_existing_connection() {
    let mut status = Status::default();
    status.progress = sample(json!({"height":99,"db_error":false}));
    status.electrum.error = Some("Electrum connection unavailable".into());
    assert_eq!(status.view(&core(), 50003, 101)["state"], "UNAVAILABLE");
    status.runtime =
        sample(json!({"listener_error":true,"resource_error":true,"phase":"compacting"}));
    assert_eq!(status.view(&core(), 50003, 101)["state"], "RESOURCE_ERROR");
    status.electrum = sample(json!({"height":100,"tip":"tip","index_ready":true}));
    assert_eq!(status.view(&core(), 50003, 101)["wallet_ready"], false);
    status.runtime.value["resource_error"] = json!(false);
    assert_eq!(
        status.view(&core(), 50003, 101)["state"],
        "CONNECTION_ERROR"
    );
    status.runtime.value = json!({"phase":"compacting","compaction":"funding"});
    status.electrum.error = Some("Electrum response delayed".into());
    assert_eq!(status.view(&core(), 50003, 101)["state"], "FINALIZING");
    assert_eq!(status.view(&core(), 50003, 101)["compaction"], "funding");
    status.runtime.updated = 80;
    assert_eq!(status.view(&core(), 50003, 101)["state"], "INDEXING");
}

#[test]
fn whole_db_work_is_separate_from_height_and_catchup_is_not_ready() {
    let mut status = Status::default();
    status.progress = sample(json!({"height":99,"db_error":false}));
    status.electrum.error = Some("Electrum response delayed".into());
    status.runtime = sample(
        json!({"running":true,"phase":"compacting","compaction":"spending",
        "compaction_progress":{"basis":"estimated_records","percent_basis_points":6400,"complete":false}}),
    );
    let view = status.view(&core(), 50003, 101);
    assert_eq!(view["state"], "FINALIZING");
    assert_eq!(view["height"], 99);
    assert_eq!(view["compaction_percent_basis_points"], 6400);
    assert_eq!(justverify::electrs_status::progress_text(&view), "~64.00%");
    assert_eq!(justverify::electrs_status::state_text(&view), "DB 정리 중");
    for invalid in [json!(10000), json!(-1), json!("6400"), Value::Null] {
        status.runtime.value["compaction_progress"]["percent_basis_points"] = invalid;
        assert!(status.view(&core(), 50003, 101)["compaction_percent_basis_points"].is_null());
    }
    status.runtime.value["compaction_progress"]["percent_basis_points"] = json!(6400);
    assert!(status.view(&core(), 50003, 116)["compaction_percent_basis_points"].is_null());
    status.runtime.value["phase"] = json!("indexing");
    status.runtime.value["compacted"] = json!(true);
    let view = status.view(&core(), 50003, 101);
    assert_eq!(view["state"], "CATCHING_UP");
    assert_eq!(view["wallet_ready"], false);
    assert!(view["compaction_percent_basis_points"].is_null());
    status.electrum = sample(json!({"height":100,"tip":"tip","index_ready":true}));
    let view = status.view(&core(), 50003, 101);
    assert_eq!(view["state"], "READY");
    assert_eq!(
        justverify::electrs_status::progress_text(&view),
        "100.00% (100/100)"
    );
}

#[test]
fn block_details_require_actual_ibd_completion_and_caught_up_headers() {
    use justverify::collector::details_ready;
    assert!(!details_ready(
        &json!({"blocks":99,"headers":100,"initialblockdownload":false,"verificationprogress":0.99999999})
    ));
    assert!(!details_ready(
        &json!({"blocks":100,"headers":100,"initialblockdownload":true,"verificationprogress":1})
    ));
    assert!(!details_ready(&json!({"initialblockdownload":false})));
    assert!(details_ready(
        &json!({"blocks":100,"headers":100,"initialblockdownload":false})
    ));
}
