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
    assert_eq!(status.view(&core(), 50001, 101)["state"], "INDEXING");
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
