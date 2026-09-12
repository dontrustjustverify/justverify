//! Offline, best-effort pool attribution. Coinbase markers do not prove identity.
use serde::Deserialize;
use serde_json::{Value, json};
use std::{collections::BTreeSet, sync::OnceLock};

#[derive(Deserialize)]
struct Pool {
    name: String,
    tags: Vec<String>,
    addresses: Vec<String>,
}

fn pools() -> &'static Vec<Pool> {
    static POOLS: OnceLock<Vec<Pool>> = OnceLock::new();
    POOLS.get_or_init(|| {
        serde_json::from_str(include_str!("../catalog/mining-pools.json"))
            .expect("pinned pool registry")
    })
}

pub fn identify(coinbase: &Value, mainnet: bool) -> Value {
    let Some(hex) = coinbase["vin"][0]["coinbase"].as_str() else {
        return json!({"status":"unavailable"});
    };
    if hex.len() > 200 || hex.len() % 2 != 0 || !hex.is_ascii() {
        return json!({"status":"unavailable"});
    }
    let Ok(script) = (0..hex.len())
        .step_by(2)
        .map(|i| u8::from_str_radix(&hex[i..i + 2], 16))
        .collect::<Result<Vec<_>, _>>()
    else {
        return json!({"status":"unavailable"});
    };
    let mut names = BTreeSet::new();
    let mut methods = BTreeSet::new();
    for pool in pools() {
        if pool
            .tags
            .iter()
            .any(|t| !t.is_empty() && script.windows(t.len()).any(|w| w == t.as_bytes()))
        {
            names.insert(pool.name.as_str());
            methods.insert("coinbase_tag");
        }
        // Registry reward addresses are Bitcoin mainnet addresses. Core 22 reports
        // scriptPubKey.addresses; newer releases report scriptPubKey.address.
        if mainnet
            && coinbase["vout"].as_array().into_iter().flatten().any(|o| {
                let spk = &o["scriptPubKey"];
                pool.addresses.iter().any(|a| {
                    spk["address"].as_str() == Some(a)
                        || spk["addresses"]
                            .as_array()
                            .into_iter()
                            .flatten()
                            .any(|v| v.as_str() == Some(a))
                })
            })
        {
            names.insert(pool.name.as_str());
            methods.insert("reward_address");
        }
    }
    match names.len() {
        0 => json!({"status":"unknown"}),
        1 => {
            json!({"status":"identified","name":crate::clean(names.first().unwrap()),"basis":methods,"inferred":true})
        }
        _ => json!({"status":"ambiguous"}),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn cb(tag: &str) -> Value {
        json!({"vin":[{"coinbase":tag.as_bytes().iter().map(|b|format!("{b:02x}")).collect::<String>()}]})
    }
    #[test]
    fn tags_and_ambiguity() {
        assert_eq!(identify(&cb("\x03\x01\x02/LUXOR/"), false)["name"], "Luxor");
        assert_eq!(
            identify(&cb("/LUXOR//Noderunners/"), true)["status"],
            "ambiguous"
        );
        assert_eq!(identify(&cb("unregistered"), true)["status"], "unknown");
        assert_eq!(
            identify(&json!({"vin":[{"coinbase":"zz"}]}), true)["status"],
            "unavailable"
        );
    }
    #[test]
    fn address_versions_and_network_boundary() {
        for spk in [
            json!({"address":"1PzVut5X6Nx7Mv4JHHKPtVM9Jr9LJ4Rbry"}),
            json!({"addresses":["1PzVut5X6Nx7Mv4JHHKPtVM9Jr9LJ4Rbry"]}),
        ] {
            let mut c = cb("unknown");
            c["vout"] = json!([{"scriptPubKey":spk}]);
            assert_eq!(identify(&c, true)["name"], "BlockFills");
            assert_eq!(identify(&c, false)["status"], "unknown");
        }
    }
}
