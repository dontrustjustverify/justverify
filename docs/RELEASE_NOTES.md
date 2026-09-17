# JustVerify 0.1.0-beta8

- Open Core-backed Mempool pages while Electrs indexes. Address history becomes available as indexing completes.
- Distinguish Electrs index cleanup from synchronization completion; confirm readiness with a matching Core tip and a working Electrum response.
- Restart a failed explorer backend without restarting its healthy MariaDB instance. Bound log retention and discard oversized disposable RBF caches.
- Validate saved explorer block caches against the current Core chain before reuse, including after a reset.
- Keep explorer storage tied to the registered data profile when the Core executable changes. Preserve separate networks and watch-only profiles.
- Retry transient Core/Electrs/TLS startup failures without exhausting the short retry window. Allow Core and Electrs up to fifteen minutes to flush on shutdown; recover services when backup preparation fails.
- Support private IPv6 LAN Electrum TLS connections and count activity in either direction before idle disconnection.
- Limit expensive recent-block detail reads during IBD while keeping status collection independent.
- Change Core versions through a prepared, explicitly confirmed chain reset in the current data directories. Downloading or selecting a card never deletes data. Wallet-bearing transitions are blocked; preserved wallet files are never opened automatically by an older version.

Bitcoin Core 31.1, electrs 0.11.1, Mempool 3.3.1 and i2pd 2.61.0 remain pinned. Their sources and licenses are included with the release materials.

The [beta8 release](https://github.com/dontrustjustverify/justverify/releases/tag/v0.1.0-beta8) contains `justverify-0.1.0-beta8.img.xz`, its signed `SHA256SUMS`, manifest and validation report. Extract the IMG for the tested balenaEtcher workflow. Reflashing erases the selected disk.

See [installation](INSTALL.md), [recovery](RECOVERY.md) and [validation](TESTING.md).

Validated on a Raspberry Pi 5 with NVMe: initial boot, data-volume expansion, password-authenticated sudo, continuing mainnet IBD and the LAN explorer block API/WebSocket. Full mainnet Electrs completion and physical wallet app combinations remain pending. No operational restart or reset was used for these checks.
