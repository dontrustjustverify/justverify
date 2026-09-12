# 요구사항별 인수 상태


## 2026-09-12 0.1.0-beta1 변경 검증

| 요구사항 | 구현·검증 | 결과·증거 |
| --- | --- | --- |
| 큰 BTC 원형 favicon, 전체 문구, 글자색 계층 | web/static, scripts/build_favicon.py; 실제 브라우저390px/새로고침/테마 클릭 | PASS, evidence/beta1-responsive-ui.json; 물리 휴대폰 NOT RUN |
| 내장 mempool3.3.1·3006·SQL·Core/electrs 연결 | scripts/build_mempool.sh, mempool_service.py, web/mempool_proxy.py; tests/mempool_live.py | PASS, evidence/beta1-mempool-regtest.json: 실제 서명거래/미확인→2확인/107높이·hash/주소/WS |
| Core·electrs 중단 뒤 실제 연결·상태 복구 | 동일 실서비스 시험, 새 cookie/실제 indexer 재시작/Electrum tip·주소 재확인 | PASS. 처음의 부족한 electrs 재연결 검증과 발견된 false-ready 오류·수정·재시험은 STATUS 및 로그 보존 |
| Core22.0 + 내장 mempool 호환 | 동일 실제 거래/서비스/SQL/실시간/indexer 회귀 | PASS, evidence/beta1-mempool-core22.json; 107높이·2확인 |
| 네트워크 불일치 차단·프로필별 SQL 분리 | tests/mempool_profile_live.py | PASS, evidence/beta1-mempool-profile.json; Core 실제 chain 불일치 사전 차단 및 별도 SQL 데이터 보존 |
| 설치 이미지 새 서비스·txindex 기본·실제 부팅 | image/verify-pi.sh, tests/image_boot_probe.py, image_data_probe.py | 파일·초기 등록·내장 멤풀 tip PASS; cold Tor onion timeout FAIL 유지, evidence/image-beta1-r3-boot.json |
| 동일 이미지 복구와 실제 재부팅 | tests/image_recovery_probe.py, scripts/run_image_recovery.py | PASS2회: 같은 신원/UUID/tip/설정/멤풀 SQL와 실제 Tor RPC200·401/404. evidence/image-beta1-recovery.json; 새 Pi 실기 NOT RUN |
| 영어/한국어/일본어 설치 README | README.md, docs/ko/README.md, docs/ja/README.md | 작성 완료. 새 저장소 생성 및 승인된 CLI 인증 완료, 소스 게시 준비 |

기존 dev16 실기 결과는 보존하지만 새 내장 mempool 이미지 검증을 대신하지 않는다.

전체: 진행 중. 배포 후보 완료 아님. PASS는 표에 적힌 범위만 의미한다.

## 2026-09-12 dev16 새 Pi5 실기 검증

대상은 실제 NVMe에서 새로 부팅한 Pi5/8GB, Core31.1.0·electrs0.11.1·Tor0.4.9.11이다. 아래 결과는 이전 VM 결과를 대체하지 않는다. 상세 범위와 실패·재시험은 [실기 보고서](PI5_DEV16_VALIDATION.md), 원본 경로와 수치는 [실행 증거](evidence/dev16-pi-hardware.json)에 기록했다.

| 요구사항 | 구현·실제 검증 | 결과·증거 |
|---|---|---|
| 새 이미지 Pi5 부팅·확장·SSH·HTTP | 설치된 dev16, tests/pi_readonly_observe.py; 지정 NVMe 모델·새 UUID·데이터 확장·14개 서비스·root 키/justverify 암호 SSH·IP/mDNS HTTP | PASS. 새 Pi5 부팅 NOT RUN 상태 해소 |
| 실제 TUI·웹·QR | 비권한 패키지 TUI120/80/42열; 별도 loopback 시험 계정으로 실제 공유 수집기/인증/CSRF/refresh/WebSocket, QR 디지털 해독·LAN TLS 검증 | 명시한 범위 PASS. HDMI 실제 화면·휴대폰 카메라·앱은 NOT RUN |
| Pi Tor P2P·인증 RPC | 독립 Tor client → Pi onion. P2P handshake; 임시 node-read 계정·동일 패키지 gateway의 실제 Core 조회/무인증·비허용 RPC·관리 경로 차단 | PASS. 시험 계정 폐기/포트 종료; 운영 Remote RPC는 기존 비활성 유지. 이전 VM RPC timeout은 별도 FAIL |
| 설치된 Core/electrs의 실제 거래·인덱싱 | tests/pi_regtest_transaction.py; 격리 regtest에서 생성·서명·Electrum broadcast·mempool·2확인·수신 잔액·높이103/tip 일치 | PASS. evidence/dev16-pi-regtest-transaction.json. Mainnet/공개 testnet 거래를 실행한 결과가 아님 |
| 실제 기기 재부팅·설정·데이터 보존 | 웹 power preview/apply→제한 기기 API; 새 boot ID, 설정/신원14개 hash·UUID 유지, Core 체인 조상 일치; 같은 regtest 지갑/인덱스 재개 | PASS. SSH44.6초, main265712→273501; regtest103/2확인 유지 |
| 수집기 장애 복구 | 실제 manager SIGKILL→새 PID·재시작 수·신선한 RPC snapshot; Core PID 유지 | PASS4.81초. 시험 실행기 첫 sample 대기 실패와 재시험 보존 |
| 새 설치 설정 백업 | 실제 암호화·복호화 검사28개 설정, Mac 전송 hash 일치 | PASS(생성/검사/전송). 실제 restore는 NOT RUN |
| Mainnet 전체 동기화·electrs 전체 인덱싱 | 실제 RPC 및 수집기, 2026-09-12 12:50:06UTC | 진행 중:303442/966678, IBD=true. electrs는 Core IBD 대기; 완료 판정 불가 |

## 2026-09-12 설정·favicon·채굴 풀 추가 검증

