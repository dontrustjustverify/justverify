# Release validation — 0.1.0-beta4

Beta4 is a testing release. Physical Pi installation of this image remains pending.

| Check | Scope and result |
|---|---|
| Menu links | PASS: shipped JavaScript transformations for LAN hostname, IPv4, IPv6 and onion; Korean, English and Japanese; return link retains the hostname |
| LAN explorer regression | PASS: actual Core31.1/electrs0.11.1/mempool3.3.1/SQL, signed regtest transaction, two confirmations, matching height107/tip, backend restart and Core outage/recovery |
| Tor explorer | PASS: two independent Tor instances; descriptor publication observed before connection; three localized HTML pages, configuration, source links, authenticated API and actual WebSocket block data |
| Tor transaction | PASS: signed regtest transaction broadcast through onion port3006, one confirmation at height108, equal Core/electrs/mempool tip |
| Access and session lifecycle | PASS: shared Tor login, anonymous API rejection, HTML redirect to onion login, Host/Origin/unsafe-POST guards, logout and disable revocation, graceful restart, timestamp-boundary expiry/renewal and real occupied-port failure |
| Tor backup compatibility | PASS: actual GPG restore of three historical/current layouts into the installed fixed template; three altered destination/listener configurations rejected before writes |
| Packaged boot and reboot | PASS: disposable generic ARM image with external Debian kernel; actual Core/electrs/mempool, Tor-specific loopback HTTP/WebSocket, saved identity/login and opt-in setting, web-service restart, remote disable, production guarded GPG restore of previous Tor layout and explorer recovery |
| ARM64 application | PASS: locked release build with version0.1.0-beta4 |

Run `node tests/mempool_links.js` from a source checkout. For the live tests, use the dedicated `justverify` test account and separate regtest described in [BUILD.md](BUILD.md), keep `tests/mempool_live.py` running with `--hold`, then run `tests/mempool_tor_live.py` against that fixture. The Tor test requires test-only aiohttp3.13.3, aiohttp-socks0.10.1, python-socks2.8.2 and a Tor executable. Its `--state` must be a fresh private directory. It never opens another node dataset. Bootstrap100% alone does not establish onion descriptor publication; the test also observes `HS_DESC UPLOADED`. Session timestamp-boundary checks are distinct from a seven-day duration test.

The image probe checks installed services through loopback; the independent Tor test above checks network transport separately.

The release test-report JSON contains exact transaction IDs, block hashes and image checks. Tests use private regtest funds transported through the public Tor network; they are not public Bitcoin testnet transactions.

Unchanged policy, I2P, backup and earlier component results are in [beta3](https://github.com/dontrustjustverify/justverify/releases/tag/v0.1.0-beta3) and [beta2](https://github.com/dontrustjustverify/justverify/releases/tag/v0.1.0-beta2). They are not new beta4 physical-installation results. Core22 I2P incoming-only remains unsupported; Core22/23 outgoing identity behavior differs from Core24+. Pruning is incompatible with bundled electrs.

Physical beta4 installation/reboot, full public-network synchronization/indexing, physical mobile-wallet/camera use, long-duration operation, restore onto a new data UUID, OS update failure recovery and whole-image byte reproducibility remain pending. Earlier generic ARM onion-RPC timing failures have not been proven to be VM-only; the successful explorer test does not close those separate timing checks.
# Electrs progress and readiness regression checks

```sh
cargo test --locked --lib --test electrs_status
node tests/electrs_status_view.cjs
python3 tests/electrs_status_live.py \
  --core /path/to/bitcoin/bin \
  --electrs /path/to/electrs \
  --binary target/release/justverify
```

The live test creates an isolated regtest chain. It checks real wallet queries and tip agreement, delayed forwarded responses, preserved stale values, process pause/resume, service restart and chain changes. Manual invalidation to a shorter chain is tested separately using electrs' explicit `--reindex-last-blocks` recovery option; the application does not automatically reindex user data.
