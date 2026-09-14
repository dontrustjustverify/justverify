# Node settings

This guide applies to JustVerify 0.1.0-beta2.

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

I2P is not included in this image. Core supports I2P through a separately running SAM-compatible router, but JustVerify does not yet package or verify that router. Incoming and outgoing I2P are therefore unavailable. Enabling an unsupported checkbox would not provide working I2P connectivity.

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