| 요구사항 | 구현 | 실제 검증 | 결과·증거 |
|---|---|---|---|
| 설정 계층 정리·고급 복구 보존 | web/static/device.js, app.js | Pi5 제품 코드, 별도 임시 계정으로 백업/진단/보호된 저장장치 진입 | PASS, docs/evidence/dev16-ui-pi.json |
| Amber BTC 돋보기 favicon | scripts/build_favicon.py, web/static/favicon.* | 실제 HTTP 라우트·MIME·파일 바이트, SVG/ICO/PNG 시각 확인 | PASS, .state/release-dev16/http-with-favicon.log |
| 블록 번호 오른쪽 채굴 풀 | src/miner.rs, src/lib.rs, dashboard.js | 실제 Core22.0/22.1/23.2/24.2/25.2/26.2/27.2/28.2/28.4/29.3/29.4/30.2/30.3/31.1, txindex=0 regtest submitblock와 reorg | PASS, docs/evidence/miner-attribution-live.json |
| 반응형 메뉴·세션 유지 | web/static | 실제 Pi 데이터, 브라우저1200/390px, refresh, Amber, 일본어 | PASS(브라우저 viewport), 실제 휴대폰 검증과 구분 |
| 재설치 전 설정 보존 | scripts/backup_bundle.py | 실제 Pi28개 설정 파일 암호화, Mac에서 독립 복호화와 전체 entry hash 대조 | PASS, .state/release-dev16/preflash-backup/local-verification.json; 실제 restore는 미실행 |
| 새 이미지 파일 검증 | image/build-pi.sh, verify-pi.sh | dev16 전체 offline·xz·hash 및 실제 SSH | PASS(파일/실행 범위). 후속 새 Pi5 부팅도 위 실기 표에서 PASS |
| dev16 실제 NVMe 기록·읽기 검증·추출 | balenaEtcher2.1.6, diskutil | 지정 외장 GEIL2TB에 pristine raw 기록, Validating 완료/성공1개, 새 파티션 배치 및 안전 추출 | PASS, docs/evidence/dev16-etcher-flash.json; 후속 새 Pi5 부팅은 docs/evidence/dev16-pi-hardware.json |
| 새 이미지 부팅·Tor | tests/image_boot_probe.py, run_image_probe.py | 실제12GiB 가상 디스크 데이터 확장/Core/electrs/TLS/HTTP/TUI/QR, Tor bootstrap/onion | 전체 FAIL: Tor timeout. image-dev16-private-{grown,retry}-probe.json |
| 동일 실패 이미지 재부팅 복구 | tests/image_recovery_probe.py | 같은 신원/UUID/tip/정책/인덱스/지갑/TLS·HTTP/TUI 재검증 | 독립 항목 PASS, Tor BLOCKED → 전체 PARTIAL, docs/evidence/image-dev16-recovery.json |

최신 dev12(a87289a assembly /11c8419 Rust /770b8e8 observer): 읽기 전용 검증과 실제 최초 설치·두 번 부팅 PASS. dev11 범위에 더해 설치된 policy API의 Core31 cluster default64를 양쪽 부팅에서 확인했다. 증거 pi-image-dev12-verify.log, image-dev12-data-probe.json. 전체 Pi/mobile/백업·업데이트/정책 의미·서명 게이트는 남아 있다.

제품 Tor RPC/TUI/Quick Connect: C/O에서 상태·검토·관리자 암호 재확인·적용을 제공하고, 별도 RPC onion 8332를 제한 gateway에 연결한다. 실제 비권한 PTY, 0700/0600 IPC와 타 UID/중복 서버 차단, 오암호/취소, 실제 Core 호출, 웹 프로세스 재시작 복원, 제품 systemd Tor onion 경유 인증·관리 경로 차단, W/T watch-only·PSBT 회귀 PASS(`docs/evidence/remote-rpc-tui-tor.log`). Fully Noded 고정 commit 형식 QR의 실제 PTY 셀 및 디지털 decode PASS(`docs/evidence/rpc-quick-connect-qr.json`). OS 재부팅·새 이미지·실제 앱/카메라는 아직 NOT RUN/BLOCKED이며 dev8에 미포함이다.

원격 RPC 저장/소유자 API: `web/remote_rpc.py`, `web/server.py`. `sudo /opt/justverify/venv/bin/python tests/remote_rpc_control.py`에서 실제 HTTPS 소유자/CSRF/암호 재확인, 실제 Core 조회, 서버 객체/소켓 재생성 후 committed 설정 유지, 미완료 파일의 비활성 시작, 오래된 검토 거부, 실제 포트 충돌 및 복구 PASS(`docs/evidence/remote-rpc-control.log`). 이는 실제 SIGKILL/OS 재부팅이나 TUI/Tor 서비스 통합 시험이 아니며 dev8 미포함이다.

Tor RPC 전송 구현: `web/server.py`의 선택적 RPC-only listener. `tests/wallet_gateway_tls.py <version> --tor`로 Core22.0/31.1에서 동일 Gateway/공유30회 한도/폐기/지갑 격리/관리 경로 부재 PASS. Core31.1은 `JV_TOR_TEST`의 별도 실제 Tor SOCKS/v3 onion 연결까지 PASS(`docs/evidence/tor-rpc-transport.log`). 기본 비활성, dev8 미포함, 소유자 설정 UI/재부팅·모바일 앱·배포 이미지 검증은 NOT RUN이다.

dev8 이미지 검증: source fd3d4b1, artifact SHA256 `13296d8e019a4f779a60d5aa2bcdb5c8bbb90b0c779ebf4c8843544edd47f8aa`. 읽기 전용 검사와 외부 Debian 커널에서 최초 데이터 설정→실제 Core/electrs/LAN TLS/지갑/coin-control/Q-L 화면→실제 재부팅 후 데이터·인증 유지 PASS(`docs/evidence/pi-image-dev8-verify.log`, `docs/evidence/image-dev8-data-probe.json`). 아래 dev7 미포함으로 기록된 coin-control/LAN TLS 소스 변경은 dev8에 포함됐다. Pi 실기/모바일/전체 정책·설정/복구·업데이트 등의 남은 기준을 충족했다는 뜻은 아니다.

LAN Electrum TLS: `web/electrum_tls.py`, `image/systemd/justverify-electrum-tls.service`, `scripts/profile_helper.py`, Q/L 연결 UI. 설치된 ARM Linux 비권한 서비스와 실제 Core31.1/electrs0.11.1 등록 프로필에서 TLS 인증서 검증·header 일치·평문/비LAN 주소 거부·서비스 재시작·연속 프로필 전환 PASS(`tests/linux_initial_profile.py`→`tests/linux_electrum_tls.py`, `docs/evidence/electrum-tls-profile.log`). 실제 PTY/QR 디지털 해독 PASS. 새 배포 이미지 부팅 및 별도 LAN 단말/실제 모바일 앱은 아직 미검증이며 dev7에는 미포함이다.

