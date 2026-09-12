# Wallet connections

Open **Electrs** in JustVerify and choose **Local network** or **Tor**. Use the address shown by your device; another device's onion address or certificate is not interchangeable.

| Connection | Address and protocol | Wallet setup |
|---|---|---|
| Electrum on LAN | `justverify.local:50002`, TLS | Select SSL/TLS and verify the device certificate fingerprint |
| Electrum over Tor | Device-specific `.onion:50001`, TCP inside Tor | Configure the wallet's Tor/SOCKS connection; this endpoint is not TLS |
| Wallet RPC | Separately authenticated gateway, enabled explicitly | Create an individual client and use its assigned permissions |

Electrum QR codes contain ordinary `host:port` text. They do not imply that every wallet supports automatic QR import. The LAN Electrum listener currently supports private/link-local IPv4 and loopback, not IPv6. Core must be ready and electrs must agree with its height and tip before relying on wallet results.

## RPC clients

The fixed TUI **C** menu creates and revokes individual clients. A new client has node-read permissions. Its password is displayed once; keep it private. The device's internal Core cookie is never a wallet credential.

Use **C/O** to review and explicitly enable the Tor RPC gateway. It uses a separate onion address and port 8332. It accepts authenticated RPC requests; it does not expose the browser administration UI or unrestricted Core RPC. The LAN HTTPS gateway requires the device certificate to be trusted. Do not disable certificate verification.

For Fully Noded Quick Connect, explicitly open **Q** after creating the client. This QR contains credentials and uses `btcrpc://user:password@onion:port?label=...`. Keep it out of screenshots and shared logs. This format is separate from the plain Electrum server QR.

## Watch-only and transaction permissions

1. In **V**, select **W** for a separate watch-only profile and review the version, network and data path. A new profile can require fresh synchronization and additional storage.
2. In **C/A**, create a client. Use **C/W** to assign its watch-only wallet and public-descriptor permissions.
3. If needed, use **C/T** to grant separate transaction preparation/broadcast permissions. They are not automatically included with read access.
4. The client can use only its assigned `/wallet/<name>` path. Private-key import/export, node-side signing and management RPC are denied. PSBT processing has signing disabled; sign with a separate signer.
5. **C/R** revokes access while preserving wallet data. Client permissions are tied to the data UUID and profile.

For PSBT fees, `fee_rate` is sat/vB and `feeRate` is BTC/kvB; do not specify both. Watch-only clients can query UTXO locks. Changing locks needs transaction permissions; persistent locks are not provided, and restart persistence is not claimed.

## Current validation limits

The RPC/Electrum protocols, digital QR contents, watch-only restrictions, PSBT and actual regtest transactions have software-level validation. Physical Nunchuk/Fully Noded installations, camera scans, mobile certificate setup and each application's full call sequence are still unverified for beta1. Check [TESTING.md](TESTING.md) before relying on a specific phone workflow.
