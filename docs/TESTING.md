# Release validation — 0.1.0-beta6

Beta6 is a testing release. The application changes have been exercised on a Raspberry Pi 5; fresh installation of this exact beta6 image on physical hardware remains pending.

| Check | Scope and result |
|---|---|
| Core settings and editor | PASS: 32 verified ARM Core releases22.0–31.1, 64 isolated starts; editor save/restart, actual failed-start recovery, version/protected-setting guards and signed regtest arbitrary-data boundaries |
| Pi application | PASS: application update on Pi5/8GB/NVMe; authentication/CSRF/editor checks, retained settings/session after physical reboot, active Core RPC and continued mainnet IBD. Existing production data preserved. |
| Electrs progress | PASS: zero/unknown target and IBD guards; real Core/electrs tip and wallet query, delayed responses, timestamps, pause/resume, restart and fork recovery |
| Core status and interface | PASS: real Core initial sync, caught-up tip, header-only lag, no-new-block waiting, RPC pause/recovery and HTTP stall; desktop/mobile, four themes and three languages. Reduced-motion CSS branch checked; actual OS preference switch not exercised. |
| Recent block sizes | PASS: native/ARM Core31.1 regtest sizes match serialized bytes, including genesis; retained across refresh/reorg; six Pi mainnet blocks match RPC; desktop1280/mobile390/320px preserve pool and avoid overflow |
| Packaged boot and reboot | PASS: two fresh generic ARM boots; factory policy defaults, actual editor preflight and block sizes, matching Core/electrs/mempool tips, login/settings/identity persistence, index pause/resume, and guarded encrypted backup restore |
| Image integrity | PASS: full transfer/decompression hashes, filesystem, ARM executables, runtime source hashes, service units and absence of provisioned device identities |

The title badge uses fresh Core IBD and block/header state. Rounded100% and time since the previous block do not establish synchronization. Electrs wallet readiness additionally requires fresh matching Core/Electrum tips and a usable index query. A shorter-chain test explicitly invokes electrs `--reindex-last-blocks=2` only on disposable regtest data.

Run focused checks with the pinned executables in an isolated environment:

```sh
cargo test --locked
node tests/core_status_view.cjs
node tests/electrs_status_view.cjs
python3 tests/collector_responsiveness.py --binary /path/to/justverify --core /path/to/bitcoin/bin
python3 tests/electrs_status_live.py --binary /path/to/justverify --core /path/to/bitcoin/bin --electrs /path/to/electrs
JV_CORE_BIN=/path/to/bitcoin/bin/bitcoind cargo test --test policy_integration -- --ignored
JV_CORE_MATRIX=/path/to/verified-core-matrix cargo test --test config_editor -- --ignored
```

The image test `tests/image_mempool_tor_probe.py` runs only on a disposable generic ARM image copy using an external Debian kernel. It exercises installed services, not physical Pi firmware or public Tor transport. The source build procedure is in [BUILD.md](BUILD.md).

Previous unchanged Tor explorer transport, I2P and backup evidence remains in [beta5](https://github.com/dontrustjustverify/justverify/releases/tag/v0.1.0-beta5) and its linked earlier releases. Core22 incoming-only I2P remains unsupported; Core22/23 reuse persistent outgoing identities. Pruning is incompatible with bundled electrs.

Fresh physical beta6 installation/reboot, full public-network synchronization/indexing, physical mobile-wallet/camera use, long-duration operation, restore onto a new data UUID, OS update failure recovery and whole-image byte reproducibility remain pending. Earlier generic ARM onion-RPC timing failures are separate from the passing explorer checks and have not been proven to be VM-only.
