use justverify::policy::{Policy, Values};
use std::path::Path;
fn policy(version: &str, network: &str) -> Policy {
    Policy::load(
        &Path::new(env!("CARGO_MANIFEST_DIR")).join("catalog"),
        version,
        network,
    )
    .unwrap()
}
fn value(key: &str, value: &str) -> Values {
    Values::from([(key.to_owned(), value.to_owned())])
}
#[test]
fn prevent_silent_clamps_overflow_and_network_misapplication() {
    let modern = policy("31.1", "regtest");
    let legacy = policy("22.0", "regtest");
    assert!(modern.validate(&value("blockmaxweight", "7999")).is_err());
    assert!(modern.validate(&value("blockmaxweight", "4000000")).is_ok());
    assert!(
        legacy
            .validate(&value("blockmaxweight", "4000000"))
            .is_err()
    );
    assert!(legacy.validate(&value("blockmaxweight", "3996000")).is_ok());
    assert!(
        modern
            .validate(&value("datacarriersize", "4294967296"))
            .is_err()
    );
    assert!(
        modern
            .validate(&value("maxmempool", "9223372036854775807"))
            .is_err()
    );
    assert!(modern.validate(&value("blockversion", "-1")).is_ok());
    assert!(
        modern
            .validate(&value("blockversion", "2147483648"))
            .is_err()
    );
    assert!(
        policy("31.1", "main")
            .validate(&value("blockversion", "1"))
            .is_err()
    );
    assert!(
        policy("31.1", "main")
            .validate(&value("acceptnonstdtxn", "1"))
            .is_err()
    );
    assert!(legacy.validate(&value("limitclustercount", "25")).is_err());
    assert!(modern.validate(&value("limitancestorcount", "25")).is_err());
}

#[test]
fn outgoing_destinations_are_finite_and_proxy_cannot_inject_an_endpoint() {
    for version in ["22.0", "31.1"] {
        let p = policy(version, "regtest");
        assert_eq!(
            p.validate(&value("onlynet", "onion,ipv4")).unwrap()["onlynet"],
            "ipv4,onion"
        );
        assert_eq!(
            p.validate(&value("onlynet", "i2p")).unwrap()["onlynet"],
            "i2p"
        );
        for bad in [
            "",
            "i2p,i2p",
            "i2p\ni2psam=192.0.2.1:7656",
            "ipv4,ipv4",
            "ipv4\nrpcbind=0.0.0.0",
            "onion,",
        ] {
            assert!(p.validate(&value("onlynet", bad)).is_err());
        }
        assert_eq!(
            p.validate(&value("proxy", "1")).unwrap()["proxy"],
            "127.0.0.1:9050"
        );
        assert!(p.validate(&value("proxy", "192.0.2.1:9050")).is_err());
    }
}

#[test]
fn incoming_selector_cannot_expose_arbitrary_bindings() {
    for version in ["22.0", "31.1"] {
        let p = policy(version, "regtest");
        for allowed in [
            "none",
            "clearnet",
            "tor",
            "clearnet,tor",
            "i2p",
            "clearnet,i2p",
            "i2p,tor",
            "clearnet,i2p,tor",
        ] {
            if version.starts_with("22.") && allowed.split(',').any(|n| n == "i2p") {
                assert!(p.validate(&value("listen", allowed)).is_err());
                let both = Values::from([
                    ("listen".into(), allowed.into()),
                    ("onlynet".into(), "i2p".into()),
                ]);
                assert_eq!(p.validate(&both).unwrap()["listen"], allowed);
                continue;
            }
            assert_eq!(
                p.validate(&value("listen", allowed)).unwrap()["listen"],
                allowed
            );
        }
        for bad in [
            "",
            "0",
            "none,tor",
            "tor,tor",
            "i2p,i2p",
            "i2p\ni2pacceptincoming=1",
            "0.0.0.0:8333",
            "tor\nbind=0.0.0.0",
        ] {
            assert!(p.validate(&value("listen", bad)).is_err());
        }
    }
}

