<p align="center"><img src="web/static/favicon.svg" alt="JustVerify BTC" width="96"></p>
<h1 align="center">JustVerify</h1>
<p align="center">YOUR BITCOIN NODE.<br>No Knots, no Blake2B—nothing but Bitcoin.<br>We are all Satoshi.</p>
<p align="center">English · <a href="docs/ko/README.md">한국어</a> · <a href="docs/ja/README.md">日本語</a></p>

Your own Bitcoin Core node, with a compact terminal-style dashboard, Tor, electrs and a local mempool explorer. Flash one image to your NVMe, connect your Raspberry Pi 5, and open **http://justverify.local**.

**0.1.0-beta1 is a testing release.** Check [tested and pending requirements](docs/ACCEPTANCE.md) before installing. A successful build or regtest does not establish full mainnet indexing, physical mobile-wallet compatibility or long-term reliability.

## What is included

- Official, signature-verified Bitcoin Core binaries. Select a supported release from Core 22 onward; incompatible versions use separate data directories.
- A real non-root TUI and a responsive browser dashboard with live blocks, peers, fees and system information.
- Tor and electrs, with distinct LAN/Tor connection details and QR codes.
- The **mempool 3.3.1** explorer already installed at **http://justverify.local:3006**. Open **Mempool** beside Electrs in the top menu.
- Korean, English and Japanese; Teal, Amber, Green and Ice themes.
- Reviewed settings changes, encrypted configuration backups and recovery tools.

## Hardware

The current image targets **Raspberry Pi 5, 64-bit, wired Ethernet and NVMe**. The hardware validation target is an **8 GB Pi 5 with a 2 TB NVMe SSD** and a compatible NVMe HAT/bootloader. Use a suitable power supply and cooling. Pi 4 and x86 machines are not covered by this image.

One NVMe contains the OS and a separate data partition that expands at first boot. There is no A/B OS requirement. A full Bitcoin chain, txindex, electrs index and explorer database need substantial free space; the compressed download size is not the storage requirement.

## Download and install

1. Get `justverify-0.1.0-beta1.img.xz`, `justverify-0.1.0-beta1-SHA256SUMS`, its signature, the manifest and release notes from this repository's **Releases** page when published. Use only an artifact listed in that release's manifest.
2. Check the download against `justverify-0.1.0-beta1-SHA256SUMS`. On macOS: `shasum -a 256 justverify-0.1.0-beta1.img.xz`. See [signature verification](docs/INSTALL.md) for the project's experimental signing key and trust limits.
3. In **balenaEtcher**, select the `.img.xz`, select your intended NVMe, and flash. If your Etcher version does not accept the compressed file, extract it first. Flashing erases the selected drive. Keep validation enabled and wait for successful completion.
4. Safely eject the NVMe, attach it to the Pi 5, connect Ethernet and power it on.
5. Open **http://justverify.local** from the same network. If mDNS does not work, use the Pi's IP address from your router.
6. Create your web administrator password and confirm it. The node prepares its own identity and data volume, then starts the default Core profile automatically.
7. Keep the Pi powered and connected while Core synchronizes. electrs and mempool need their own readiness checks after Core; an active service or a progress bar alone does not mean completion.

Fresh profiles enable `txindex=1` for mempool transaction lookups. Existing profiles keep their settings. The explorer shows a preparation message until Core, txindex and electrs are ready. It uses your node; it does not replace unavailable results with a public explorer's data.

## Everyday use

| Open | Purpose |
|---|---|
| `http://justverify.local` | Dashboard, Core version and policy settings, Electrs, device settings |
| `http://justverify.local:3006` | Your local mempool explorer |
| Electrs → Local network / Tor | Actual host, port, protocol, TLS fingerprint and connection QR |
| Settings | Account, text color, language, Remote Tor access, restart and shutdown |
| Settings → Backup and restore | Encrypted configuration backup and recovery |
| Settings → Troubleshoot | Service diagnosis and advanced storage tools |

The browser administrator password and SSH password are separate. As requested for this appliance, initial SSH access is **`justverify` / `justverify`**; change it with `passwd` after your first SSH login. This account does not grant an unrestricted root shell. Public images do not include the developer's root SSH key or any pre-generated device private keys.

Management HTTP and the explorer are intended for a trusted LAN. Do not forward these ports from the internet. Core RPC remains local; wallet RPC access uses the separately authenticated protected gateway. Remote Tor access is an explicit setting, and each service has its own address. Read [wallet connection details](docs/MOBILE_CONNECTIONS.md) before importing a QR.

## Backup, shutdown and recovery

Save an encrypted configuration backup and its password **off the Pi** before reinstalling. It contains configuration and device identities, not the full blockchain or wallet private keys. Use Settings to restart or shut down before removing power or the NVMe. Reflashing is a fresh installation and replaces the disk contents; it is not an in-place update. Follow the [installation guide](docs/INSTALL.md) and [recovery guide](docs/RECOVERY.md).

## Build and verification

Source, pinned component manifests and executable tests are included. Image assembly runs in an isolated **ARM64 Linux** builder; see [build instructions](docs/BUILD.md). macOS is used for development and flashing, not for running Linux systemd services directly. [Acceptance](docs/ACCEPTANCE.md), [test results](docs/TEST_RESULTS.md) and [work status](docs/STATUS.md) distinguish actual hardware tests, VM tests and untested requirements.

## Licenses and credits

JustVerify's original code and separately packaged components retain their respective licenses. See [third-party notices](THIRD_PARTY_NOTICES.md). Bitcoin Core, Tor and electrs are upstream projects. The bundled mempool app is licensed under its upstream **AGPL** terms; its corresponding source and JustVerify build modifications are accessible from **Source · AGPL** in the explorer and included in the release materials. No affiliation or endorsement is implied. Umbrel's installation-guide structure and app integration were reviewed; Umbrel source/UI assets are not copied.