모바일 coin-control 소프트웨어: `web/watch_only.py`, `web/rpc_gateway.py`, C/T 안내. `TMPDIR=/var/tmp /opt/justverify/venv/bin/python tests/wallet_gateway_tls.py <version>`으로 공식 검증 ARM Core 22.0~31.1의 32개 조합에서 잠금 권한·조회·자금 선택 제외/복구·지갑 격리·입력 거부 PASS(`docs/evidence/coin-control-tls-matrix.json`). dev7에는 아직 미포함이며 실제 모바일 앱 실행/QR/전송 신뢰 완료를 의미하지 않는다.

dev7 설치 이미지: 저장장치 수정 포함 소스 일치·기기별 비밀정보 부재·파일시스템 검사 PASS(`docs/evidence/pi-image-dev7-verify.log`). 외부 Debian 커널을 사용한 최초 저장장치 설정→Core31.1 watch-only/regtest·electrs height1·Tor 서비스/주소·TLS 지갑/PSBT·실제 TUI→재부팅 후 데이터/인증 보존 PASS(`docs/evidence/image-dev7-data-probe.json`). Pi 실기/실제 모바일 지갑/전체 정책 및 나머지 필수 수용 항목은 별도이며 전체 완료가 아니다.

설치 직후 저장장치 UUID: dev6 원본은 임시 mount source 때문에 프로필 준비 FAIL(`docs/evidence/image-dev6-data-initial-failure.json`). 수정 소스의 실제 ext4 즉시 UUID 회귀 시험과 수정 사본의 최초 설정→Core/electrs/watch-only/PSBT→실제 재부팅 PASS(`docs/evidence/volume-mount-identity.log`, `docs/evidence/image-dev6-patched-data-probe.json`). 외부 Debian 커널을 사용한 가상 머신 시험이다. 수정된 dev7 배포 이미지 검증 및 Pi 실기 검증은 아직 NOT RUN/BLOCKED이며 전체 완료가 아니다.

| ID | 요구사항 | 구현/명령 | 대상 | 결과 및 증거 |
|---|---|---|---|---|
| S0-01 | 요구사항/위협 경계/결정/환경 | docs/ARCHITECTURE.md, DECISIONS.md, ENVIRONMENT.md | 개발 호스트 | 작성, 상세 대응표 확장 중 |
| S1-01 | 실제 RPC 공유 수집 및 stale | src/lib.rs, src/main.rs; scripts/regtest_smoke.py | Core 31.1 macOS arm64 | PASS evidence/regtest-smoke.json |
| S1-02 | 실제 TUI 120×40 | 동일 smoke의 PTY | macOS | 기본 표시 PASS, 모든 요약 필드/80×24/모바일 레이아웃 NOT RUN |
| S1-03 | 브라우저 동일 TUI/인증 | web/server.py; tests/web_security.py | 실제 HTTPS/WS macOS | 자동 보안 흐름 PASS evidence/web-security.json; GUI 브라우저 NOT RUN |
| S1-04 | Linux 부팅/systemd | scripts/vm_prepare.py, vm_start.sh | QEMU Debian ARM64 | VM 부팅 PASS evidence/vm-first-boot.log; 제품 이미지 부팅 아님 |
| S2-01 | Core/electrs 인덱싱/조회/재시작 | scripts/electrs_smoke.py | 31.1 + electrs 0.11.1 macOS arm64 | PASS evidence/electrs-smoke.json; mempool tx 전파 NOT RUN |
| S2-02 | Tor 및 서비스별 onion | scripts/electrs_smoke.py --tor-hostname-file | 실제 Tor → Electrum | onion 조회 PASS evidence/onion-electrum.json; 제품 systemd lifecycle PASS (linux-network-services-test.log), 최종 이미지 반영 NOT RUN |
| S2-03 | QR/LAN/모바일 연결 | 구현 진행 예정 | Nunchuk/Fully Noded | NOT RUN; 실제 카메라 BLOCKED (장비 없음) |
| S2-04 | 초기 소유권/TLS/mDNS | web/server.py, web_identity.py | 개발 HTTPS | owner-file/실제 TLS proof/verified HTTPS claim/VM firstboot script+console PTY PASS (headless-pairing-durable.log, linux-owner-firstboot-durable.log); 일반 headless GUI/실제 브라우저 신뢰/Pi 최초 설치 NOT RUN |
| S3-01 | 22~최신 전체 안정판 선택 | catalog/releases.json, catalog_core.py, fetch_core.py | 34 releases | 목록화 및 32개 ARM Linux 실행 PASS, 30.0/30.1 upstream 철회; 31.1↔22.0 native API/TUI 전환 PASS (linux-version-tui-bootstrap-guard.log); 23.2 official download/API/TUI D PASS (linux-download-accessible.log, linux-download-tui.log); firstboot 등록/전체 운영 matrix 미완료 |
| S3-02 | 전체 정책 카탈로그/검증/적용 | src/policy.rs, policy_service.rs, tui.rs; tests/policy_integration.rs, linux_policy_api.py, linux_policy_crash.py | 실제 Core31.1/macOS 및 Linux ARM64 | 단위/실제 apply/rollback/강제 종료 TUI recovery PASS (policy-recovery-integration.log, linux-policy-api-ready.log, linux-policy-crash-tui-socket.log); 전체 semantic/behavior matrix 미완료 |
| S3-03 | Umbrel 대응표 | docs/UMBREL_PARITY.md | 고정 commit | 조사/구현 진행 예정 |
| S3-04 | 데이터 보호/전환 실패 복구 | src/storage.rs, versions.rs; tests/version_transition.rs | 실제 ARM Linux Core22.0↔31.1 + electrs0.11.1 | 데이터/인덱스 분리·보존, 실제 startup failure/SIGKILL 복구 PASS (version-transition-recovery-final.log); 운영 systemd/UI31.1↔22.0 PASS; 전체 network/전환 범위 미완료 |
| S4-01 | Pi 이미지 빌드/기록/부팅 | image/ | Raspberry Pi 5 | 개발 이미지 생성/RO 구조 검사 PASS (pi-image-verify-scratch.log), 실기 부팅 BLOCKED |
| S4-02 | 재부팅/마운트/디스크/네트워크/업데이트 실패 | 구현 예정 | VM 및 Pi | VM mount/low-disk/service/reboot PASS (linux-services-final.log, vm-reboot.json), 업데이트 실패 NOT RUN |
| S4-03 | 암호화 백업/복구/서명/고지 | 구현 예정 | 릴리스 | NOT RUN |
| S4-04 | 24시간 Pi 운영/성능 | 시험 계획 필요 | Pi 5 8GB/2TB | BLOCKED (장비 접근 없음) |
| S4-05 | 새 환경 재빌드 | Cargo.lock, web/requirements.lock | Linux VM | 진행 중 |

