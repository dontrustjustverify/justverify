# Tested and pending behavior — 0.1.0-beta1

This is a testing candidate, not a completed hardware acceptance release. The [machine-readable test report](https://github.com/dontrustjustverify/justverify/releases/download/v0.1.0-beta1/justverify-0.1.0-beta1-test-report.json) includes exact versions, transaction IDs, tips, results and preserved failures.

| Check | Result |
|---|---|
| Core 22.0 and 31.1 + electrs 0.11.1 + mempool 3.3.1 | PASS in isolated ARM64 Linux regtest: create/sign/broadcast, unconfirmed transaction, mining, two confirmations, height/tip and address agreement |
| Core, electrs, SQL/backend interruption and restart | PASS with actual services and persisted data |
| Network mismatch and separate profile database | PASS |
| Browser themes, login refresh, three language links, 390px layout | PASS in a browser viewport; not a physical phone test |
| Pristine image checksums, filesystem, packaged code and identity absence | PASS |
| Generic ARM initial registration, Core/electrs, RPC/wallet/PSBT, HTTP/TUI/QR and mempool | Independent checks PASS; the cold-boot suite retained a Tor onion RPC timeout FAIL |
| Same-image recovery and actual subsequent reboot | PASS twice, including preserved identity/data/SQL and authenticated Tor RPC plus access denials |
| New beta1 image on physical Pi 5 | NOT RUN |
| Physical mobile wallet and camera | NOT RUN |
| Full mainnet synchronization on the new image, 24-hour validation | NOT COMPLETE |
| All policy transaction semantics, restore to a new UUID, OS update failure recovery | NOT COMPLETE |
| Byte-for-byte reproduction of the whole OS | NOT COMPLETE |

Build and test scripts remain in `scripts/` and `tests/`. Generated local logs and historical development notes are not shipped in the source tree. Removing those notes does not remove test requirements or turn a failed result into a pass.
