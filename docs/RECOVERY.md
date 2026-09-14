# Backup and recovery

Save an encrypted configuration backup and its password off the NVMe before reinstalling. Use **Settings → Backup and restore**. A backup contains configuration and device identities, not the blockchain or wallet private keys.

## Restart and service problems

Use **Settings → Troubleshoot** to inspect service state and errors. Core must finish IBD; electrs must match its tip; mempool also requires a synchronized txindex. A running service alone is not proof of readiness. After changing settings, wait for the affected services to restart and verify the new state.

If Tor access times out, inspect device time, network and Tor status. Keep the existing onion identity and try again after connectivity recovers. Tor bootstrap 100% does not establish successful onion RPC access. Do not delete Tor keys, certificates or indexes to clear a connection error.

## I2P connectivity

I2P starts only when selected in incoming or outgoing peer settings. SAM READY confirms the local router API; wait for actual Bitcoin peer handshakes before treating connectivity as established. The router restarts automatically after failure. Switching both directions off stops it. Keep the Core I2P private key: encrypted configuration backups preserve it, while router transport keys are regenerated on a new installation. Old backups without an I2P identity can still be restored.

## Interrupted configuration changes

The policy and version tools retain a change journal. Review the recovery operation in the TUI before applying it. Restore the previous configuration only when the binary, network and data profile still match. Do not roll an old binary back over a migrated database. Version transitions use separate data profiles.

## Storage and reinstallation

A missing or changed data UUID blocks node startup. Reconnect the original volume and preserve its journal and contents. Do not reformat or adopt a different UUID merely to dismiss an error. The node must not write a replacement chain onto the OS partition.

Reflashing is a fresh installation and erases the selected NVMe. Use [the installation guide](INSTALL.md), keep backups off that NVMe, and use Settings to shut down before moving it. Restoring onto a newly created data UUID after OS reinstallation is still unverified in beta3. Do not rely on that procedure as a proven migration path.

## Explorer database

The bundled mempool service keeps separate SQL/cache directories per network, Core version and watch-only profile. A restart preserves its database. It reports waiting when Core/electrs is unavailable. Do not remove these directories or weaken permissions to force readiness.

See [tested and pending behavior](TESTING.md) for the limits of this candidate.
