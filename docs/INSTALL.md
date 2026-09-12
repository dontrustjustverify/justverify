# Install JustVerify 0.1.0-beta1

[English overview](../README.md) · [한국어 설치](ko/README.md) · [日本語](ja/README.md)

This image targets Raspberry Pi 5 with wired Ethernet and NVMe. The validation target is 8 GB RAM and a 2 TB SSD. It uses one OS and a data partition on the same NVMe. The data partition expands on first boot.

## Artifact and verification

Use the **pristine** `justverify-0.1.0-beta1.img.xz`, not a booted test disk. The compressed image is **654,231,760 bytes (624 MiB)**; its raw disk size is **6,444,548,096 bytes**. Empty filesystem space compresses well. Blockchain data and indexes are downloaded after installation.

Image SHA256:

```text
31ed2db7a8f16de4a0947eb5468cb61054a3eeff4ea6001c5ebb86498bed462d
```

The candidate bundle includes `justverify-0.1.0-beta1-SHA256SUMS`, its `.asc` signature, manifest, source archive, package inventory and test report. From the bundle directory:

```sh
shasum -a 256 -c justverify-0.1.0-beta1-SHA256SUMS
gpg --import justverify-experimental-signing-key.asc
gpg --fingerprint 705D2C55D7BAFACB3683EE18329759FF93A854DF
gpg --verify justverify-0.1.0-beta1-SHA256SUMS.asc justverify-0.1.0-beta1-SHA256SUMS
```

Expected signing fingerprint: `705D 2C55 D7BA FACB 3683 EE18 3297 59FF 93A8 54DF`. This is an experimental project key; a key downloaded beside the artifact does not independently establish the publisher's identity. Bitcoin Core's upstream signatures are verified separately during assembly.

## Flash and start

1. Keep your encrypted configuration backup and its password off the NVMe. Flashing replaces the selected disk contents.
2. In balenaEtcher, select `justverify-0.1.0-beta1.img.xz` and the intended NVMe. Flash and wait for validation to succeed. If compressed input is unsupported, decompress the image first.
3. Eject the NVMe safely, connect it to your Pi 5, attach Ethernet and power it on.
4. Open **http://justverify.local** on the same LAN. Use the IP shown by your router if mDNS is unavailable. HTTP is the normal initial setup path.
5. Create and confirm a new web administrator password. The default Core profile starts automatically after registration.
6. Allow Core to synchronize. Check IBD, recent blocks, index status and matching Core/electrs tips. An active process does not establish synchronization.
7. Open **Mempool** beside Electrs, or **http://justverify.local:3006**. New profiles enable `txindex=1`; existing profile settings are preserved. The explorer waits for Core, txindex and electrs to be ready.

## Access and recovery

- SSH: `ssh justverify@justverify.local`, initially `justverify` / `justverify`. Change the SSH password with `passwd`. The web password is separate. There is no unrestricted sudo access, and the public image has no developer root SSH key.
- Electrs: choose **Local network** or **Tor** in its menu and use the displayed host, port, protocol and QR. See [mobile connections](MOBILE_CONNECTIONS.md).
- Keep management HTTP and port 3006 on your trusted LAN. Core RPC uses a separate authenticated gateway; do not expose raw RPC by forwarding a port.
- Use Settings to restart or shut down. Follow [recovery instructions](RECOVERY.md) for service and configuration failures. Reflashing is a fresh installation, not an in-place update or an automatically verified migration of a backup to a new data UUID.

## Verification scope

The pristine file passed filesystem, identity-absence, packaged-source, ARM executable and compression/hash checks. A disposable generic ARM VM passed initial registration, Core/electrs, HTTP/TUI/QR and mempool tip checks. Its first Tor onion RPC attempt timed out; that cold-boot failure is retained. Separate recovery and a subsequent actual reboot passed with the same data, identity, explorer database and authenticated onion RPC. This does not establish reliable cold Tor startup or physical Pi5 acceptance for beta1.

New beta1 Pi5 installation, physical mobile-wallet/camera tests and the remaining [acceptance gates](ACCEPTANCE.md) are pending. Earlier dev16 Pi results are not beta1 results. Public source is available separately; a public binary release requires the remaining distribution review.

For development, use [BUILD.md](BUILD.md). Superseded installation instructions are preserved in [development history](INSTALL_HISTORY_KO.md); do not use their old filenames or HTTPS onboarding steps for beta1.
