# Validation — 0.1.0

The attached release test report contains exact image hashes and executed checks.

## Executed for this release

- Digital Rain: authenticated HTTP, schema and range validation, defaults of40% /1.60× /140%, maxima of100% /4.00× /300%, explicit save/cancel and reloading. Chromium exercises three languages, four themes, mobile390px and desktop1440px, reduced motion and page hiding/freezing. No extra node requests are introduced by the animation.
- Encrypted preferences: actual Linux GPG restores legacy and current settings, including the new maxima, and rejects out-of-range values. The full backup regression covers wrong passwords, tampering, certificate/key consistency, path protections and interrupted restoration.
- ARM64 release compilation, filesystem and ownership checks, fresh-device identity absence, complete compressed/uncompressed hashes and matching source inputs.
- Packaged generic ARM VM boot and reboot: real Core31.1/electrs0.11.1 regtest, matching tips, Mempool, IPv4/IPv6 TCP and optional TLS, public50001 versus private50003 metadata, local Tor forwarding configuration, session persistence/revocation and Digital Rain persistence across service restart and reboot. The companion report records the result; the VM uses an external Debian kernel.
- An existing synchronized Pi received only the appearance-related update. Core/electrs process identities stayed unchanged and LAN50001 answered with the same latest block hash as Core. This is separate from installing the complete0.1.0 image.

## Earlier checks of unchanged components

Actual isolated Core/electrs tests exercised four signed regtest transactions, lookup and new-block subscriptions over TCP/TLS. Session tests covered412 logins, expiration/renewal, device-specific logout and restarts. Earlier mainnet observation verified initial Electrs DB cleanup followed by catch-up and subsequent new-block updates without a restart. These results are retained as prior evidence, not new full-suite executions for0.1.0.

## Not yet executed for this complete image

- Physical Raspberry Pi5/NVMe installation, firmware boot and reboot of the exact0.1.0 image.
- Physical iPhone/Safari/Onion Browser rendering, battery use and external Tor transport.
- Actual BlueWallet/Nunchuk/hardware-wallet end-to-end interaction on the new image.
- Long-duration mainnet soak testing and whole-image byte-for-byte rebuild reproducibility.

Generic ARM tests do not establish Pi firmware or adapter compatibility. Browser viewport tests do not establish physical phone performance. No real-user wallet funds or chain data were used for destructive or transaction tests. Consult [installation](INSTALL.md), [wallet connections](MOBILE_CONNECTIONS.md) and [recovery](RECOVERY.md) before deployment.
