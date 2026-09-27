# Peer networks

JustVerify 0.1.1 keeps incoming and outgoing selections separate. Existing selections, chain data, wallet data and Tor/I2P identities are preserved. A permitted connection is not the same as an established peer.

## Defaults and Umbrel comparison

The reference is Umbrel Bitcoin v1.4.0, commit `2fe07948f99e101dbee95ce34e5947a69c441ee4`, checked on 2026-09-27. These are the app's new-install settings, not a reading of any particular installed Umbrel node.

| Setting | Umbrel reference | JustVerify mainnet |
|---|---|---|
| Incoming Clearnet / Tor / I2P | All off in settings | Clearnet and Tor on; I2P off |
| Outgoing Clearnet / Tor / I2P | All on | Clearnet and Tor on; I2P off |
| Clearnet over Tor | Off | Off |
| Clearnet outgoing selector | IPv4 and IPv6 together | IPv4 and IPv6 together |
| Tor inbound address | Core creates/announces an onion through Tor Control | Tor owns a persistent P2P identity; the registered Core launcher announces its public hostname |
| I2P transport | Bundled SAM router | Bundled i2pd; starts when either direction is selected |
| Incoming off | Core still listens for internal apps; the generated Clearnet bind remains present | External selected listeners close; electrs retains a dedicated loopback connection |

Umbrel's default-off Clearnet setting does not mean its Bitcoin process has no Clearnet listening socket: its generator always emits `listen=1` and an IPv4 bind. Actual external access also depends on Docker networking, the router and firewall. JustVerify enforces its Clearnet selector on IPv4 and IPv6 binds. It does not automatically create router port mappings.

Sources: [Umbrel settings](https://github.com/getumbrel/umbrel-bitcoin/blob/2fe07948f99e101dbee95ce34e5947a69c441ee4/libs/settings/settings.meta.ts), [configuration generator](https://github.com/getumbrel/umbrel-bitcoin/blob/2fe07948f99e101dbee95ce34e5947a69c441ee4/apps/backend/src/modules/config/config.ts). The implementation is independently written; upstream application code is not incorporated.

## What changed in 0.1.1

Previous releases created the P2P onion and its local listener but did not register that address with Core. The launcher now reads only the published P2P hostname, checks its v3 checksum and ownership, and supplies `externalip` with the hidden service's public port8333. Web, RPC and Electrum onion addresses are separate and are never substituted. Private Tor keys remain with Tor.

Core starts after Tor's public hostname publication. The launcher validates the registered data volume, selected binary and profile, then replaces itself with that binary. It does not change the Core version or data path. Missing or invalid required startup inputs stop startup with a bounded diagnostic rather than using an arbitrary address. An unavailable Tor circuit after startup does not restart Core.

Adding `externalip` normally disables Core's address discovery. The launcher enables discovery only when direct Clearnet incoming and outgoing are selected, and keeps it off when Clearnet is proxied through Tor or incoming Clearnet is disabled. It does not expose RPC or enable router port mapping. See [Core's manual onion configuration](https://github.com/bitcoin/bitcoin/blob/v31.1/doc/tor.md#3-manually-create-a-bitcoin-core-onion-service).

Turning Tor incoming off removes its listener and its announcement after the reviewed settings restart. Core's `onlynet`/onion reachability rules also restrict address gossip: with Tor outgoing off, incoming Tor can still accept connections to an already-known address, but the launcher does not silently enable outgoing Tor to advertise it. Use both Tor directions for normal discovery. Turning either direction on does not guarantee an external peer immediately.

The settings interface labels these selections as JustVerify defaults, not native Core defaults. Exact historical encrypted backups are upgraded to the registered launcher during restore. Modified commands, paths or privileged service options are rejected.

## I2P and reachability

I2P uses its own SAM router and `.b32.i2p:0` P2P destinations, independently of Tor. Tunnel bootstrap can take several minutes. Core22 requires I2P outgoing when I2P incoming is selected; unsupported incoming-only combinations are rejected. Core24.0/24.0.1 have an upstream transient-session issue; select Core24.1 or later, or enable both directions. See [settings](SETTINGS.md) for identity and resource limits.

Core31.1 private transaction broadcast is a separate feature from ordinary peer relay. JustVerify still requires Tor outgoing for that optional feature; I2P-only private broadcast is not a verified supported combination. The regular I2P block and transaction relay test does not establish private-broadcast coverage.

For Clearnet mainnet incoming peers, check TCP8333 forwarding for IPv4 NAT, ISP restrictions and IPv6 firewall rules. Never forward RPC8332 or internal P2P8335 as part of this check. An internal electrs peer can appear as `IN` without any external incoming peers. The peer list scrolls and includes more entries than the first visible rows.

## Recovery

If Core cannot start after a configuration change, the existing settings transaction restores the previous reviewed configuration. If its P2P hostname is missing, check the Tor service and restore the existing identity from the encrypted device backup if necessary; do not delete keys or chain data. Unsupported or altered profile/backup inputs require repair before startup. Reflashing an image erases the selected disk and is not a data-preserving update procedure.