실행 artifact SHA256은 각 evidence JSON에 저장한다. 증거를 추가하면서 이 표를 갱신한다. 문서 작성만으로 동작 검증 PASS를 부여하지 않는다.

### 초기 데이터 볼륨 transaction 추가 증거

- 구현: `scripts/volume_setup.py`; 시험: `sudo python3 scripts/linux_volume_setup.py` (새 프로젝트 전용 2GiB JUSTVERIFY_TEST_DATA blank disk에만 실행).
- Debian ARM VM actual ext4 format/SIGKILL/UUID-bound recovery/ownership/isolated-fstab PASS: `.state/linux-volume-setup.log`. 실제 fstab 자동mount 재부팅/내용보존/원래fstab복원 PASS: `.state/linux-volume-reboot.log`.
- TUI/API 연결 및 초기profile등록 NOT RUN. 물리 설치/부팅 BLOCKED (대상장비 없음). 이 증거만으로 초기설치 또는 S4 완료 판정하지 않는다.

### 저장장치 owner API 경계

- 구현 `scripts/storage_service.py`, `image/systemd/justverify-storage.service`, `web/server.py` `/storage`; 검증 `sudo python3 tests/linux_storage_api.py` Debian ARM VM 실제 TLS/root Unix API PASS (`.state/linux-storage-api.log`). 로그인·Origin·CSRF·필드·peer권한·owner등록 경계와 실제 inventory를 검증했다.
- 설치 TUI 확인/owner API 실제format 성공경로/최초 profile 등록 NOT RUN. 새 unit 포함 이미지 부팅 NOT RUN. 기존 engine format/reboot 증거와 구분한다.

### TUI S volume 흐름

- 구현 `src/storage_ui.rs`, `src/tui.rs`, root inventory saved plans 및 interrupted guard. Linux actual PTY/rootAPI recovery review/cancel/UUID mount/proof-preservation PASS: `tests/linux_storage_tui.py`, `.state/linux-storage-tui-owner.log`.
- `cargo test --locked storage_ui`: 잘못된확인/Esc/system선택 mutation 미발생 단위 PASS. 실제TUI 새disk format 성공은 NOT RUN, 최초profile설정 NOT RUN, 새이미지/물리설치 acceptance는미충족.

### 실제 TUI 신규 데이터 디스크 초기화

- `tests/linux_storage_tui_format.py` / `.state/linux-storage-tui-format.log`: 새전용 ARM VM 2GiB JUSTVERIFY_UI_TEST에서 실제 non-root TUI→rootAPI→mkfs.ext4→UUIDmount/fstab PASS. 80×24 삭제확인/잘못된문구·취소시signature보존 PASS. 기존node data/fstab보존 PASS.
- 별도ownerfixture/시험mount/fstab에대한검증이다. 정상첫version/network등록 NOT RUN, 이미지설치/실제Pi부팅 BLOCKED 또는NOT RUN 상태유지.

### 최초 profile 등록 eligibility

- `scripts/profile_helper.py` check_initial + `src/version_service.rs` first preview/apply guard. 실제 VM ext4 mount/UUID/root journal/empty layout 및위험상태거부 PASS (`tests/linux_initial_volume.py`, `.state/linux-initial-volume.log`).
- 직접guard시험이며firstversion/Core/electrs 전체통합 NOT RUN. image startup gate/정상초기설치 acceptance 미완료.

### 정상 최초 version profile → Core/electrs

- `tests/linux_initial_profile.py`, `.state/linux-initial-profile-final.log`: production guard/allow_initial_selection=false에서 최초preview/apply, preview후변경거부, 실제Core31.1regtest/블록생성/electrsheight1 PASS. 기존VMnode복원·height2 PASS (`.state/electrs-rpc-startup-restored.log`).
- 발견된electrs cookie cold-start실패는 `scripts/wait_core_rpc.py` + electrs ExecStartPre로수정·실제재시험했다. ownerfixture/일시productionmount의통합시험으로, 설치이미지기동·자동first-run등록·물리Pi acceptance는아직미충족.

### 등록 전/후 서비스 시작 경계

- `scripts/node_ready.py`, `scripts/profile_helper.py`, Core/electrs/policy systemd units: 실제등록전inactive/등록후Core+electrs/UUID변조시MainPID0/복원기동 PASS (`.state/linux-registration-startup.log`).
- firstboot소유권·실제TLS·consoleTUI회귀 PASS (`.state/firstboot-registration-regression.log`). 등록profile의실제reboot 및최종설치이미지기동 NOT RUN, 물리장비gate 미충족.

### Volume 완료 후 version service 준비

- Production storage callback 및 `prepare_profile` ownerAPI: committed recovery완료→actualsystemd versionsactive/Coreinactive, 준비재시도무format, 후속firstprofile/Core/electrs PASS (`.state/linux-profile-preparation.log`).
- TUI B/FIRST PROFILE 안내구현; B키실제PTY NOT RUN. 새image/registered reboot/물리설치gate 미충족.

### dev3 설치 이미지 조립

- `image/build-pi.sh` actualARMbuild 및 `image/verify-pi.sh` readonly검증 PASS (`.state/image-dev3-build.log`, `.state/image-dev3-verify.log`). artifactSHA256 `3571842365fdc706f5d2feaabb6ce94133baa8a1bb6deff7925efb86240b203c` host/VM일치.
- versions/storage/roothelper/owner/nodegate packaging 및권한/실행파일검증을확대했다. 물리Pi부팅/전체이미지설치 NOT RUN/BLOCKED; reproducible/signed release미완료. RC gate충족아님.

### B 준비 → V 최초등록 화면 실제PTY

