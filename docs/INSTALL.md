# Install JustVerify 0.1.0-beta6

[English overview](../README.md) · [한국어 설치](ko/README.md) · [日本語](ja/README.md)

This image targets Raspberry Pi 5 with wired Ethernet and NVMe. The validation target is 8 GB RAM and a 2 TB SSD. It uses one OS and a data partition on the same NVMe. The data partition expands on first boot.

## Artifact and verification

Download the **pristine** [justverify-0.1.0-beta6.img.xz](https://github.com/dontrustjustverify/justverify/releases/download/v0.1.0-beta6/justverify-0.1.0-beta6.img.xz), not a booted test disk. The compressed download is approximately **625 MiB** and expands to a **6,444,548,096-byte** disk image. The release manifest contains its exact size and checksum. Empty filesystem space compresses well. Blockchain data and indexes are downloaded after installation.

Image SHA256:

```text
bfd14e31cc8a07d988d4c2f8c5ced086cbc94237a0ca5edf0ba2ce1995c64baa
```

The release includes [SHA256SUMS](https://github.com/dontrustjustverify/justverify/releases/download/v0.1.0-beta6/justverify-0.1.0-beta6-SHA256SUMS), its [signature](https://github.com/dontrustjustverify/justverify/releases/download/v0.1.0-beta6/justverify-0.1.0-beta6-SHA256SUMS.asc), the [public signing key](https://github.com/dontrustjustverify/justverify/releases/download/v0.1.0-beta6/justverify-experimental-signing-key.asc), manifest, source archives, package inventory and test report. OS source and notices are optional downloads; they are not needed to flash the image. To check only the image without downloading every optional source archive:

```sh
awk '$2 == "justverify-0.1.0-beta6.img.xz"' justverify-0.1.0-beta6-SHA256SUMS | shasum -a 256 -c -
```

For signature verification:

```sh
gpg --import justverify-experimental-signing-key.asc
gpg --fingerprint 705D2C55D7BAFACB3683EE18329759FF93A854DF
gpg --verify justverify-0.1.0-beta6-SHA256SUMS.asc justverify-0.1.0-beta6-SHA256SUMS
```

Expected signing fingerprint: `705D 2C55 D7BA FACB 3683 EE18 3297 59FF 93A8 54DF`. This is an experimental project key; a key downloaded beside the artifact does not independently establish the publisher's identity. Bitcoin Core's upstream signatures are verified separately during assembly.

## Flash and start

1. Keep your encrypted configuration backup and its password off the NVMe. Flashing replaces the selected disk contents.
2. Extract `justverify-0.1.0-beta6.img.xz` with an XZ-capable archive tool, then select `justverify-0.1.0-beta6.img` and the intended NVMe in balenaEtcher. Keep validation enabled and wait for success. On our macOS/Etcher 2.1.6 test, direct XZ input failed with `EVALIDATION`; the extracted IMG passed on the same target. Etcher supports XZ in general, but this tested installation uses the extracted image.
3. Eject the NVMe safely, connect it to your Pi 5, attach Ethernet and power it on.
4. Open **http://justverify.local** on the same LAN. Use the IP shown by your router if mDNS is unavailable. HTTP is the normal initial setup path.
5. Create and confirm a new web administrator password. The default Core profile starts automatically after registration.
6. Allow Core to synchronize. Check IBD, recent blocks, index status and matching Core/electrs tips. An active process does not establish synchronization.
7. Open **Mempool** beside Electrs, or **http://justverify.local:3006**. New profiles enable `txindex=1`; existing profile settings are preserved. The explorer waits for Core, txindex and electrs to be ready.

## Access and recovery

- SSH: `ssh justverify@justverify.local`, initially `justverify` / `justverify`. Change the SSH password with `passwd`. The web password is separate. Beta2 provides password-authenticated sudo; see [SSH administration](SSH.md). Public images have no developer root SSH key.
- Electrs: choose **Local network** or **Tor** in its menu and use the displayed host, port, protocol and QR. See [mobile connections](MOBILE_CONNECTIONS.md).
- Keep management HTTP and port 3006 on your trusted LAN. Core RPC uses a separate authenticated gateway; do not expose raw RPC by forwarding a port.
- Use Settings to restart or shut down. Follow [recovery instructions](RECOVERY.md) for service and configuration failures. Reflashing is a fresh installation, not an in-place update or an automatically verified migration of a backup to a new data UUID.

## Verification scope

See [release validation](TESTING.md) for image checks, component tests and remaining hardware requirements.

Physical installation of beta4, mobile-wallet/camera tests and the remaining [release validation](TESTING.md) are pending. The release page provides the image, checksums, signature, notices and component source.

For development, use [BUILD.md](BUILD.md). Use the release-linked filenames and HTTP onboarding instructions above.
