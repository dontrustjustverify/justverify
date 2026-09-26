# JustVerify 0.1.0

The first non-prerelease distribution of JustVerify for Raspberry Pi5.

- Electrs distinguishes block indexing, estimated DB cleanup progress, catching up and verified readiness. Open-file limits and connection recovery support continued indexing after initial cleanup.
- Core and the explorer remain usable while Electrs indexes. Expensive recent-block size/miner reads wait until Core finishes IBD and cover only the displayed recent blocks.
- Wallet connections default to LAN TCP50001; `server.features` advertises that public port. Optional TLS50002 and Tor remain available.
- Browser sessions renew during use without a fixed valid-session capacity limit. Settings lists active browsers and supports individual or other-session logout.
- Genesis Digital Rain adds on/off, preview/save/cancel, brightness40% up to100%, speed1.60× up to4.00×, and density140% up to300%. Existing preferences and encrypted backups remain compatible.
- Core versions use verified downloads, preflight checks and an explicit chain-reset confirmation. The same data paths are used for same-network/mode version changes; unrelated profiles and identity data are preserved. Wallet-bearing unverified transitions are blocked before deletion.

Pinned components: Bitcoin Core31.1, electrs0.11.1, Mempool3.3.1 and i2pd2.61.0.

[Download image and signed checksums](https://github.com/dontrustjustverify/justverify/releases/tag/v0.1.0). Follow [installation](INSTALL.md); reflashing deletes the selected disk. A version label does not upgrade an existing installation automatically. Existing nodes do not need to discard synchronized data just to use the appearance settings.

See [validation](TESTING.md) and the release test report for actual runs and remaining physical-device coverage. A non-prerelease tag does not imply every wallet/device combination has been tested.
