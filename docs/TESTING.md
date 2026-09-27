# Validation — 0.1.1

The release test report records the exact image hashes, executed checks and limitations. No real-user wallet funds or chain data were used for destructive or transaction tests.

## Executed for this release

- Officially verified ARM64 Core binaries: 32 versions from 22.0 through 31.1, with five real startup/RPC announcement cases per version. Incoming and outgoing preflight tests separately exercise 256 and 192 real Core starts. They check network restrictions, loopback preservation and settings round trips.
- A real Tor circuit between two fresh Core 31.1 regtest nodes: Bitcoin handshake, 101-block catch-up, remote address learning from Core's announcement, and a subsequent block at height 102. No clearnet fallback or manual insertion of the advertised address into the remote address database.
- Two real I2P routers and fresh Core 31.1 regtest nodes: persistent destination creation, incoming/outgoing I2P peers, 101-block catch-up, a signed test transaction with two confirmations, restart with identity preservation, and outgoing-only operation through height 104.
- Launcher input boundaries, onion v3 checksum validation and 280 network-selection combinations. Actual Linux GPG backup tests cover Tor configuration variants, rejection cases and preservation of I2P identity bytes.
- Policy integration tests exercise a successful change and recovery from a real failed Core start. Configuration validation and JavaScript syntax checks also pass.
- ARM64 release compilation, filesystem/ownership and fresh-device identity checks, complete compressed/uncompressed hashes, and comparison of installed changes with the preceding image.
- Packaged generic ARM VM boot and reboot: real Core 31.1/electrs 0.11.1 regtest, matching tips, Mempool, IPv4/IPv6 TCP and optional TLS, session persistence/revocation, saved appearance settings, registered Core launch and Tor address announcement. Incoming selections are applied through the authenticated web API, with actual listener/announcement removal and restoration. Legacy encrypted Core launcher configuration is normalized on restore.

The boot harness waits for a successful TLS header response after service restarts; a systemd start acknowledgement alone is not treated as socket readiness. The initial immediate TLS probe failed before the listener was ready. The unchanged image is retested with the full response and header-hash assertions retained.

## Existing Pi and remaining checks

A synchronized Pi 5 received the targeted network-code update. Core and electrs retained the existing chain and index; Tor identities, preferences and the Tor process were preserved. An external Tor client completed a real mainnet Bitcoin handshake and ping, and Core classified it as an incoming onion peer. After the patch, Core and LAN Electrum 50001 both advanced from height 968758 to 968759 with the same block hash. The Pi retained its prior base OS/application version; this is not a complete 0.1.1 image installation.

The first update verification retained an old in-memory configuration validator and triggered a code rollback. After fixing that verification path, the update and protected-byte checks passed. This involved three intentional Core/electrs restart cycles including rollback and retry, without chain reset or reindexing. Earlier electrs restart history predates the patch and is not evidence of a regression or a long-duration reliability guarantee.

- NOT RUN: installation and firmware boot/reboot of the exact 0.1.1 image on physical Raspberry Pi 5/NVMe.
- NOT RUN: actual BlueWallet/Nunchuk/hardware-wallet interaction on this image.
- NOT RUN: independent WAN reachability of the owner's Clearnet router/firewall, unsolicited mainnet inbound peers, and a long-duration mainnet soak.
- NOT RUN: whole-image byte-for-byte rebuild reproducibility and an optional private-transaction broadcast configured to use only I2P.

The generic ARM VM uses an external Debian kernel and does not establish Pi firmware or adapter compatibility. Real Tor/I2P transport checks do not prove reachability of a particular home network. Enabling incoming connections permits them; it does not guarantee peers will connect.

## Earlier evidence of unchanged features

The preceding release exercised Digital Rain ranges and rendering, encrypted preferences, session expiration/renewal and device logout. Earlier actual Core/electrs tests covered four signed regtest transactions, transaction lookup and new-block subscriptions over TCP/TLS. Mainnet observation separately confirmed initial Electrs cleanup, catch-up and subsequent new blocks. These are retained prior results, not repeated full-suite executions for 0.1.1.

See [network behavior](NETWORKING.md), [installation](INSTALL.md), [wallet connections](MOBILE_CONNECTIONS.md) and [recovery](RECOVERY.md).
