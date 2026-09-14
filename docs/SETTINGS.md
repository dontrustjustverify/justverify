# Node settings

This guide applies to JustVerify 0.1.0-beta3.

## OP_RETURN and transaction policy

Open **Bitcoin Core → Mempool · Network settings → Optimization**. **Relay OP_RETURN data transactions** writes Bitcoin Core's `datacarrier=1` or `datacarrier=0`. `OP_RETURN` is a script opcode; there is no separate `op_return` configuration option in the supported Core releases from 22.0 through 31.1.

Disabling the toggle restricts local acceptance and relay of unconfirmed transactions with OP_RETURN outputs. It does not change Bitcoin consensus, reject otherwise valid blocks, remove historical data, or filter every way of embedding arbitrary data. The size field (`datacarriersize`) becomes editable when relay is enabled; disabling the toggle preserves the chosen size.

| Control | Core option | Core 31.1 default / behavior |
|---|---|---|
| Database cache | `dbcache` | 1,024 MiB on devices with at least 4 GiB RAM; 450 MiB below that. Umbrel deliberately sets 450 MiB. |
| Prune old blocks | `prune` | JustVerify keeps 0/full blocks: bundled electrs 0.11.1 rejects pruned Core. Pruning also conflicts with the two transaction indexes. |
| Full transaction index | `txindex` | Core defaults to 0. JustVerify enables it during initial setup for the bundled Mempool app. Disabling it retains existing index files. |
| Transaction output spender index | `txospenderindex` | 0; available from Core 31. Requires additional indexing and disk space. |
| OP_RETURN relay | `datacarrier` | 1/on. |
| OP_RETURN size limit | `datacarriersize` | 100,000 bytes since Core 30; earlier versions use 83 bytes. Core 30+ limits the combined output-script size across multiple OP_RETURN outputs. This includes script overhead. |
| Mempool memory limit | `maxmempool` | 300 MB; 1 MB = 1,000,000 bytes. |
| Minimum block template fee | `blockmintxfee` | 0.001 sat/vB. Applies to this node's block templates. |
| Minimum relay fee | `minrelaytxfee` | 0.1 sat/vB. |
| Incremental replacement fee | `incrementalrelayfee` | 0.1 sat/vB. Review together with the minimum relay fee. |
| Transaction retention | `mempoolexpiry` | 336 hours. |
| Persist mempool | `persistmempool` | 1/on; saved at clean shutdown and loaded on startup. |
| Maximum orphan transactions | `maxorphantx` | No effect in Core 30; removed in Core 31. Older versions support it, normally defaulting to 100. |

Defaults follow the selected Core version. For example, Core 22 defaults to 1 sat/vB for all three fee settings above; Core 29.4 uses 0.001 / 0.1 / 0.1. Existing saved values are retained. The interface distinguishes the Core default from your saved request. Fee inputs use sat/vB and are converted exactly to Core's BTC/kvB units.

Choose **Review changes → Save and apply**. The service validates the version, input and dependencies, starts the selected Core binary against fresh private preflight data, saves the reviewed configuration atomically, restarts related services and checks observable runtime values. Core does not expose every option through RPC. OP_RETURN behavior is additionally checked with signed transactions in isolated regtest. Saving can interrupt node and wallet connections briefly.

For a Core 30 configuration containing an old `maxorphantx` value, use **Remove ineffective setting** and review the removal. A new save containing that option is rejected.

## Peer networks

Incoming and outgoing controls are separate. Outgoing clearnet is split into IPv4 and IPv6; Umbrel's single clearnet choice enables both. Tor outgoing uses Core's onion network. **Route clearnet through Tor** controls the proxy for ordinary internet destinations; onion connections always use Tor.

**I2P incoming and outgoing** are available in beta3. The image bundles i2pd 2.61.0 and starts it when either I2P selector is enabled. Both are off by default. Saving both off stops the router; ordinary policy changes preserve a running router and its tunnels.

| Selection | Generated Core settings |
|---|---|
| I2P outgoing | `onlynet=i2p` alongside other selected outgoing networks; `i2psam=127.0.0.1:7656` |
| I2P incoming on/off | `i2pacceptincoming=1/0` while either I2P direction is selected |
| I2P both off | No SAM or I2P accept setting; router stopped |

