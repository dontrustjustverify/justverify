# Validation — 0.1.2

## Network defaults and compatibility

- PASS: 32 official ARM Bitcoin Core versions, from 22.0 through 31.1, started with the new incoming-none/outgoing-all settings in isolated regtest preflight. Actual RPC, listener checks and saved-policy round trips completed.
- PASS: native configuration editor and initial policy semantics across the same 32 actual Core binaries.
- PASS: 142 supported version/network combinations for fresh profile serialization and preservation of legacy implicit or explicit outgoing selections; existing files remained unchanged by read/preview.
- PASS: local policy validation, configuration editor checks and Tor announcement input/selection boundaries.

Implementation: `src/policy.rs`, `src/versions.rs`, `src/tui.rs`, `web/static/settings.js`, `scripts/core_service.py`, `image/systemd/justverify-i2p.service`. Tests: `tests/peer_defaults.rs`, `tests/config_editor.rs`, `tests/policy_validation.rs`, `tests/core_announcement.py`.

- PASS: a fresh real i2pd router under the production service sandbox started as a nonroot user in 0.12 seconds, answered SAM3.1 after 2.49 seconds and retained the same process with zero restarts and a successful normal stop. Test: `tests/i2p_startup_live.py`.

- PASS: a fresh real router with external networking blocked by systemd retained its process during bootstrap and stopped normally after 201.81 seconds; no forced termination or relaxed backup stop check.

## Packaged image

PASS: two boots of a disposable copy of the packaged image, including an actual VM reboot, under an external generic ARM kernel. `tests/image_mempool_tor_probe.py` verifies:

- Incoming-none/outgoing-all defaults, disabled external incoming binds and onion announcement, with the configured I2P router running on both boots.
- Unavailable external I2P reseed does not block Core/electrs startup or cause router restart loops. Disabling the still-bootstrapping router and encrypted backup restore require a successful normal stop.
- Authenticated web API incoming selections, actual IPv4/IPv6 listeners, Tor announcement removal/restoration and unchanged chain/index tip.
- Actual unprivileged TUI default reset for incoming and outgoing: staged review, cancellation without saved or effective changes, explicit apply, observed Core settings and restoration.
- Core/electrs/explorer tip agreement; Electrum TCP50001 and optional TLS50002 on IPv4/IPv6; advertised port metadata.
- Session persistence and revocation, authenticated Tor explorer routing/WebSocket, saved display settings and actual encrypted legacy-backup restore.

Offline checks passed for filesystem integrity, identity absence, ARM binaries, packaged Python imports, service units and exact runtime-file hashes.

## Mainnet runtime

PASS: Raspberry Pi 5 application update to 0.1.2, peer-policy application, matching Core/electrs tips after a subsequent mainnet block, and Electrum header/ping through the LAN wallet port. Chain/index directories, wallet/authentication settings and Tor/I2P identities were preserved. The settings screen reports 0.1.2.

## Release checks

Release artifacts include signed SHA256 checksums, source archives, component sources and package inventories. The test report records the executed compatibility and image checks.

The optional I2P-only private transaction broadcast mode is not supported. See [network behavior](NETWORKING.md) and [installation and recovery](INSTALL.md).
