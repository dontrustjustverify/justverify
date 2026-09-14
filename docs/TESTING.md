# Release validation — 0.1.0-beta5

Beta5 is a testing release. Physical Pi installation of this image remains pending.

| Check | Scope and result |
|---|---|
| Electrs monitor | PASS: actual Core31.1/electrs0.11.1 in isolated ARM regtest; matching tips and wallet query, delayed responses, retained timestamps, process pause/resume, stop/restart and fork recovery |
| Pi indexing observation | PASS: corrected application tested alongside the installed services with read-only access; progress remained available while Electrum replies were delayed. This does not replace installation testing. |
| Progress display | PASS: automatic percentage/height updates against actual index data; desktop/mobile layouts, Korean/English/Japanese and all four themes |
| Packaged boot and reboot | PASS: two disposable generic ARM boots with the external Debian kernel; live progress and matching Core/electrs/mempool tips, web restart, saved login/identity/settings, actual electrs pause/resume with retained timestamp, guarded encrypted backup restore and restored authenticated HTTP/index readiness |
| Image integrity | PASS: ARM executables, packaged source hashes, OS version, filesystem, service units and absence of provisioned device identities |

A full progress bar is a block-height ratio. Wallet readiness additionally requires fresh matching Core/Electrum tips and a usable index response. A shorter-chain test explicitly invokes electrs `--reindex-last-blocks=2` on disposable regtest data; the application does not automatically reindex a production database.

Monitor and interface tests:

```sh
cargo test --lib
cargo test --test electrs_status
node tests/electrs_status_view.cjs
python3 tests/electrs_status_live.py --binary /path/to/justverify --core /path/to/bitcoin/bin --electrs /path/to/electrs
```

Run live tests in an isolated build environment with the pinned Core and electrs executables. The fixture creates its own regtest data and never opens another node dataset. The image test, `tests/image_mempool_tor_probe.py`, runs only on a disposable generic ARM boot copy and checks the packaged services; it is not a physical Pi boot test or a public Tor transport test.

Unchanged Tor Mempool transport, signed regtest transactions, policy, I2P and backup results are in [beta4](https://github.com/dontrustjustverify/justverify/releases/tag/v0.1.0-beta4), [beta3](https://github.com/dontrustjustverify/justverify/releases/tag/v0.1.0-beta3) and [beta2](https://github.com/dontrustjustverify/justverify/releases/tag/v0.1.0-beta2). They are not new beta5 physical-installation results. Core22 I2P incoming-only remains unsupported; Core22/23 outgoing identity behavior differs from Core24+. Pruning is incompatible with bundled electrs.

Physical beta5 installation/reboot, full public-network synchronization/indexing, physical mobile-wallet/camera use, long-duration operation, restore onto a new data UUID, OS update failure recovery and whole-image byte reproducibility remain pending. Earlier generic ARM onion-RPC timing failures have not been proven to be VM-only; the passing explorer transport tests do not close those separate timing checks.
