<p align="center"><img src="web/static/favicon.svg" alt="JustVerify BTC" width="96"></p>
<h1 align="center">JustVerify</h1>
<p align="center">YOUR BITCOIN NODE.<br>No Knots, no Blake2B—nothing but Bitcoin.<br>We are all Satoshi.</p>

JustVerify combines Bitcoin Core, electrs, Tor and a local Mempool explorer in an installable Raspberry Pi image. Manage your node from `justverify.local` or the text interface.

[한국어](docs/ko/README.md) · [日本語](docs/ja/README.md) · [Build from source](docs/BUILD.md)

## Download 0.1.2

- [Raspberry Pi image — IMG.XZ](https://github.com/dontrustjustverify/justverify/releases/download/v0.1.2/justverify-0.1.2.img.xz)
- [SHA256SUMS](https://github.com/dontrustjustverify/justverify/releases/download/v0.1.2/justverify-0.1.2-SHA256SUMS) · [Signature](https://github.com/dontrustjustverify/justverify/releases/download/v0.1.2/justverify-0.1.2-SHA256SUMS.asc) · [Signing key](https://github.com/dontrustjustverify/justverify/releases/download/v0.1.2/justverify-signing-key.asc)
- [Source archive](https://github.com/dontrustjustverify/justverify/releases/download/v0.1.2/justverify-0.1.2-source.tar.gz) · [Release and component sources](https://github.com/dontrustjustverify/justverify/releases/tag/v0.1.2)

## Install

Use a Raspberry Pi 5 with 8 GB RAM, a suitable power supply, wired networking and a 2 TB SSD/NVMe for the default unpruned mainnet node.

1. Download the image and verify its checksum and signature as described in [installation](docs/INSTALL.md).
2. Extract the `.img.xz` and select the `.img` in balenaEtcher. Check the target device carefully: **flashing erases that disk**. Keep Etcher validation enabled.
3. Attach the storage to the Pi, boot and open `http://justverify.local/` on the same LAN. Create the separate web administrator password.
4. Wait for Core synchronization, Electrs indexing and DB cleanup to finish. The dashboard distinguishes indexing, cleanup, catching up and readiness.

For wallet applications, use **`justverify.local:50001`, SSL/TLS off**, on a trusted LAN. Optional TLS uses port50002; Electrs settings also provide the Tor address and QR codes. See [wallet connections](docs/MOBILE_CONNECTIONS.md).

Initial SSH access is `justverify` / `justverify`; change it with `passwd` after first login. This is separate from the web password. Password-authenticated sudo provides OS administration. See [SSH](docs/SSH.md).

## Features

- Core status, recent blocks, fees, connected peers and service readiness.
- Official signed Bitcoin Core releases from22.x through31.1, with version-specific settings and explicit confirmation before a version change clears chain/index data for full resynchronization. Merely selecting or downloading a version does not change it.
- Clearnet, Tor and I2P peer controls; independent optional remote web access through Tor.
- Electrum LAN TCP and optional TLS, plus Tor wallet connections. The default node holds no wallet private keys.
- Core-backed Mempool pages during Electrs indexing; address history becomes available when the index is ready.
- Seven-day renewable browser sessions, device/session management, logout and encrypted configuration backups.
- Korean, English and Japanese; automatic browser-language selection and four color themes.
- Optional genesis-block **Digital Rain** in Settings: brightness40% (maximum100%), speed1.60× (maximum4.00×), density140% (maximum300%). It starts off on a new installation; saved preferences are preserved. Animation runs in the browser and stops when hidden; reduced-motion uses a static background.

## See JustVerify

Version 0.1.0, with Digital Rain enabled. Captured from a running node in an isolated regtest environment; mobile views use a 390 px browser viewport.

**Desktop dashboard**

![Desktop dashboard](docs/media/justverify-desktop.png)

**Mobile dashboard and Electrs wallet connection**

<p><img src="docs/media/justverify-mobile.png" alt="JustVerify mobile dashboard" width="300"> <img src="docs/media/justverify-mobile-electrs.png" alt="Electrs mobile connection" width="300"></p>

**Digital Rain settings**

![Digital Rain settings](docs/media/justverify-digital-rain.png)

**30-second tour · ten views, three seconds each**

https://github.com/user-attachments/assets/d26903d9-03a6-45cb-b740-3a5e81ee8407

[Download MP4](https://github.com/dontrustjustverify/justverify/releases/download/v0.1.0/justverify-0.1.0-tour.mp4)

## Documentation

[Install](docs/INSTALL.md) · [Settings](docs/SETTINGS.md) · [Appearance](docs/DEVICE_SETTINGS.md) · [Recovery](docs/RECOVERY.md) · [Release notes](docs/RELEASE_NOTES.md) · [Validation scope](docs/TESTING.md)

Core31.1, electrs0.11.1, Mempool3.3.1 and i2pd2.61.0 are pinned. The release includes source bundles, package inventories and [third-party notices](licenses/THIRD_PARTY_NOTICES.md). Raspberry Pi firmware/NVMe behavior and individual physical wallet applications have separate validation requirements; see the validation report for tested and untested combinations.