- `tests/pty_initial_profile.py` + `tests/linux_initial_profile.py`, `.state/linux-initial-profile-pty-final.log`: 실제non-rootTUI B 서비스준비/V FIRST PROFILE/network/review/cancel PASS, 취소시Core미기동/active없음확인. 후속실제Core/electrs통합도PASS.
- 앞선 B-key NOT RUN 항목을해결했다. registered VM reboot와실제이미지/Pi설치gate는여전히미충족.

### 등록profile 실제 재부팅

- Generic ARM VM에서production등록profile의actual reboot/newbootID/UUID·identity보존/Core31.1regtestheight1/electrsheight1/전체서비스기동 PASS (`.state/registered-reboot-verify.log`, `tests/linux_registered_reboot.py`). baseline복원/원래height2 PASS (`.state/registered-reboot-baseline.log`).
- registered VM reboot NOT RUN 항목을해결. 중단transition reboot복구, dev3image/physicalPi boot/모바일/soak gate는아직미충족.

### V/R interrupted-version recovery UI

- `src/versions.rs` recovery status, `src/version_service.rs` active_error, `src/version_ui.rs`/`src/tui.rs` R review. 실제missingtarget API상태조회/PTY review-cancel-recover/previous별도profile복구 PASS (`tests/pty_version_recovery.py`, `.state/version-recovery-tui.log`).
- journal주입시험으로한정. 실제versionapply중단후reboot복구 gate는아직NOT RUN.

### Actual version SIGKILL + reboot recovery

- `tests/interrupted_version_boot.py` + initial/reboot integration: 실제APIapply durable starting→servicecgroupSIGKILL→actualVMreboot→mismatchCorestartup차단→actualTUI R→prior31별도data/height1복구 PASS (`.state/interrupted-boot-prepare.log`, `.state/interrupted-boot-recovery.log`).
- interrupted-transition VM reboot NOT RUN을해결. journal주입시험과별도증거. 실제hardwarepowercut/Pi/image/mobile/soak gate는미충족.

### Client별 RPC 인증/폐기 기반

- `web/rpc_gateway.py` + owner `/rpc-clients` + TLS `/rpc`: 실제Core31.1regtest조회/개별발급·폐기/인증·CSRF·관리메서드차단·requestbudget/secret비저장 PASS (`.state/rpc-client-tls.log`). 기존WebSocket/TUI회귀 PASS.
- node-read범위만검증. 모바일앱/QR/watch-only/TorRPC/전체Core지원조합 acceptance는미충족.

### Client발급/폐기 TUI

- `src/client_ui.rs`/`web/manage_clients.py`: 실제PTY발급·secret숨김·폐기취소/확인→actualTLSCore조회/폐기후401 PASS (`.state/client-tui-tls-final.log`). 동시8개client기록보존 PASS (`.state/rpc-client-concurrent.log`).
- scope node-read 한정. 연결QR/mobile/walletwatch-only/TorRPC gate는아직미충족.

### Tor Electrum 실제 TUI QR

- Q popup actualPTY black/white quiet-zone matrix/resize fallback PASS (`.state/electrum-qr-pty.log`); 실제terminalcell재구성후zxingpayload일치 PASS (`.state/electrum-qr-decode.log`). pinnedqrcode8.2/공식mobile sourceaudit기록.
- 일반host:port QR이며Nunchuk/FullyNoded자동import또는physicalcamera성공으로해석하지않는다. 해당mobile gates는미충족.

### RPC root path / authentication persistence

- `web/server.py`, `tests/linux_client_tui.py`: Core31.1 ARM regtest / actual TLS / PTY root JSON-RPC1.0, anonymous/wallet/admin rejection, browser GET, process restart→persisted authentication→TUI revoke PASS (`.state/rpc-root-restart.log`).
- FullyNoded official source routing and commands pinned in `catalog/mobile-source-audit.json`; compatibility gaps recorded in `docs/MOBILE_CONNECTIONS.md`. Watch-only/mobile app acceptance remains unmet.

### dev5 image userspace first boot / actual reboot

- `image/build-pi.sh`, `image/verify-pi.sh`, `tests/image_boot_probe.py`: pristine image offline verification PASS; disposable copy + external Debian ARM kernel/module fixture firstboot→TLS owner registration→packaged browser TUI→actual reboot→identity preserved→owner login/TUI PASS (`docs/evidence/pi-image-dev5-verify.log`, `docs/evidence/image-dev5-virt-probe.json`).
- Inherited OS userconfig was found during dev4 boot and masked in dev5; actual boot verifies mask and PID0. No check removed or weakened.
- This satisfies additional generic image userspace evidence only. Actual Pi installation/boot, packaged firmware/kernel, physical console, mobile and full image data/profile setup requirements remain unmet.

### Watch-only internal per-client wallet isolation

- `web/watch_only.py`, `tests/watch_only_matrix.py`: 32 verified ARM Core versions real regtest create/import/private-key rejection/wallet separation/restart/clean shutdown PASS (`docs/evidence/watch-only-matrix.json`).
- This establishes wallet-engine compatibility only. Full watch-only profile activation, owner/UI/public gateway lifecycle and actual FullyNoded acceptance remain unmet. Default production wallet stays disabled.

### Watch-only profile selection / data separation

- `src/storage.rs`, `src/versions.rs`, `src/version_service.rs`, TUI V/W, `scripts/profile_helper.py` and `node_ready.py`: actual Core31.1/electrs Linux profile switching, separate data/index, wallet persistence, return to node, production startup gate and actual PTY review/cancel PASS (`docs/evidence/watch-profile-tui.log`, `docs/evidence/watch-profile-transition.log`).
- Uses existing journal/token/preflight/recovery; node-mode persisted records remain compatible. Full wallet-client authorization/RPC/PSBT/mobile gates remain unmet; no new image or physical Pi claim.

### Client wallet grants / TLS route isolation

- `web/wallet_gateway.py`, owner API, fixed helper and C/W UI: real Core31.1 TLS grant/import/query, per-client routing/list filtering, private-key denial, profile+volume binding, revoke and missing-wallet preservation PASS (`docs/evidence/wallet-gateway-tls.log`). Production selected profile + actual PTY review/cancel/confirm + TLS wallet check and mode-switch data preservation PASS (`docs/evidence/wallet-grant-production.log`).
- Wallet read/public-import scope is implemented. Full PSBT workflow, exact FullyNoded app compatibility, actual phones/camera and latest image inclusion remain required; do not mark S2/S3/S4 complete.