Core 22.0/22.1 override `onlynet` reachability when a SAM endpoint is configured. Therefore, **Core 22 requires outgoing I2P when incoming I2P is enabled**. Choose Core 23 or later for incoming-only I2P. The interface and backend reject the unsupported combination rather than silently allowing outgoing I2P.

SAM is bound to loopback and cannot be used from the LAN. Bitcoin I2P peer addresses use `.b32.i2p:0`; this is not an Electrs, RPC or browser endpoint. Routing clearnet through Tor does not route I2P through Tor. No router console, SOCKS/HTTP proxy or UPnP service is exposed. The bundled router uses a 256 KB/s bandwidth class, 50% sharing and a maximum of 20 transit tunnels. Actual traffic and startup times depend on the I2P network.

The dashboard shows **OFF**, **ROUTER UNAVAILABLE**, **SAM READY; waiting for peers**, or **CONNECTED** with actual incoming/outgoing counts. SAM READY means only that the local API answers; it does not prove a usable tunnel. Old Core data is marked STALE. Initial tunnel creation can take several minutes.

Incoming I2P uses Core's persistent `i2p_private_key`. Encrypted configuration backups include that identity; old backups without it remain restorable. Turning incoming off retains the key. Core 22/23 also reuse this persistent identity for outgoing connections; Core 24+ use transient outgoing identities. Core 24.0/24.0.1 can create excessive transient tunnels: use incoming and outgoing together, or choose Core 24.1 or newer with the upstream session limit. Router transport keys are generated locally and are not copied into the image or configuration backup.

The incoming selector preserves a private loopback P2P connection for electrs. P2P selection does not expose Core RPC. RPC wallet access uses separately authenticated and restricted endpoints.

## Addresses and sessions

Electrs offers separate **Local network** and **Tor** tabs. The copy icon on the right copies the complete address even when the input shows only part of it. LAN is `justverify.local:50002` with TLS; onion uses port 50001 with Tor on the wallet device. The address and QR are plain `host:port`; select the displayed protocol in the wallet. QR scanning is not a claim of automatic wallet configuration.

Device settings also provide copy buttons for local IPs and the enabled remote web onion address. Remote web access uses onion HTTP port 80, independently of the Electrs and RPC services. Browser clipboard support differs; if automatic copying fails, the address is selected for manual copying.

Browser login lasts seven days and renews during authenticated use. Refresh and a web-service restart preserve the session. Logout, password changes, and successful backup restoration revoke it. Disabling remote web access revokes its Tor sessions. LAN, HTTPS and Tor cookies remain separate. Session bearer tokens are not stored in plaintext or included in installation images and backups.

## Dashboard freshness

Core status, network data, block headers, mining-pool identification and host metrics are collected separately. The browser makes one status request at a time. During initial sync, the recent-block list is sampled every 15 seconds; pool identification may finish later.

An RPC timeout during heavy disk activity is shown as a delayed update. A failed RPC connection is shown separately. Previously collected values retain their timestamps and stale indication; a host update does not make old Core data current. This improves responsiveness but does not eliminate Core or disk latency during initial synchronization.

## Source references

Behavior was compared with [umbrel-bitcoin at 2fe07948](https://github.com/getumbrel/umbrel-bitcoin/tree/2fe07948f99e101dbee95ce34e5947a69c441ee4), [Umbrel authentication at bfa79ed2](https://github.com/getumbrel/umbrel/blob/bfa79ed24031b0065dd2f810411d58b82af1b95e/packages/umbreld/source/modules/auth/auth.ts), [Bitcoin Core 31.1](https://github.com/bitcoin/bitcoin/tree/9be056a8a72b624dae9623b2f7bded92c2a21c91) and [electrs 0.11.1](https://github.com/romanz/electrs/tree/35216c6d30148be8e6763d913d437330f431fc03). Product implementation is independently written. Version-specific catalogs are under `catalog/`.

I2P references: [Core 22 network implementation](https://github.com/bitcoin/bitcoin/blob/v22.0/src/net.cpp), [Core 24 transient sessions](https://github.com/bitcoin/bitcoin/blob/v24.0/src/net.cpp), [Core 24.1 I2P fixes](https://bitcoincore.org/en/releases/24.1/), [Core 31.1 I2P guide](https://github.com/bitcoin/bitcoin/blob/v31.1/doc/i2p.md), [i2pd pinned source](https://github.com/PurpleI2P/i2pd/tree/635b013a612ff47278ef02acf8580a28e10e26c5).
