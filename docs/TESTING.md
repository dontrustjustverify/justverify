# Release validation — 0.1.0-beta8

| Check | Result |
|---|---|
| Core/electrs/Mempool/MariaDB integration | PASS: isolated ARM64 regtest; early HTTP/WebSocket, address queries, signed transaction broadcast, confirmation, outage/reconnect |
| Explorer failure and storage | PASS: actual backend SIGKILL preserves SQL PID; separate watch-only profile, fixed storage identity, bounded logs/cache; saved height107 → fresh height2 recovery |
| LAN Electrum TLS | PASS: actual IPv4/IPv6 headers and signed broadcasts, trusted certificate, idle expiry, ping and reconnect |
| Services and backup | PASS: four native startup failures followed by real Core RPC; actual stop failure refuses backup writes and resumes services; strict policy API accepts registered storage identity |
| Version changes | PASS: native Core31.1 →22.0 →31.1, same data paths and fresh genesis; earlier full pinned release matrix and interruption tests recorded separately |
| Collector and configuration | PASS: actual RPC delays, pause/recovery/reorg; Rust tests and actual encrypted GPG backup/restore |
| Image integrity | PASS: offline filesystem, runtime/source identity, pinned binary hashes, empty device identities and service definitions; complete transfer checks recorded in the manifest |
| Packaged boot and reboot | PASS: both boots, real Core/electrs/explorer tip agreement, session/identity preservation, indexing pause/recovery and encrypted backup restore in disposable generic ARM image |
| Physical Pi 5 / 2 TB NVMe installation and boot | PASS: Etcher verification, factory data-partition expansion, exact installed binary/runtime hashes, SSH/sudo, active services and continuing mainnet block download |
| Explorer on physical Pi during IBD | PASS: real block list and WebSocket; Core 10,356 → 37,026 over 212 seconds; Electrs correctly waits for Core |
| Full mainnet indexing and physical reboot | NOT RUN for beta8; generic ARM reboot was checked separately |
| Physical hardware wallet and mobile wallet app combinations | NOT RUN; regtest signing is not physical-device testing |
| Mainnet throughput/thermal comparison with Umbrel | NOT RUN; startup health observation is not a controlled throughput comparison |

See the packaged test report for artifact hashes, exact checks and remaining limits. Generic ARM boot does not test Raspberry Pi firmware or the physical NVMe adapter.

First-boot observations: the explorer frontend retried once while the protected Tor state directory was created. Tor initially reported clock skew, then reached bootstrap 100% after time synchronization. Both recovered automatically, and no further restarts occurred in the observation interval. No undervoltage, OOM, NVMe I/O or ext4 errors were found in that boot journal. Services, policies and chain data were not changed during observation.