### PSBT preparation / signed transaction relay

- `web/watch_only.py`, wallet gateway, owner grant_transactions and TUI C/T: real TLS/Core32-version fund/no-node-sign/separate-test-sign/finalize/mempool/broadcast/confirm/revoke PASS (`docs/evidence/psbt-tls-matrix.json`). Final option/Origin guards and actual PTY permission review/cancel/display plus baseline restore PASS (`docs/evidence/psbt-final-regression.log`).
- Transaction permission is separate from existing watch-only read/import grants. No real hardware/mobile signer, complete target-app compatibility or latest image verification is claimed; those gates remain unmet.

### dev6 packaged wallet/PSBT source and bootstrap persistence

- Latest package/source byte equality/imports and readonly filesystem/service/identity checks PASS (`docs/evidence/pi-image-dev6-verify.log`). Generic image two-boot enrollment/client credentials/C/T menu persistence PASS (`docs/evidence/image-dev6-virt-probe.json`).
- Actual registered node/profile inside this image, Pi firmware/media/hardware and phones remain unmet. Do not infer those from source equality or authenticated unavailable-Core response.

### dev9 installed userspace / remote RPC / Quick Connect reboot gate

- `image/build-pi.sh` and `image/verify-pi.sh`: immutable dev9 ARM64 image build and read-only filesystem/component/identity/service verification PASS. Artifact SHA256 `604f4d8e813995503a7791c8cc8b1a589bbff0a81829298f0ded1e5054001c5c`; evidence `docs/evidence/pi-image-dev9-verify.log`.
- `tests/prepare_image_boot_probe.sh`, `tests/image_boot_probe.py`, `tests/image_data_probe.py`: fresh dedicated data disk first boot through owner/storage/Core31.1 watch-only/electrs/wallet/PSBT/LAN TLS and actual product Tor RPC, authenticated browser TUI remote state and sensitive Quick Connect QR PASS; actual reboot then identity/data/client/remote-listener/onion RPC recovery PASS (`docs/evidence/image-dev9-data-probe.json`). Anonymous onion RPC401 and non-RPC `/login`404 were required.
- Generic QEMU userspace uses an external Debian kernel/initramfs/module tree. Raspberry Pi firmware/EEPROM/HAT/media, real phone application/camera/separate LAN trust, signer and soak are NOT RUN or BLOCKED. This closes the corresponding generic-image integration evidence only and does not satisfy physical S4 or final RC gates.

## 2026-09-12 source/public-network audit additions

| Requirement | Implementation / command | Target | Result / evidence |
|---|---|---|---|
| Official source correspondence | docs/UMBREL_PARITY.md, upstream-audit.json | fixed Umbrel/Core/electrs commits | PARTIAL: full key inventory, general settings UI gaps retained |
| Signed transaction life cycle | tests/signed_chain_audit.py | Core31.1/electrs0.11.1 macOS ARM regtest | PASS confirmations0/1/3, tip/hash and restart; signed-chain-audit.json |
| Published RPC methods | tests/wallet_gateway_tls.py | Core22.0 and31.1 Debian ARM regtest | PASS37 exposed methods; RPC_AUDIT.md; other Core methods help-only or NOT RUN |
| Tor outbound | tests/linux_tor_outbound.py | actual product Tor + Core31.1 regtest | PASS SOCKS/P2P handshake and effective proxy; tor-outbound-audit.log |
| Collector tip correctness | src/lib.rs + tests/linux_initial_profile.py | registered Debian ARM product services | PASS hash/height/IBD gate; upstream-profile-audit.log |
| Reboot persistence | tests/linux_registered_reboot.py | actual Debian ARM VM reboot | PASS new boot ID/config/UUID/Core/electrs/proxy/collector; upstream-reboot-audit.log |
| Public testnet4 full sync and spend | scripts/public_testnet_audit.py | Core31.1/electrs0.11.1 independent host datadir | RUNNING; do not infer PASS from progress |


### 2026-09-12 incoming and policy metadata audit

| Requirement | Implementation | Command / environment | Result / evidence |
|---|---|---|---|
| Incoming Clearnet/Tor independent selection | src/policy.rs, policy_service.rs | JV_CORE_MATRIX=/home/builder/core-matrix cargo test --test incoming_preflight -- --ignored --nocapture; official ARM22-31.1 | PASS128 modes, evidence/incoming-preflight-matrix.log; preflight uses remapped loopback ports |
| Actual bind application, RPC isolation, electrs continuity, TUI | tests/linux_incoming_policy.py, linux_policy_tui.py via linux_initial_profile.py | Debian ARM VM, Core31.1/electrs0.11.1 | PASS evidence/incoming-profile-audit.log |
| Rejected incoming startup rolls back safely | image/restart-core.sh, policy service; tests/linux_incoming_rollback.py | Actually occupy onion backend; authenticated Core readiness bounded before starting electrs | PASS evidence/incoming-rollback-audit.log; initial long helper wait timed out, fixed/retested |
| Selected incoming/outgoing survive reboot | linux_registered_reboot.py | Actual VM reboot of registered disposable volume | PASS evidence/incoming-reboot-audit.log, baseline restored; Pi BLOCKED |
| Catalog network/version consistency | scripts/policy_catalog.py | Inherit release-supported network list, regenerate executed-help catalogs | Metadata fixed; no previously unsupported network enabled |


### Resources, indexes and confirmed public transaction

| Requirement | Implementation / execution | Result / evidence |
|---|---|---|
| Resource defaults/ranges/units/application | scripts/resource_catalog.py, src/policy.rs; resource_preflight matrix32 releases | PASS source/real startup/native settings + observed connection limit/upload bytes; evidence/resource-preflight-matrix.log |
| Actual resource service/TUI behavior | linux_resource_policy.py / linux_policy_tui.py under registered Linux fixture | PASS ban duration, upload bytes, Core/index continuity and saved values; evidence/resource-profile-audit.log |
| Index/filter/REST/ASMAP version support and application | auxiliary_preflight32 releases x2 modes, linux_auxiliary_policy.py | PASS actual index RPCs/service flags/REST/logs, index completion and real block filter; evidence/auxiliary-preflight-matrix.log and auxiliary-profile-audit.log |
| Signed confirmed transaction and Core indexes after restart | signed_chain_audit.py --core-indexes, real native31.1/electrs0.11.1 | PASS confirmations0/1/3, all indexes104, indexed spending tx and block filter; evidence/signed-chain-index-restart-audit.json |
| Public testnet4 confirmed propagation and indexing | public_testnet_audit.py --observe | PASS block151996, Core wallet+independent confirmation, electrs history and Merkle proof; evidence/public-testnet4-audit.json |
| privatebroadcast configuration support | 31.1 main/testnet4/signet isolated preflight with networkactive=0 | PASS startup; transport/anonymity NOT RUN.31.0 enable refused due documented upstream IP leak; evidence/private-broadcast-preflight.log |
| Updated pristine image and full installed reboot | extended image_data_probe.py + verify-pi.sh | NOT RUN pending dev10 build; dev9 does not contain current changes |

