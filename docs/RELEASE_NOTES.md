# JustVerify 0.1.0-beta3

Add I2P peers to Bitcoin Core's incoming and outgoing network controls. The image includes source-pinned i2pd 2.61.0, starts it only when selected and keeps its SAM interface on loopback. Both directions default off.

- Separate incoming/outgoing choices, validated configuration preview, atomic save, service restart and effective Core RPC checks.
- Core 22 requires I2P outgoing when incoming is enabled because of its upstream reachability behavior; Core 23+ permits incoming-only.
- Display local SAM readiness separately from completed Bitcoin peer handshakes.
- Preserve the Core I2P identity in encrypted backups; accept existing backups without the new optional identity.
- Retain beta2's session, dashboard freshness, address copying, OP_RETURN controls and SSH administration changes.

Bundled: Bitcoin Core 31.1, electrs 0.11.1, mempool 3.3.1 and i2pd 2.61.0. I2P provides Bitcoin P2P transport, not a new browser or wallet endpoint. Pruning remains incompatible with bundled electrs.

Download the matching image and checksum from [Releases](https://github.com/dontrustjustverify/justverify/releases/tag/v0.1.0-beta3). Extract the IMG before using balenaEtcher and keep validation enabled. Reflashing erases the selected drive.

Physical beta3 Pi installation/reboot and long-duration operation remain pending. Earlier generic VM Tor timeouts are not established to be VM-only. See [validation](TESTING.md), [settings](SETTINGS.md) and [installation](INSTALL.md).
