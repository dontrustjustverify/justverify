# Release validation - 0.1.0-beta3

Beta3 is a testing release. Physical Pi installation of this image remains pending.

| Check | Scope and result |
|---|---|
| Core policy compatibility | PASS: 32 real ARM64 Core binaries, 256 incoming and 192 outgoing combinations, startup/preflight, saved-file roundtrip, effective RPC proxy/limited flags and listeners |
| Core 31.1 over I2P | PASS: two independent i2pd routers on the public I2P network, including the documented source-build test runner; private regtest blocks, signed transaction propagation, two confirmations, equal tip, restart/reconnection and outgoing-only propagation to height104 |
| Core 22.0 over I2P | PASS: signed transaction and two confirmations over I2P; restart, outgoing-only propagation to height104; persistent outgoing identity verified against the selected upstream version |
| Browser | PASS: actual booted image UI, saved I2P switches, refreshed session, desktop rendering and390px mobile layout without horizontal overflow; matching test port behind QEMU forwarding |
| Encrypted I2P backup | PASS: real Core-generated key, GPG encryption/restoration, original bytes and0600 restored; older complete backups without this optional entry accepted |
| ARM64 build and Rust suite | PASS; Core31.1's actual help confirms the450MiB cache default on the smaller VM, while the larger development host uses1024MiB |
| Packaged systemd, policy API and reboot | PASS: booted generic ARM factory image; HTTP registration and policy preview/save, incoming-only/outgoing-only/both off, nonroot router and loopback SAM, forced router crash recovery and actual reboot with unchanged Core identity, settings and Core/electrs tip |
| Pristine beta3 image | PASS: filesystem, full packaged source/binary hashes, identity absence, enabled systemd units, ARM runtime and cross-host full decompression/SHA256 |

Previous component evidence is available in [beta2](https://github.com/dontrustjustverify/justverify/releases/tag/v0.1.0-beta2): physical Pi5 isolated regtest Core/electrs/mempool transactions and recovery, collector delays/reorgs, OP_RETURN and mempool behavior, desktop/mobile viewport and session tests, and isolated SSH/password-sudo checks. These are not new beta3 physical-installation results.

I2P differences follow the selected Core version. Core22 does not enforce incoming-only I2P. Core22/23 reuse a persistent outgoing identity even with incoming off; Core24+ use transient identities. Core24.0/24.0.1 lack the later transient-session limit, so prefer24.1+ for outgoing-only operation. Public I2P transport tests use private regtest funds; they are not public Bitcoin testnet transactions or mainnet synchronization.

Physical beta3 installation/reboot, full public-network synchronization/indexing, physical mobile-wallet/camera use, long-duration operation, restore onto a new data UUID, OS update failure recovery and whole-image byte reproducibility remain pending. Earlier generic VM Tor timeouts remain open and have not been proven to be VM-only. Pruning is incompatible with bundled electrs.