## 2026-09-12 historical P2P and image regression

| Requirement | Implementation / actual command | Result / evidence |
|---|---|---|
| Finite upload cap must not stall electrs historical index | profile_helper.py, policy.rs/service; `python3 scripts/historical_index_matrix.py` uses32 checksum-verified ARM Core builds and real electrs0.11.1 | PASS32: ordinary P2P historical download actually refused, separate download,noban backend indexes65 real blocks, header tip exact, cap unchanged. historical-index-matrix.json + per-version records; native31.1 also PASS |
| Backend not exposed as external wallet endpoint | loopback network P2P+2; linux_incoming_policy.py checks all4 modes, LAN backend closed, matching electrs config, exact permissions; Tor incoming must lack download/noban | Registered integration PASS before reboot; complete log pending restoration |
| dev10 pristine image | clean9ec13c8 build, read-only verify, actual data install and reboot | Read-only PASS; first boot PASS, second Tor timeout FAIL: image-dev10-data-probe.json. Independent dev10b bootstrap100 then circuit timeout FAIL: image-dev10b-data-probe.json. Not RC; new backend absent from dev10 |

- **dev11 actual image PASS**: clean application11c8419, observerc9b05e9, SHA256160b202f895b10f15aa9e9ca33bead39b950f813c1ed3cfdffff2fcc8f168f74. Fresh virtual disk format/registration→Core31.1 watch-only→real block/electrs index→20 selected network/resource/index policies→TLS wallet/PSBT→authenticated Tor RPC→real packaged TUI/Quick Connect/connection display→actual reboot→same data UUID, identities, wallet, policy/index/tip→authenticated Tor RPC/TUI again. First34.96s/second24.95s. `image-dev11-data-probe.json`, read-only `pi-image-dev11-verify.log`. Physical Pi/mobile/24h and other release gates remain incomplete. dev10/dev10b failures retained.


## 백업 보강 추가 증거 — 2026-09-12

| 항목 | 구현/명령 | 환경 | 결과/증거 |
|---|---|---|---|
| 선택 정책 및 root 경계 | scripts/backup_guard.py, profile_helper.py, backup_bundle.py; JV_BACKUP_AUDIT=1 JV_BACKUP_ONLY=1 tests/linux_initial_profile.py | Debian ARM64 / Core31.1 / electrs0.11.1 / 실제 regtest | PASS, evidence/backup-hardening.json |
| 실제 서비스 백업/복원 및 중단 | tests/linux_backup_production.py, systemd-run Unix API / NoNewPrivileges / 제한 주소군 | 동일 등록 시험 볼륨 | PASS 420→430→420, health 실패430 rollback, SIGKILL 후430 복구. TLS 헤더와 Core 해시 대조 |
| 소유자 재인증/터미널 | tests/linux_backup_service.py | 비권한 120×40 PTY, 실제 root Unix API·GPG; 서비스 callback은 UI 범위용 | PASS, backup-tui-reauth-retry10.log; 실제 Core 서비스 증거는 위 별도 시험 |
| 형식/암호화/경로 | tests/backup_bundle.py | macOS 실제 GPG2.5.22, 격리 파일 | PASS; secret fixture는 실제 서비스 연결 증거로 사용하지 않음 |
| 재설치/전원 차단/모바일 복원 | 아직 해당 실행 없음 | Pi5 NVMe 예정 | NOT RUN; 전체 복구 완료 아님 |
| Python 잠금 설치 | web/requirements.arm64.lock; pip install --no-index --require-hashes / pip check | 새 Linux ARM64 CPython3.13 venv | PASS 11 wheels; OS와 이미지 전체 재현성은 별도 NOT RUN |


## 실제 거래 정책 확장 — 전체 정책 완료는 아님

`tests/policy_semantics.py`와 `scripts/policy_semantics_matrix.py`: 검증한 공식 ARM64 Core32개 버전 PASS, 공식 철회30.0/30.1 BLOCKED. 실제 서명/브로드캐스트/5MB 압력/재시작/보존시간/채굴 수수료 및 표준성 경계를 시험했다. `scripts/policy_confirmation_audit.py`는 지갑과 mempool 로드를 끈 동일 버전 Core로 저장된 블록을 조회하여 confirmed 또는 consensus block acceptance로 기록한 모든 txid의 블록 포함을 대조했다. 결과/txid/높이/hash/설정은 `evidence/policy-semantics/*.json`, source commit은 `catalog/core-source-commits.json`.

10개 정책 키의 선택한 행동 사례에 대한 증거다. 전체 범위, topology/cluster/RBF/bytespersigop/whitelist/privatebroadcast 등 나머지 행동, public network의 모든 설정 조합을 대신하지 않는다. 새 이미지의 설치/부팅 및 Pi 시험도 별도다.

### 단일 NVMe 설치 전환 (2026-09-12)

| 항목 | 구현·검증 | 결과·증거 |
|---|---|---|
| 단일 OS·동일 디스크 데이터 초기 준비 | scripts/factory_volume.py, scripts/build_single_disk.py, image/firstboot.sh | 실제 GPT/ext4 loop 시험 PASS; docs/evidence/single-os-factory-volume.json |
| 초기 준비 강제 종료 복구 | tests/linux_factory_volume.py; commit 직전 실제 SIGKILL 후 unmount/replay | PASS 계획 UUID·OS 파일·노드 파일 보존; OS 재부팅 시험과 별개 |
| 단일 디스크 이미지 최초·재부팅 | tests/image_data_probe.py factory branch; scripts/run_image_probe.py (data disk 없음) | dev14 FAIL 보존; dev15 최초/재부팅 PASS, docs/evidence/image-dev15-single-probe.json |
| balenaEtcher 기록·Pi5 NVMe 부팅 | 지정 물리 NVMe·Pi5 | BLOCKED 장치 연결·IP 아직 없음; A/B 검증 요구 없음 |

