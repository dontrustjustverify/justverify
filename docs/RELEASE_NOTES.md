# JustVerify 0.1.0-beta1

[Download image and checksums](https://github.com/dontrustjustverify/justverify/releases/tag/v0.1.0-beta1) · [Install](INSTALL.md) · [Tested and pending behavior](TESTING.md)

- Large amber BTC circle favicon and responsive full brand message.
- Teal, Amber, Green and Ice with separate accent, body and muted tones.
- Built-in mempool at `http://justverify.local:3006`, beside Electrs in the menu.
- Korean, English and Japanese explorer pages and installation guides.
- Per-profile explorer storage, actual Core/electrs tip checks, and service recovery.
- Fixed first-registration storage creation while preserving existing-volume protection.

The image is 654,231,760 bytes compressed (624 MiB); raw disk size is 6,444,548,096 bytes. It contains one OS and a data partition that expands on the same NVMe. No chain data, test wallets or developer root SSH key are included.

| Component | Pinned version/source |
|---|---|
| Bitcoin Core | 31.1, official signed artifact; catalogs include supported versions from 22 onward |
| electrs | 0.11.1 · `35216c6d30148be8e6763d913d437330f431fc03` |
| mempool | 3.3.1 · `9332d9db97bcc7beed079acc8f79aa21c9b12a3b` |
| Node.js / MariaDB / Tor | 20.19.2 / 11.8.6 / 0.4.9.11 |
| Base OS | Raspberry Pi OS Lite 64-bit, 2026-06-18 |

The first generic-VM Tor connection timed out. Separate recovery and subsequent reboot passed without resetting identities. Physical beta1 Pi5/mobile and other remaining checks are listed in TESTING.md; this candidate does not claim complete normal operation.

The image bytes are unchanged by the repository documentation cleanup. The signed manifest identifies the image and its original build source; current main provides the cleaned documentation. Historical source tags remain available in Git history.