#[test]
fn resources_use_version_defaults_and_reject_clamping_or_overflow() {
    for version in ["22.0", "31.1"] {
        let p = policy(version, "regtest");
        for (key, bad) in [
            ("maxconnections", "0"),
            ("maxconnections", "2147483647"),
            ("dbcache", "3"),
            ("timeout", "0"),
            ("peertimeout", "0"),
            ("rpcworkqueue", "0"),
            ("maxuploadtarget", "8796093022208"),
            ("maxsendbuffer", "9223372036854776"),
        ] {
            assert!(p.validate(&value(key, bad)).is_err(), "{version}: {key}");
        }
        let entries = p.entries();
        let default = entries.iter().find(|r| r["key"] == "dbcache").unwrap()["default"]
            .as_str()
            .unwrap();
        let mut host = sysinfo::System::new();
        host.refresh_memory();
        let expected = if version == "22.0" || host.total_memory() < 4_294_967_296 {
            "450"
        } else {
            "1024"
        };
        assert_eq!(default, expected);
    }
    assert!(
        policy("22.0", "regtest")
            .validate(&value("dbcache", "16385"))
            .is_err()
    );
}

#[test]
fn index_dependencies_and_embedded_asmap_are_version_scoped() {
    let modern = policy("31.1", "regtest");
    assert!(modern.validate(&value("peerblockfilters", "1")).is_err());
    assert!(
        modern
            .validate(&Values::from([
                ("peerblockfilters".into(), "1".into()),
                ("blockfilterindex".into(), "1".into())
            ]))
            .is_ok()
    );
    assert!(
        policy("30.3", "regtest")
            .validate(&value("asmap", "1"))
            .is_err()
    );
    assert!(
        policy("30.3", "regtest")
            .validate(&value("txospenderindex", "1"))
            .is_err()
    );
    assert!(
        modern
            .validate(&value("asmap", "/tmp/arbitrary-file"))
            .is_err()
    );
    assert!(modern.validate(&value("prune", "550")).is_err());
}

#[test]
fn private_broadcast_rejects_known_leak_and_incompatible_network_setup() {
    assert!(
        policy("31.0", "main")
            .validate(&value("privatebroadcast", "1"))
            .is_err()
    );
    assert!(
        policy("31.1", "regtest")
            .validate(&value("privatebroadcast", "1"))
            .is_err()
    );
    assert!(
        policy("31.1", "testnet4")
            .validate(&Values::from([
                ("privatebroadcast".into(), "1".into()),
                ("onlynet".into(), "ipv4".into())
            ]))
            .is_err()
    );
    assert!(
        policy("31.1", "testnet4")
            .validate(&value("privatebroadcast", "1"))
            .is_ok()
    );
}

#[test]
fn op_return_and_removed_orphan_option_are_version_scoped() {
    for version in ["22.0", "29.4", "30.3", "31.1"] {
        let p = policy(version, "regtest");
        assert!(p.validate(&value("op_return", "0")).is_err());
        assert!(p.validate(&value("datacarrier", "0")).is_ok());
        assert!(p.validate(&value("datacarrier", "1")).is_ok());
        assert!(p.validate(&value("datacarrier", "2")).is_err());
        assert_eq!(
            p.validate(&value("maxorphantx", "100")).is_ok(),
            version == "22.0" || version == "29.4"
        );
    }
    let temp = std::env::temp_dir().join(format!("jv-orphan-migration-{}", std::process::id()));
    std::fs::create_dir(&temp).unwrap();
    let file = temp.join("managed.conf");
    std::fs::write(&file, "maxorphantx=100\n").unwrap();
    let p = policy("30.3", "regtest");
    let saved = p.current(&file).unwrap();
    assert_eq!(saved["maxorphantx"], "100");
    assert!(p.current_effective(&file).unwrap().is_empty());
    assert!(p.preview(&file, saved).is_err());
    let plan = p.preview(&file, Values::new()).unwrap();
    assert!(
        plan.changes
            .iter()
            .any(|v| v.contains("maxorphantx: 100 ->"))
    );
    assert_eq!(std::fs::read_to_string(&file).unwrap(), "maxorphantx=100\n");
    std::fs::remove_dir_all(temp).unwrap();
}