A/B 실험은 사용자 지시로 제품 설계에서 제외했다. 기존 정책·백업·설치·실패 복구의 필수 결과를 이 변경으로 통과 처리하지 않는다.

| 거래 관계·RBF·증분 수수료 | tests/policy_topology.py / scripts/policy_topology_matrix.py | 32개 실제 공식 Core PASS, 철회2개 BLOCKED; docs/evidence/policy-topology-matrix.json 및 policy-topology/*.json. 174개 카탈로그 행에 증거 연결; 전체 입력 범위는 미검증 |

| 단일 NVMe UUID 장애 차단·재부팅 복구 | tests/image_volume_fault.py + dev15 실제 QEMU | PASS; docs/evidence/image-dev15-volume-fault.json. 명시적 시험 수리 후 복구이며 자동 UUID 채택 아님 |
| dev15 artifact 정합성·실험용 서명 | frozen e5c1737 source / image/verify-pi.sh / scripts/verify_development_bundle.py | PASS .state/dev15-frozen-offline-verification.log 및 dev15-bundle-verification.log; Pi 실기·최종 릴리스 승인 아님 |


## 2026-09-12 Core 중심 화면 변경

src/dashboard.rs, src/tui.rs, web/static: 실제 Core31.1 격리 regtest recent headers/reorg/offline + 120/80/42열 PTY PASS (`tests/dashboard_live.py`, `docs/evidence/dashboard-live.json`). 실기 Pi5 비권한 TUI/메뉴 PASS. HTTP/HTTPS 인증 회귀 PASS. 해당 변경 후 새 이미지 부팅 및 사용자 브라우저 로그인 후 육안 확인 NOT RUN. 기존 동기화/지갑/복구 필수 기준 유지.


## 반응형·QR 후속 검증 (2026-09-12)

`web/static/dashboard.js`, `web/server.py`, `web/electrum_qr.py`, `src/dashboard.rs`: 데스크톱/모바일390px 브라우저 레이아웃·native42/80/120열·실제 Pi 미설정 상태 및 Safari 메인 정렬 PASS. 이미지 QR 두 네트워크 실제 PNG·스크린샷 exact decode PASS. auth/CSRF/Origin/logout 및 HTTP/HTTPS TUI 회귀 PASS. 증거 docs/evidence/responsive-ui.json, 상세 private .state/browser-ui. 실제 Pi 노드 연결/휴대폰 카메라·지갑/새 이미지 부팅은 별도 미완료 기준 유지.

### 2026-09-12 브라우저 설정·초기 노드 시작 후속 검증

| 요구 | 구현 | 실제 검증 및 범위 | 증거 |
|---|---|---|---|
| 새로고침 로그인 유지 | web/server.py `/session`, web/static/app.js | HTTP 실서버 cookie 복원/로그아웃 폐기/Origin 차단 및 실제 Pi·Linux browser reload PASS. web 재시작/재부팅 시 재로그인은 유지 | docs/evidence/browser-settings.json |
| 실제 Pi 동기화 시작 | web/node_admin.py Startup → storage/versions/profile helper | Pi5/8GB/NVMe2TB, Core31.1 main, 실제 신규 등록·헤더/블록 증가·재부팅 후 계속 증가 PASS; 전체 IBD와 electrs index 완료는 미충족 | 같은 증거, .state/pi5-install/settings-*-reboot.json |
| Electrs·버전 변경·피어 메뉴 정리 | web/static/index.html | 실제 desktop/mobile DOM 및 화면 PASS; 피어 전체는 overview에 표시 | .state/browser-ui/settings-*.png |
| 설정 토글 및 저장 | web/static/settings.js, web/server.py → Rust policy service | 실제31.1 regtest API 및 browser toggle→preview→apply→서비스 재시작→파일 유지, uploadtarget RPC 및 maxconnections startup limit, electrs height PASS | .state/browser-ui/settings-integration-audit.log |
| 버전 클릭·hover·실제 적용 | settings.js → version service | 실제 browser31.1→23.2→31.1, 각 버전 별도 데이터 및 복귀 PASS; selected=false인 다른 카드 hover CSS 상태도 실관측 | docs/evidence/browser-settings.json |
| 설치물 반영 | Pi `/opt/justverify/web`, 21파일 SHA256 대조 | Pi 실배포/HTTP200/실재부팅 PASS. 이번 변경을 포함한 새 설치 이미지 빌드·부팅 NOT RUN | .state/pi5-install/settings-deploy-verification.json |

## 2026-09-12 일반 설정 추가 요구

| 요구 | 구현 | 실제 결과 |
|---|---|---|
| 상단 오른쪽 로그아웃, 로고80% | web/static/index.html, app.css | Pi browser PASS:21/16.8px, center delta0 |
| 네 가지 색상·설정 저장 | web/static/device.js, device_settings.py | Linux API + Pi desktop/mobile PASS |
| 기기·OS·IP·Uptime·전원 | scripts/device_service.py, device unit | 실제 Pi facts PASS; VM reboot/poweroff/cold start PASS |
| 웹 계정명·암호 변경 | device_settings.py | 격리 owner 암호 회전/세션폐기 PASS; 실사용 암호 보존 |
| ko/en/ja 웹 화면 | web/static/i18n.js | Pi browser 및 persisted preferences PASS; 기존 native 상세 TUI 번역은 범위 밖 미완료 |
| Remote Tor access | remote_web.py, torrc, publish_onions.py | 실제 Tor HTTP 및 same-session disable PASS; RPC 경계 회귀 PASS |
| 백업·실기 배포 | backup_bundle.py, backup_guard.py, build-pi.sh | 실제4개Tor GPG복구/legacy호환/Pi snapshot PASS;32개배포파일SHA 일치 |

증거와 명령은 docs/DEVICE_SETTINGS.md 및 .state/device-settings/. 새 이미지 부팅·전체 IBD/electrs 완료·실제 모바일 지갑·최종RC 판정은 이번 UI 검증으로 대체하지 않는다.
