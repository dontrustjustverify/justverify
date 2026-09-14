# Third-party notices

JustVerify's original code is MIT-licensed. Each separately bundled component and dependency keeps its own license; the root MIT license does not relicense the OS, Tor or mempool.

| Component | Version/source | Notices and corresponding source |
|---|---|---|
| Bitcoin Core | Official, signature-verified releases; default 31.1 | MIT; pinned artifacts/signers in `catalog/` |
| i2pd | 2.61.0, `635b013a612ff47278ef02acf8580a28e10e26c5` | BSD-3-Clause; `licenses/i2pd/LICENSE`; exact source/SHA256 in `catalog/i2pd.json`. The image bundle also includes its source archive and public reseed certificates. |
| electrs | 0.11.1, `35216c6d30148be8e6763d913d437330f431fc03` | MIT; exact source URL/hash in `catalog/electrs.json` |
| mempool | 3.3.1, `9332d9db97bcc7beed079acc8f79aa21c9b12a3b` | Upstream AGPL; full source, patches, locks, build instructions, LICENSE and COPYING.md in the companion source archive and the app's **Source · AGPL** link |
| Mining-pool data | `f678a4a620537ad7997a475ad0f14bfab1de3c8b` | MIT; `licenses/mining-pools/LICENSE` and `image/mempool/POOLS-LICENSE` |
| xterm.js | 6.0.0 | MIT; `web/static/XTERM_LICENSE`, pinned npm integrity in `catalog/xterm.json` |
| Rust dependencies | `Cargo.lock` | Individual notices in `licenses/rust/`; ARM target inventory in `licenses/rust-license-arm64.json` |
| Raspberry Pi OS / Debian packages | Exact installed versions in the release package inventory | Individual copyright notices and source packages in the release's OS notices/source assets |
| Node.js / MariaDB / Tor | 20.19.2 / 11.8.6 / 0.4.9.11 | Upstream and Debian licenses; included in the OS notices/source inventory |

Download [notices](https://github.com/dontrustjustverify/justverify/releases/download/v0.1.0-beta1/justverify-0.1.0-beta1-notices.tar.gz), the [source manifest](https://github.com/dontrustjustverify/justverify/releases/download/v0.1.0-beta1/justverify-0.1.0-beta1-os-sources.json), OS source [part 1](https://github.com/dontrustjustverify/justverify/releases/download/v0.1.0-beta1/justverify-0.1.0-beta1-os-source-1.tar) / [part 2](https://github.com/dontrustjustverify/justverify/releases/download/v0.1.0-beta1/justverify-0.1.0-beta1-os-source-2.tar), and [mempool source](https://github.com/dontrustjustverify/justverify/releases/download/v0.1.0-beta1/justverify-0.1.0-beta1-mempool-source.tar.gz) beside the image from [Releases](https://github.com/dontrustjustverify/justverify/releases/tag/v0.1.0-beta1). Source assets include exact source-file hashes and upstream locations. The image also retains installed `/usr/share/doc/*/copyright` notices. Firmware retains its respective vendor redistribution terms.

The mempool modifications bind the backend to loopback, package three locales, disable external fiat/acceleration services, and integrate local source access. The full patch and build procedure are included. npm dependencies retain their notices inside the bundle; GBT source and its Cargo lock are included with upstream source.

Umbrel app commit `01de454ee9a368245a2513afc8e84969bafb946a` and guide commit `bfa79ed24031b0065dd2f810411d58b82af1b95e` were references for integration and guide structure. No Umbrel code or artwork is copied. No upstream endorsement or affiliation is implied.

The OS source assets cover 405 exact source package versions. Raspberry Pi Connect Lite uses the permissive terms listed in its packaged notice; that notice is included. The upstream raspberrypi-net-mods 1.4.4 package omits a copyright file in both its installed package and source; its complete unchanged source and this packaging limitation are retained in the companion assets. This inventory does not claim independent legal certification of every upstream package.
