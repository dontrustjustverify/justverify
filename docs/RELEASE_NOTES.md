# JustVerify 0.1.0-beta4

Fix Mempool navigation when JustVerify is opened through Tor. The menu now keeps the web onion hostname and opens port3006 with the selected language, instead of sending the browser to justverify.local.

- Serve the explorer through the same onion identity, using a separate authenticated loopback listener.
- Share the existing Tor login across the dashboard and explorer. Reject unauthenticated API/WebSocket requests and foreign origins.
- Close live explorer connections on logout, session expiry or disabling Remote Tor access. Preserve login through a graceful web-service restart.
- Restore existing encrypted backups with the current fixed Tor routes, preserving device identities and rejecting noncanonical destinations.
- Keep trusted-LAN access and the I2P, Core and Electrs configuration unchanged.

Bundled versions remain Bitcoin Core31.1, electrs0.11.1, mempool3.3.1 and i2pd2.61.0.

Download the matching image, checksum and signature from [Releases](https://github.com/dontrustjustverify/justverify/releases/tag/v0.1.0-beta4). Extract the IMG before using balenaEtcher and keep validation enabled. Reflashing erases the selected drive; preserve your configuration backup and existing node data before choosing a reinstall.

Physical beta4 Pi installation/reboot and the remaining hardware, wallet and long-duration checks are pending. See [validation](TESTING.md), [settings](SETTINGS.md) and [installation](INSTALL.md).
