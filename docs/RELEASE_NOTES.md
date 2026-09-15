# JustVerify 0.1.0-beta7

- Keep the previous recent-block list visible until the next batch has size and mining-pool details. A bounded wait still reports unavailable data honestly.
- Use a clearer waiting-for-response status and remove routine Electrs query ages and wallet-probe rows from the overview.
- Fit the full mobile tagline on one line below YOUR BITCOIN NODE and use the available desktop peer-panel height.
- Keep the language selector heading fixed as **Language/언어설정/言語設定**. New installations default to Automatic, following the browser's Korean, English or Japanese preferences and falling back to English.
- Preserve manual language choices across refresh, include Automatic in encrypted backups, and use the resolved language for Mempool links.

Bundled versions remain Bitcoin Core31.1, electrs0.11.1, mempool3.3.1 and i2pd2.61.0. Existing Core policy, Tor/I2P connectivity and renewable browser sessions are retained.

Download [image and signed checksums](https://github.com/dontrustjustverify/justverify/releases/tag/v0.1.0-beta7). Read [installation](INSTALL.md), [settings](SETTINGS.md) and [validation](TESTING.md). Reflashing erases the selected disk; it is a fresh installation, not an in-place update.

# JustVerify 0.1.0-beta6

- Correct Electrs progress while Core is syncing: unknown/zero targets no longer show 100%, and waiting takes priority over apparent height completion.
- Show distinct syncing, delayed-update and synchronized SVG indicators, with reduced-motion support and compact, right-aligned placement. Remove repeated delay notices.
- Show recent block sizes to two decimals in MB beside each block number, preserving mining-pool names and mobile layout.
- Combine outgoing IPv4/IPv6 into one Clearnet toggle; incoming Clearnet covers both IP families.
- Default new profiles to arbitrary-data relay disabled (`datacarrier=0`) and an 83-byte size limit. Existing saved settings are preserved.
- Keep the orphan-limit field editable with explicit Core-version behavior. Core 30/31 store it only as a reference preference.
- Add a Danger Zone bitcoin.conf editor with protected system settings, version validation, real Core preflight and failed-start recovery.

Bundled versions remain Bitcoin Core31.1, electrs0.11.1, mempool3.3.1 and i2pd2.61.0. Includes previous Tor Mempool routing, I2P and seven-day renewable browser sessions.

Download [image and signed checksums](https://github.com/dontrustjustverify/justverify/releases/tag/v0.1.0-beta6). Read [installation](INSTALL.md), [settings](SETTINGS.md) and [validation](TESTING.md). Reflashing erases the selected disk; it is a fresh installation, not an in-place update.

# JustVerify 0.1.0-beta5

- Show Electrs indexing percentage and processed/Core heights in the Bitcoin Core overview, with a live progress bar in the Electrs menu.
- Collect index progress independently of wallet requests, preserving the last height and observation time during delays or outages.
- Confirm matching Core/Electrum tips and usable index queries before reporting wallet readiness. A full progress bar alone does not mean the wallet index is ready.
- Refresh progress and connection guidance while the Electrs menu stays open; support desktop/mobile layouts and all interface themes and languages.

Includes the Tor Mempool routing, I2P and earlier node-management improvements. Bundled versions remain Bitcoin Core31.1, electrs0.11.1, mempool3.3.1 and i2pd2.61.0.

Download the image, checksums and signature from [beta5 Releases](https://github.com/dontrustjustverify/justverify/releases/tag/v0.1.0-beta5). See [validation](TESTING.md) for tested and pending requirements. Physical beta5 Pi installation and reboot remain pending.

# JustVerify 0.1.0-beta4

Fix Mempool navigation when JustVerify is opened through Tor. The menu now keeps the web onion hostname and opens port3006 with the selected language, instead of sending the browser to justverify.local.

- Serve the explorer through the same onion identity, using a separate authenticated loopback listener.
- Share the existing Tor login across the dashboard and explorer. Reject unauthenticated API/WebSocket requests and foreign origins.
- Close live explorer connections on logout, session expiry or disabling Remote Tor access. Preserve login through a graceful web-service restart.
- Restore existing encrypted backups with the current fixed Tor routes, preserving device identities and rejecting noncanonical destinations.
- Keep trusted-LAN access and the I2P, Core and Electrs configuration unchanged.

Bundled versions remain Bitcoin Core31.1, electrs0.11.1, mempool3.3.1 and i2pd2.61.0.

Download the matching image, checksum and signature from [Releases](https://github.com/dontrustjustverify/justverify/releases/tag/v0.1.0-beta4). Extract the IMG before using balenaEtcher and keep validation enabled. Reflashing erases the selected drive; preserve your configuration backup and existing node data before choosing a reinstall.

Physical beta4 Pi installation/reboot and the remaining hardware, wallet and long-duration checks are pending. See [validation](TESTING.md), [settings](SETTINGS.md) and [installation](INSTALL.md).
