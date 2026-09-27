# Install JustVerify 0.1.1

## Hardware and download

Raspberry Pi5,8GB RAM, suitable power supply, wired LAN and a2TB SSD/NVMe are the reference configuration. Mainnet uses an unpruned blockchain and an Electrs index.

Download the pristine [IMG.XZ](https://github.com/dontrustjustverify/justverify/releases/download/v0.1.1/justverify-0.1.1.img.xz). It expands to6,444,548,096bytes; the release manifest lists the exact compressed size and SHA256. Blockchain data is downloaded after installation.

## Verify

Download [SHA256SUMS](https://github.com/dontrustjustverify/justverify/releases/download/v0.1.1/justverify-0.1.1-SHA256SUMS), [its signature](https://github.com/dontrustjustverify/justverify/releases/download/v0.1.1/justverify-0.1.1-SHA256SUMS.asc) and the [public key](https://github.com/dontrustjustverify/justverify/releases/download/v0.1.1/justverify-signing-key.asc).

```sh
awk '$2 == "justverify-0.1.1.img.xz"' justverify-0.1.1-SHA256SUMS | shasum -a 256 -c -
gpg --import justverify-signing-key.asc
gpg --fingerprint 705D2C55D7BAFACB3683EE18329759FF93A854DF
gpg --verify justverify-0.1.1-SHA256SUMS.asc justverify-0.1.1-SHA256SUMS
```

The fingerprint remains `705D 2C55 D7BA FACB 3683 EE18 3297 59FF 93A8 54DF`, the key used for earlier releases. It is a project signing key, not a third-party certification. Confirm its fingerprint through a previously trusted copy; downloading both a file and its key from one location alone does not establish independent trust.

## Flash and first boot

1. Extract with `xz -dk justverify-0.1.1.img.xz` or an XZ-capable archive tool.
2. In balenaEtcher select `justverify-0.1.1.img` and check the intended SSD/NVMe model and capacity. **All data on the selected device will be erased.** Leave validation enabled. Extracted IMG is the tested macOS workflow; Etcher supports XZ, but direct compressed input previously failed validation on the reference Mac/adapter.
3. Connect the disk to the Pi and boot. Open `http://justverify.local/` from the same LAN and create a web administrator password.
4. Allow Core to finish IBD and Electrs to index and clean its database. Cleanup progress is an estimate of processed database work, not time remaining. Readiness requires an Electrum response matching Core's current tip.
5. Connect a wallet using `justverify.local:50001` with SSL/TLS off on a trusted LAN, or use the Tor details on the Electrs screen. TLS50002 is optional and uses the device certificate.

SSH initially uses `justverify` / `justverify`. Run `passwd` after first login. The web administrator password is separate. Sudo uses SSH-user authentication; see [SSH administration](SSH.md).

## Appearance and updates

Settings → Digital Rain starts off on a new installation. Brightness defaults to40% (3–100%), speed1.60× (0.15–4.00×), density140% (30–300%). The toggle saves immediately; sliders offer preview and explicit save/cancel. Hidden tabs stop animation and reduced-motion displays a static effect.

Reflashing is a fresh installation requiring full IBD/indexing; it is not an in-place update or a data-preserving rollback. [Configuration backups](RECOVERY.md) exclude the blockchain and wallet private keys. Back up important configuration before replacing a device.

[Validation scope](TESTING.md) · [Source build guide](BUILD.md)
