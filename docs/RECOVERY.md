# Backup and recovery

Save an encrypted configuration backup and its password off the NVMe before reinstalling. Use **Settings → Backup and restore**. A backup contains configuration and device identities, not the blockchain or wallet private keys.

## Restart and service problems

Use **Settings → Troubleshoot** to inspect service state and errors. Core-backed Mempool pages can open during Electrs indexing. Complete address/history features require the relevant indexes to catch up. A running service alone is not proof of readiness. After changing settings, wait for the affected services to restart and verify the new state.

If Tor access times out, inspect device time, network and Tor status. Keep the existing onion identity and try again after connectivity recovers. Tor bootstrap 100% does not establish successful onion RPC access. Do not delete Tor keys, certificates or indexes to clear a connection error.

## Electrs progress and database finalization


Electrs progress distinguishes block indexing, database finalization, catching up with new blocks, and synchronization complete. During database finalization, the existing progress bar shows an approximate record-weighted percentage for the whole DB. It does not restart between internal database sections and does not estimate remaining time. If reliable measurements are unavailable, the percentage is omitted. No internal stage numbers are displayed.

Initial compaction is synchronous: new blocks and wallet requests wait until it finishes, then the same process catches up. A nearly complete height, a listening TCP port or a running service alone does not establish wallet readiness. JustVerify requires a fresh Electrum response matching Core before showing synchronization complete. A fresh metrics response alone also does not prove database work is advancing.

Before restarting or rebuilding, inspect the current compaction phase, process CPU/I/O deltas, listener and file limits, restart count, and kernel storage errors. The source utility `scripts/electrs_diagnose.py` performs bounded read-only checks; journal visibility may require administrator access. It emits selected diagnostic fields without RPC credentials or data paths. An advancing phase or increasing process I/O supports continued work. A fixed height alone is not a reason to delete or reindex. A listener error, storage error or sustained lack of observable work needs separate diagnosis; do not repeatedly restart initial compaction.

## I2P connectivity

I2P starts only when selected in incoming or outgoing peer settings. SAM READY confirms the local router API; wait for actual Bitcoin peer handshakes before treating connectivity as established. The router restarts automatically after failure. Switching both directions off stops it. Keep the Core I2P private key: encrypted configuration backups preserve it, while router transport keys are regenerated on a new installation. Old backups without an I2P identity can still be restored.

## Interrupted configuration changes

The policy and version tools retain a change journal. Review the recovery operation in the TUI before applying it. Restore the previous configuration only when the binary, network and data profile still match. Do not roll an old binary back over a migrated database. Changing Core versions resets the allowlisted chain and index files inside the current registered Core/electrs directories, after preparation and explicit confirmation. It requires a full IBD and index rebuild. Before deletion starts, recovery may restore the old execution state. After deletion starts, recovery only resumes the reviewed reset and retries the target version; it never automatically starts the old binary. Use Version change → Recover interrupted change (TUI: V → R). Keep the original volume, registration and target binary. Do not remove the startup guard. Wallet-bearing transitions are blocked before deletion.

## Storage and reinstallation

A missing or changed data UUID blocks node startup. Reconnect the original volume and preserve its journal and contents. Do not reformat or adopt a different UUID merely to dismiss an error. The node must not write a replacement chain onto the OS partition.

Reflashing is a fresh installation and erases the selected NVMe. Use [the installation guide](INSTALL.md), keep backups off that NVMe, and use Settings to shut down before moving it. Restoring onto a newly created data UUID after OS reinstallation is still unverified for this release. Do not rely on that procedure as a proven migration path.

## Tor explorer after restore

Supported older backups are validated against their exact historical Tor layout, then restored with the installed fixed routing template. The web onion identity is preserved, including Mempool on port3006. Arbitrary listener or destination changes are rejected. This does not bypass the existing same-volume and same-profile restore checks.

## Explorer database

The bundled mempool service keeps separate SQL/cache directories per registered data identity, network and watch-only profile. A restart preserves its database. The backend retries independently of a healthy database. Logs retain up to three 2 MiB files per child. Oversized RBF snapshots above 64 MiB are disposable; older SQL/profile directories are not automatically deleted. Saved block-cache heights and hashes are checked against Core at startup; incompatible disposable snapshots are rebuilt after a reset or fork. Do not remove these directories or weaken permissions to force readiness.

See [tested and pending behavior](TESTING.md) for the limits of this candidate.
