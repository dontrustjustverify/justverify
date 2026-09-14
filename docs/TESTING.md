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
| Physical Pi5 running the flashed beta1 | Core31.1 mainnet IBD and web/SSH observed; full boot/recovery acceptance incomplete |
| Physical mobile wallet and camera | NOT RUN |
| Full mainnet synchronization on the new image, 24-hour validation | NOT COMPLETE |
| All policy transaction semantics, restore to a new UUID, OS update failure recovery | NOT COMPLETE |
| Byte-for-byte reproduction of the whole OS | NOT COMPLETE |

Build and test scripts remain in `scripts/` and `tests/`. Generated local logs and historical development notes are not shipped in the source tree. Removing those notes does not remove test requirements or turn a failed result into a pass.

## Pi5 NVMe recording (2026-09-13)

macOS and balenaEtcher2.1.6, GEIL RTL9210 2TB NVMe: direct XZ input failed with EVALIDATION, and an independent read-only check confirmed that the recorded image extent differed from the original. Both the compressed download and its decompressed IMG matched the signed manifest hashes.

Retrying the extracted IMG on the same target passed Etcher's write and read-back validation:1successful target,0failures, noerrors. The IMG uses2,979,004,416bytes of mapped data within its6,444,548,096-byte image extent. An additional independent comparison after retry was NOT RUN because the NVMe was no longer attached. This validates the Etcher recording procedure; the new beta1 Pi5 boot and physical mobile acceptance are still NOT RUN.


## Current source validation (2026-09-14)

The installed Pi5 was observed running Core31.1 mainnet initial synchronization. Candidate UI/collector tests used a separate, temporary unprivileged process; the installed services and mainnet configuration were preserved.

- Actual Core31.1 signed regtest transactions: OP_RETURN on/off,42/43byte script boundary,combined multiple outputs,valid-block acceptance,fee limits,persistence,expiry and mempool-pressure eviction passed. This is not a full policy-matrix pass.
- Actual Core31.1 configuration preflight/save/restart,failed-startup rollback and administrator-process crash recovery passed. Version/option validation passed20Rust checks, including refusal of Core30's ineffective maxorphantx and an invented op_return option.
- macOS and ARM64 Linux collectors passed delayed-coinbase isolation,reorg,Corepause/resume,miner cache and TUI checks. A two-minute simultaneous Pi observation reduced median Core sample age from10.744s to2.691s. The candidate had no chain errors in59initialized samples; its recent-block list still exceeded15s in7of58initialized samples. Long-run stability is not established.
- Real browser HTTP copy-and-paste matched LAN/onion address inputs. Desktop1440px/mobile390px,KO/EN/JA,OP_RETURN toggle/size dependency and reload-session behavior passed in Chromium151. A physical phone was not tested.
- Real web restarts preserved seven-day sessions; activity renewed them, and logout/password changes revoked them. TLS,Origin/CSRF and cookie-audience tests passed. Tor-specific HTTP listener lifecycle preserved sessions on graceful restart and revoked them on explicit disable; this did not test Tor network transport. Actual GPG restore removed persisted session files. Seven days of elapsed testing was not performed.

Production Pi application replacement is blocked by the public SSH account's restricted privileges. The existing release image/tag remains unchanged. Mainnet synchronization and electrs/mempool indexing are not yet a completed acceptance pass. I2P is unsupported because no SAM router is packaged; pruning is incompatible with bundled electrs.
