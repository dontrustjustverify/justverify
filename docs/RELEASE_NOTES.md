## JustVerify 0.1.0-beta2

A Raspberry Pi 5 testing release with a more responsive dashboard and longer-lasting login sessions.

### Changes

- Collect Core status, block headers and miner details independently; distinguish slow RPC responses from connection loss and preserve the last known values.
- Keep login sessions for seven days, renew active sessions, and preserve them across browser refreshes and web-service restarts.
- Add copy buttons to LAN and Tor addresses, including browsers using local HTTP.
- Group optimization settings and label the OP_RETURN relay toggle clearly; correct version-specific defaults and remove ineffective Core 30 settings.
- Allow the `justverify` SSH account to run administrator commands with its SSH password. The browser password is separate.
- Reserve 0.5% of the data filesystem for root on new installations, down from 5%.
- Find MariaDB executables reliably when started from an SSH environment.

### Known issue

Generic ARM VM tests showed intermittent Tor startup/onion RPC timeouts. A fresh first boot and separate recovery/reboot checks succeeded, but another reboot exceeded the90s onion deadline. This result remains a failure in the test report. Physical beta2 Pi5 installation and long-run Tor reliability remain pending.

### Install

Download `justverify-0.1.0-beta2.img.xz` and the matching `justverify-0.1.0-beta2-SHA256SUMS`. Verify the checksum, extract the IMG, and flash it with balenaEtcher. Keep Etcher validation enabled. Then open **http://justverify.local**.

This is a fresh-install image. Flashing erases the selected drive; it is not an in-place update for an existing synchronized node. See the [installation guide](https://github.com/dontrustjustverify/justverify/blob/v0.1.0-beta2/docs/INSTALL.md) and [SSH guide](https://github.com/dontrustjustverify/justverify/blob/v0.1.0-beta2/docs/SSH.md).

### Compatibility

Raspberry Pi 5, ARM64, wired LAN and NVMe. Bundled: Bitcoin Core 31.1, electrs 0.11.1 and mempool 3.3.1. Core versions from 22 onward use the version-specific catalog and separate data profiles where required. I2P and pruned operation with bundled electrs are unsupported.

[한국어 안내](https://github.com/dontrustjustverify/justverify/blob/v0.1.0-beta2/docs/ko/README.md) · [日本語ガイド](https://github.com/dontrustjustverify/justverify/blob/v0.1.0-beta2/docs/ja/README.md)

See [release validation and remaining limits](https://github.com/dontrustjustverify/justverify/blob/v0.1.0-beta2/docs/TESTING.md). Beta2 still requires physical installation/boot and long-run acceptance; it is not declared a fully validated stable release.

### 검증 범위 / 検証範囲

실제 Pi5의 격리 regtest에서 거래 생성·서명·전파·2회 확인, Core/electrs/mempool tip 일치와 재시작 복구를 검증했습니다. beta2 이미지의 실기 설치·부팅은 별도 확인이 필요합니다.

実際のPi5の隔離regtestで取引の作成・署名・配信・2承認、Core/electrs/mempoolのtip一致と再起動復旧を確認しました。beta2イメージの実機インストール・起動は別途確認が必要です。
