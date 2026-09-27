# JustVerify 0.1.1

Fixes discovery of incoming Tor Bitcoin peers. Earlier releases created the P2P onion listener without announcing its address to Bitcoin Core.

- The registered launcher validates Tor's public P2P hostname and announces it to Core. Direct Clearnet discovery is preserved; Tor proxy privacy and disabled incoming routes remain respected.
- Core startup waits for local Tor hostname publication. Persistent Tor keys, chain data, selected versions, RPC restrictions and connection defaults are preserved.
- Exact older encrypted backups restore through the current launcher; noncanonical service commands remain rejected.
- Peer settings explain that allowing a route does not establish a peer, and identify JustVerify's defaults separately from Core's.

[Network behavior and Umbrel comparison](NETWORKING.md) · [Validation](TESTING.md) · [Image, checksums and component sources](https://github.com/dontrustjustverify/justverify/releases/tag/v0.1.1)

Pinned components remain Bitcoin Core31.1, electrs0.11.1, Mempool3.3.1 and i2pd2.61.0. Clearnet incoming can require router forwarding or firewall changes. No router configuration is changed automatically. Reflashing erases the selected disk; existing installations do not update automatically.
