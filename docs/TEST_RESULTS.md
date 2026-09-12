# 실행한 검증

## 0.1.0-beta1 — 2026-09-12

- 실제 ARM Core31.1 및22.0 + electrs0.11.1 + mempool3.3.1 regtest: 생성·서명·HTTP broadcast→미확인→2확인,107높이/hash/주소잔액/WS/SQL·backend·Core·electrs 중단 및 복구 PASS. tests/mempool_live.py, evidence/beta1-mempool-regtest.json 및 beta1-mempool-core22.json.
- 실제 chain 불일치 사전 차단, 프로필 전환과 별도 SQL 보존 PASS: tests/mempool_profile_live.py, evidence/beta1-mempool-profile.json.
- 실제 브라우저 테마/refresh session/390px/전체 문구/3언어 링크 PASS: evidence/beta1-responsive-ui.json. Cargo locked 시험·ARM 앱·네이티브 mempool 빌드 PASS; 기존 ignored 통합시험은 통과로 세지 않음.
- 최종 image byte/source/runtime/identity absence/systemd/fsck/xz/hash PASS: evidence/beta1-image-file.json. 첫 설치·Core/electrs/PSBT·HTTP/TUI/QR·멤풀 DB/tip PASS, cold Tor onion timeout으로 전체 부팅 probe FAIL: evidence/image-beta1-r3-boot.json.
- 같은 clone에서 별도 실제 복구 및 재부팅 PASS2회: 신원/UUID/tip/인덱스/지갑/정책, 멤풀 DB·3언어·tip 및 실제 Tor RPC200·401/404. evidence/image-beta1-recovery.json. 기존 cold-boot FAIL은 유지한다.
- r1/r2 초기 등록 실패, 잘린 r3복사본 실패, 실제 electrs false-ready 발견과 수정 후 재시험은 STATUS 및 각 실패 evidence에 보존. 제품 데이터/테스트 삭제 또는 mock 대체로 통과시키지 않았다.
- 새 beta1 Pi5/물리 휴대폰/전체 정책·복구·장시간·재현 빌드 등 미완료 범위는 ACCEPTANCE를 따른다.

- 제품 Tor RPC/TUI: 실제 Debian ARM64 등록 프로필에서 비권한 C/O 검토 취소·오암호 거부·마스킹 재인증·enable/disable, 실제 Core31.1 조회, 웹 프로세스 재시작 후 committed 복원 PASS. Private 0700/0600 Unix IPC, 다른 UID 및 중복 서버 차단 PASS. 제품 systemd Tor가 생성한 별도 v3 onion을 통해 인증 요청 PASS, 익명401·관리 경로404. 같은 실행에서 watch-only 지갑 및 거래 권한/PSBT 회귀 PASS. `docs/evidence/remote-rpc-tui-tor.log`.
- Fully Noded Quick Connect: 공식 앱 commit `d0d1502eef2840c0457aa321b88cf606ee8b4650`의 btcrpc URI 필드 전체를 검증하고 QR을 디지털 decoder로 정확히 복원했다. 실제 PTY는 민감 QR을 명시적 Q 입력 뒤에만 표시하고 흑백 모듈 일치, quiet zone, 80×24 잘림 거부 PASS. 비밀 원문은 evidence·설정·로그에 없음. `docs/evidence/rpc-quick-connect-qr.json`. 실제 앱/카메라는 NOT RUN.

- 원격 RPC 소유자 설정: `tests/remote_rpc_control.py` 실제 HTTPS + 기존 개발 regtest Core 읽기 전용 조회 PASS. 기본 포트 닫힘, 미리보기 무변경, 소유자/CSRF/재인증, 적용/비활성화, 서버 소켓·객체 재생성 후 복원, `applying` 파일 시작 거부 및 재검토, 실제 점유 포트 실패 후 HTTPS 복구 PASS. 미완료 파일은 시험에서 직접 기록했으므로 실제 프로세스 강제 종료/재부팅 시험으로 해석하지 않는다. 증거 `docs/evidence/remote-rpc-control.log`; 기존 Core31.1 지갑/PSBT 회귀도 PASS.

- Tor RPC 전송: 실제 ARM Core22.0/31.1 + HTTPS/선택적 loopback listener에서 권한·배정 지갑·관리 경로404·GET405·두 listener 합산30회 제한·폐기 후401 PASS. Core31.1은 별도 Tor daemon(동일 시험 인스턴스가 client/hidden service 제공)의 실제 SOCKS/v3 onion을 통해 인증401/실제 높이/지갑 조회/관리 경로404/폐기401까지 PASS. `docs/evidence/tor-rpc-transport.log`. listener cleanup 후 포트 닫힘과 기존 서비스 보존 확인. 모바일 앱/제품 활성화 UI/이미지 시험은 별도다.

- dev8 오프라인 검증 및 두 차례 실제 generic ARM 이미지 부팅 PASS. source/module/unit 비교, identity 부재, 파일시스템/런타임 확인과 새 데이터 볼륨 설정·Core31.1 watch-only/regtest·electrs height1·TLS50002·지갑/PSBT/coin-control·실제 Q/L TUI·재부팅 후 보존을 확인했다. `docs/evidence/pi-image-dev8-verify.log`, `docs/evidence/image-dev8-data-probe.json`. 외부 Debian 커널/모듈과 시험 observer를 추가한 사본이며 Pi 실기/실제 모바일 앱과 구분한다.

- LAN TLS와 실제 등록 프로필 통합 PASS: `sudo /opt/justverify-tests/bin/python tests/linux_initial_profile.py`가 `/opt/justverify/venv/bin/python tests/linux_electrum_tls.py`와 실제 PTY LAN QR 검증을 호출한다. 먼저 새 TLS unit/script를 설치·enable한 개발 ARM VM 대상이다. 신뢰한 인증서와 실제 electrs header, 미신뢰/평문/비LAN 주소 차단, backend/TLS 재시작, 반복 node/watch-only 프로필 전환을 확인했다. 증거 `docs/evidence/electrum-tls-profile.log`. 임시 주소와 이전 데이터/프로필 복구 PASS.
- 실제 PTY에서 추출한 LAN QR 모듈을 `tests/qr_capture_decode.py`로 해독하여 원문 일치 PASS (`docs/evidence/electrum-lan-qr-decode.json`). 예제 문자열을 새 QR로 만들어 시험한 것이 아니다. 카메라/앱/새 이미지 부팅은 별도다.

- UTXO 잠금/해제 실제 TLS/Core matrix: 공식 ARM Core 32개 버전 PASS. 잠금 조회, 별도 거래 권한, 전량 잠금 후 자금 선택 불가, 일부 해제 후 PSBT 자금 선택 성공, 다른 배정 지갑 격리, 잘못된 bool/outpoint/옵션 거부 및 잠금 상태 보존. 기존 PSBT 서명 금지·별도 시험 서명·전파·확정·폐기 시험도 같은 실행에서 PASS. `docs/evidence/coin-control-tls-matrix.json`; 명령 `tests/wallet_gateway_tls.py <version>`을 배포 Python venv로 실행. 실제 휴대폰 및 최신 이미지 통합은 별도다.

- dev7 원본의 오프라인 검증 및 시험 사본의 실제 두 차례 부팅 PASS: `docs/evidence/pi-image-dev7-verify.log`, `docs/evidence/image-dev7-data-probe.json`. Source 수정 없이 시험 도구와 외부 Debian 커널/모듈만 추가했다. 최초 설정 직후 UUID 조회, watch-only Core31.1/regtest, electrs height1, TLS 지갑/PSBT, 실제 웹 TUI, 재부팅 후 UUID·체인·지갑·Tor 주소·로그인 보존을 확인했다. Pi 실기와 실제 모바일 앱은 미검증이다.

- 저장장치 초기 설정 이미지 통합: dev6 원본에서 committed 후 UUID 조회 실패 재현. 수정 후 새 ext4 파일의 실제 마운트에서 root/justverify 즉시 UUID 조회 PASS. 수정 이미지 사본의 최초 HTTPS 설정, 실제 Core31.1/electrs, watch-only 지갑/PSBT, TUI, 재부팅 후 데이터·Tor 주소·인증 보존 PASS. 증거: `docs/evidence/image-dev6-data-initial-failure.json`, `docs/evidence/volume-mount-identity.log`, `docs/evidence/image-dev6-patched-data-probe.json`. 외부 커널 가상 머신 범위이며 dev7 원본 및 Pi 실기 시험은 별도다.

2026-09-12 macOS arm64:

- `cargo test`: 3 PASS. terminal injection 제거, 정수 수수료 변환 및 잘못된 입력, stale 보존. `evidence/cargo-test-initial.log`.
- `python scripts/fetch_core.py 31.1 arm64-apple-darwin`: 최초 신뢰 서명 부재로 차단. 공식 contact fingerprint 대조 후 Ava Chow 키를 고정하여 서명+checksum PASS. ARM Linux 바이너리도 PASS.
- `python scripts/regtest_smoke.py`: 실제 Core + Rust daemon + PTY TUI, 생성 블록 3, stop/stale/restart PASS. cookie 미노출 검증 포함.
- `python tests/web_security.py`: 실제 TLS 연결, 소유권 토큰, 인증/Origin/CSRF/로그아웃/횟수 제한, 고정 TUI 종료 후 WS 종료 PASS.
- electrs 0.11.1 `cargo build --release --locked`: libclang 동적 로더 실패. CommandLineTools의 libclang 경로를 명시하여 재빌드 PASS. 원본 실패 로그 보존.
- `python scripts/electrs_smoke.py`: Core 31.1 P2P/RPC 인덱싱, Electrum headers 및 scripthash history, 인덱서 재시작 보존 PASS. mempool 전파 및 실지갑 연결은 별도 미검증.
- QEMU Debian 13 ARM64 VM 실제 첫 부팅 및 systemd running PASS. 제품 Pi 이미지 부팅 검증으로 계산하지 않음.

모든 소스/전체 버전/제품 기능이 완료된 상태는 아니다. 남은 요구사항은 ACCEPTANCE.md 참고.

## 추가 Linux/통합 검증

- 전체 ARM Linux Core 32개 + electrs0.11.1 실제 regtest 조합 PASS. 30.0/30.1 공식 철회로 다운로드 불가(공지 기록). 모든 조합의 실제 거래 인지/전파/확정/restart 검사 포함.
- Pi 개발 이미지 구조 검사 PASS: `pi-image-verify-scratch.log`. 이미지 부팅 PASS를 뜻하지 않는다. 최초 readonly Core 실행에서 데이터/설정 쓰기 실패: 외부 임시 data bind를 제공하여 image readonly를 유지하고 실행 확인.
- systemd regtest 설정 오류: connect=0이 global section에 있어 Core 거부. [regtest]로 이동 수정.
- mount 실패 시험의 최초 잘못된 조건: umount만 하면 RequiresMountsFor가 정상적으로 remount했다. backing 가상 파일을 일시 rename하여 실제 부재를 재현하고 데이터가 system disk로 흘러가지 않음을 검증. 정상 복구 후 테스트 성공.
- 실제 낮은 디스크 여유 startup 차단 및 복구 PASS, VM reboot 후 자동 mount/Core/manager/web 복구 PASS.
- Tor public circuit 및 실제 onion Electrum 조회 PASS. Tor 재시작 첫 시도에서 이전 프로세스의 listener 해제 전 port 충돌 발생; 종료 확인 후 시작 성공.
- QR digital roundtrip PASS. 실제 카메라/앱은 별도 BLOCKED/NOT RUN.

새로운 source 변경은 첫 image에 아직 반영되지 않았다. 최종 통합 및 image rebuild가 남았다.

## 정책 설정·프로세스 중단·서비스 구성 검증

- `cargo test --locked`: 단위/경계 시험 PASS (`policy-validation-final.log`). 실제 Core 통합은 명시적으로 별도 실행한다.
- `JV_CORE_BIN=.../bitcoin-31.1/bin/bitcoind cargo test --locked --test policy_integration -- --ignored --nocapture`: Core31.1 실제 preflight, fee 적용/RPC 관측, 오래된 preview 차단, 실제 startup 실패 복구, 프로세스 SIGKILL 이후 journal 복구 PASS (`policy-recovery-integration.log`). 전체 정책의 거래 수용/거부 검증은 남음.
- VM `tests/linux_policy_api.py`: 실제 서비스 재시작을 통한 변경/복원, 단위, 일회성 token, 추가 API 필드/임의 sudo/extra helper 인자 거부 PASS (`linux-policy-api-ready.log`). serde unit variant의 추가 필드 무시 문제를 명시적 key 검증으로 수정했다.
- VM `tests/linux_policy_tui.py`: 실제 PTY + pyte VT 상태 해석으로 편집/검토/취소/적용/Core 관측 PASS (`linux-policy-tui-vt-ready.log`). differential ANSI 원문 substring 검사를 화면 상태 검사로 교체했다.
- VM root `tests/linux_policy_crash.py`: 실제 Core 프로세스 SIGSTOP으로 restart 경계를 확보하고 policy 서비스 SIGKILL. systemd 재기동, TUI 경고, 복구 취소, 복구 확정 및 이전 값/건강 상태 확인 PASS (`linux-policy-crash-tui-socket.log`). 최초 readiness race 및 시험 명령의 필수 --socket 누락은 수정했으며 실패 로그 보존.
- VM `tests/linux_network_services.py`: 실제 생성 regtest 블록 인덱싱, electrs 재시작, Tor 분리 identity 및 재시작 보존, private key 권한 PASS (`linux-network-services-test.log`). onion transport는 로그의 별도 최종 결과를 확인한다.
- 이미지 스크립트 syntax PASS. 새 policy/electrs/Tor 포함 이미지 재빌드 및 chroot/부팅은 아직 NOT RUN.

- 공통 정책 matrix: 32개 verified ARM Linux Core 전체 실제 격리 기동 및 8개 입력/RPC 관측 PASS (`policy-matrix-run.log`, `policy-matrix-summary.json`). 전체 옵션 semantic/transaction behavior는 별도 미완료.
- dev2 이미지: 실제 빌드 및 read-only fsck, Core/electrs hashes, 실행파일, Tor0.4.9.11, sudoers, systemd, 공통 identity 부재 PASS (`pi-image-dev2-verify.log`, `pi-image-dev2.json`). host/VM SHA256 일치. 실제 Pi boot는 BLOCKED.

## Core 버전 전환

- Linux ARM `JV_CORE_MATRIX=/home/builder/core-matrix JV_ELECTRS_BIN=/home/builder/electrs/target/release/electrs cargo test --release --locked --test version_transition -- --ignored --nocapture` PASS (`version-transition-recovery-final.log`, `version-transition.json`).
- 실제 Core31.1→22.0→31.1 및 electrs0.11.1 전환. 22.0이 빈 데이터로 시작한 것을 먼저 관측하고 fixture 블록 생성. 31.1 복귀 시 이전 생성 블록/인덱스 보존. 실제 잘못된 target startup 인자로 실패를 주입하고 이전 Core+electrs 복구 확인.
- 별도 전환 프로세스를 실제 SIGKILL: 이전 서비스를 정지하고 selector를 저장한 후 종료. target binary 경로까지 제거한 상태에서 durable journal로 이전 verified Core/electrs 데이터 복구 PASS.
- 기존 active data 유실/루트 디렉터리 교체 시 새 빈 체인 생성 차단, upstream 철회 버전/지원하지 않는 network 거부 PASS.
- 최초 두 실패는 빈 regtest IBD 상태의 electrs readiness를 요구한 시험 전제 및 종료 대기와 관련되었다 (`version-transition-run.log`, `version-transition-regtest-ready.log`). 실제 블록으로 동기화 fixture를 구성한 뒤 성공 (`version-transition-seeded.log`); 테스트 기준을 제거하지 않았다.
- native systemd profile 전환, UI 버전 선택, 다운로드/서명 검증 연결은 아직 NOT RUN. 기존 32개 matrix는 전체 개별 바이너리/조합 검증이며 이 전환 시험은 22.0↔31.1 경로에 한정한다.

## 운영 버전 API/TUI 실제 시험

- `scripts/vm_install_profile_helper.sh`, `tests/linux_profile_helper.py`: root bridge 입력 제한, systemd31.1↔22.0 전환, version별 cookie/data/index path, Core/electrs/collector/policy restart 및 원본 개발 profile/높이 복원 PASS (`linux-profile-helper-tor-stable.log`). 초기 불필요한 Tor restart rate-limit 실패는 원인 수정 후 재검증.
- `scripts/vm_install_version_service.sh` 후 `sudo /opt/justverify-tests/bin/python tests/linux_version_api.py`: 실제 비권한 API 및 root bridge, 34 release 목록, 일회성 token, 추가 필드 거부, 실제 PTY V/network/review/Escape/Enter 흐름과 31.1→22.0→31.1 PASS (`linux-version-tui-bootstrap-guard.log`). 초기 ProtectSystem 상속으로 profile 쓰기 실패는 고정 root-owned 경로 mount 예외로 수정하여 PASS (`linux-version-api-profile-writes.log`).
- `tests/linux_version_registration_guard.py`: 운영 기본 설정에서 unregistered active profile 교체 preview 거부 PASS (`version-registration-guard.log`).
- 새 공유 operation lock을 적용한 정책 API 실제 수정/복원 regression PASS (`policy-api-shared-lock.log`). `cargo test --locked` PASS (`version-ui-unit.log`). Core/electrs 전환 엔진의 별도 강제 종료 시험은 직전 evidence 유지.
- 운영 network 전환 전체 matrix, 자동 다운로드/서명 연결, firstboot baseline 등록, version-service가 포함된 새 image 및 이미지 부팅은 아직 NOT RUN. VM 시험 후 원본 개발 profile을 복원하고 version service는 stopped 상태로 두었다.

## 운영 공식 Core 다운로드

- `tests/linux_download.py`: Core23.2 공식 archive 다운로드, 실제 trusted GPG signer/checksum, root executable hash 확인, active profile 불변, 동시 다운로드 거부, upstream 철회/arbitrary URL 거부, 다운로드된 바이너리의 실제 preflight PASS (`linux-download-accessible.log`). 처음 새 archive를 받았으나 설치 상위 directory가700으로 생성되어 접근 실패; directory755 수정 후 같은 공식 cache를 재검증하여 성공. 따라서 마지막 재시험 자체를 새 네트워크 다운로드로 해석하지 않는다.
- 초기 VM에 GPG가 없어 dependency 확인에서 중단; 실제 gnupg 설치 후 진행 (`linux-download-gpg-install.log`).
- `tests/linux_download_rejection.py`: signed SHA256SUMS 본문을 실제 수정하여 GPG BADSIG 거부 확인. 설치된 바이너리 hash 불변. staging executable을 잘못된 bytes로 바꾸어 root installer 거부 확인. 원본 복원 후 재검증/설치 성공 (`linux-download-rejection.log`). 검증기나 테스트 기대값을 mock으로 교체하지 않았다.
- `tests/linux_download_tui.py`: 실제120×40 PTY에서 V/P/버전선택/D 및 background complete 표시 PASS (`linux-download-tui.log`). 마지막 시험은 official cache의 재검증 경로다.
- Rust cargo test PASS (`download-unit.log`). signature pipeline의 변경은 경로/직렬화 지원이며 기존 verifier를 유지했다.
- 전체 artifact download UI matrix, download 중 프로세스 강제종료/재개, 새 설치 이미지 통합은 NOT RUN. 기존32개 signature/개별 Core/electrs matrix와 운영23.2 download 증거의 범위를 구분한다.

## 최초 소유권과 첫 TLS 신뢰

- macOS `tests/headless_pairing.py`: 실제 TLS server/certificate 생성, owner file 소비, 반복 생성 identity 보존, 미등록 partial pair 복구, wrong owner 거부, 다른 TLS identity를 사용하는 실제 relay server의 proof 재사용 거부, 검증된 TLS로 admin 등록, 등록 후 proof404 및 token 삭제, 등록된 identity 묵시적 회전 거부, log secret 부재 PASS (`headless-pairing-durable.log`).
- 기존 실제 HTTPS/WS 인증/Origin/CSRF/session/고정 TUI regression PASS (`web-pairing-durable.log`).
- VM `tests/linux_owner_firstboot.py`: 기존 private web state를 보존한 별도 초기 상태에서 실제 firstboot.sh 실행, boot owner 파일 소비/삭제, 출력 secret 부재, 재실행 certificate 유지, 실제120×40 PTY에서 Enter 전 secret 비표시/Enter 후 owner 확인, 실제 verified HTTPS 등록, token 삭제, fixed TUI 전환 및 shell 없는 종료 PASS (`linux-owner-firstboot-durable.log`). 원래 identity/profile은 finally로 복원했다.
- 초기 PTY 시험에서 창 크기를 설정하지 않아 TUI가 표시되지 않았다. 실제 기준 크기120×40을 설정하여 재시험 PASS (`linux-owner-firstboot-pty.log`); 실패 로그 보존.
- 위 firstboot 시험은 Linux에서 스크립트를 실행한 것이며 실제 새 Pi 이미지 부팅이 아니다. Pi display, browser certificate import, headless 일반 GUI 준비 도구, data disk/node profile onboarding은 NOT RUN/BLOCKED 상태를 유지한다.

## 저장장치 inventory

- VM `tests/linux_disk_inventory.py`: 실제 lsblk로 root backing disk, boot partition, read-only seed device, 현재 loop data mount 분류 PASS. fstab 및 mountinfo 변경 없음 (`linux-disk-inventory-final.log`). 실제 장치 포맷/마운트 시험이 아니다.
- `tests/disk_inventory_unit.py`: OS와 별도 data partition이 같은 NVMe에 있는 topology, 중복 filesystem UUID, nested mount 사용, 제어문자 처리 경계 PASS (`disk-inventory-unit.log`). 이 synthetic topology 단위시험은 실제 NVMe 부팅을 대신하지 않는다.
- 실제 Linux120×40 PTY S 화면에서 SYSTEM_DEVICE/CURRENT_DATA_MOUNT/READ_ONLY 표시 및 Esc 복귀 PASS (`linux-storage-tui.log`). Rust compile PASS (`storage-screen-check.log`, `storage-screen-build.log`).
- filesystem signature probing, mounted content review, 사용자 선택/동의, format/mount 및 baseline 등록은 NOT RUN이다.

## 실제 저장장치 서명·내용 검토

- `tests/linux_storage_probe.py`: 프로젝트 전용32MiB loop image를 만들고 backing path를 확인한 뒤 fixture에만 ext4를 생성. blank/ext4 signature 구분, stale identity 거부, system device review 거부 PASS (`linux-storage-content-review.log`).
- ext4를 read-only/no-journal-replay mount하여 empty/lost+found 및 실제 파일 존재 상태를 구분하고, 각 review 전후 전체 image SHA256 동일 확인. 파일 이름·내용은 report에 포함하지 않았다. 실제 물리 디스크는 사용하지 않았다.
- 전용2GiB virtio test disk 추가 후 VM 재부팅, system/core/electrs/Tor/web 복구 및 actual inventory PASS (`vm-provision-device-boot.log`, `vm-provision-device-inventory.log`). 새 device의 serial/size/review eligibility 및 실제 no-signature probe PASS (`provision-target-scan.log`).
- 새 test disk에는 아직 파일시스템을 만들지 않았다. 제품 format/mount/fstab/onboarding 전환 시험은 다음 작업이다.

## Dedicated VM volume setup

- PASS: `sudo python3 scripts/linux_volume_setup.py` on Debian ARM64 VM, newly created project-owned 2 GiB virtio disk with serial `JUSTVERIFY_TEST_DATA`. Target is resolved by serial/size/eligibility, never a hardcoded kernel name.
- Actual mkfs.ext4 completed; child was SIGKILLed after the durable formatted checkpoint. Repeated apply refused; recovery verified UUID, performed read-only e2fsck, mounted the real block filesystem, created private justverify-owned instances, and committed an isolated fstab fixture. Wrong confirmation left initial signature scan unchanged.
- Mounted-journal replay and unmounted remount recovery passed without duplicate fstab records. The mounted replay is a journal-state injection, not a second actual SIGKILL. Original `/etc/fstab` and existing `/srv/justverify/data` mount were checked unchanged by this test.
- Evidence: `.state/linux-volume-setup.log`; persistent VM fixture `/var/tmp/jv-volume-dcq9ed7o`. Dedicated disk now contains ext4 and must not be automatically reformatted when rerunning tests. The test deliberately rejects a nonblank disk.
- Owner-facing/API integration, real hardware formatting and first-profile startup remain NOT RUN/BLOCKED as applicable.
- PASS actual VM reboot: temporarily added only the dedicated test UUID/custom mount to real fstab, wrote a proof file, rebooted, confirmed automatic mounting and proof/volume UUID preservation, then unmounted and restored original fstab exactly. Core/electrs/web/JustVerify Tor services active after reboot. Evidence `.state/linux-volume-reboot.log`. This is a generic ARM VM storage reboot test, not Pi 5 installation/boot acceptance.

## Storage owner API integration

- `sudo python3 tests/linux_storage_api.py`: PASS real verified TLS and real root Unix storage server. Missing login, missing CSRF, foreign Origin and extra command field refused; authenticated inventory returned real VM devices; system-device preview refused; unrelated Unix user could not connect; unclaimed owner refused; setup token absent from log. Evidence `.state/linux-storage-api.log`.
- Initial integration correctly refused the original VM owner state because it is unclaimed. Test now uses a separate enrolled owner fixture with the production API implementation, temporarily stops/restores the original storage service, and never submits apply or format. Existing original owner state is preserved.
- Production unit installed and started (not enabled) in the VM; root state ownership 0700 and shared host mount namespace verified. Image builder includes helper files and enables the unit for the next build; new image NOT RUN.
- Successful format/recovery remains covered by the separate real block-device engine test; a successful owner-facing format through this API and the TUI confirmation UI are NOT RUN.
- Existing `tests/web_security.py` regression PASS with actual verified TLS/fixed TUI PTY over WebSocket, exit closure, owner setup, secure cookies, logout CSRF/session revocation and rate limit after adding `/storage`: `.state/web-storage-regression.log`.

## TUI storage selection/recovery

- Host `cargo build --locked` and ARM VM release build PASS. `cargo test --locked storage_ui` PASS: incorrect confirmation/Esc and protected-device Enter cannot start a mutation request. These are guard unit tests, not successful format integration.
- Actual Linux PTY + root storage API PASS: inventory/system/current-data/read-only statuses, protected-device selection refusal, recovery plan ID/review/cancel, then actual UUID-bound e2fsck/mount/fstab recovery and existing reboot-proof preservation. `.state/linux-storage-tui-owner.log`, `tests/linux_storage_tui.py`.
- This test uses a separate owner fixture and replays the previously formatted dedicated VM disk journal as `formatted`. It performs real recovery but does not perform another format or another SIGKILL. Original service is restored and test mount unmounted afterward. Initial failed PTY runs had connected before the fixture service was ready; an actual API readiness request resolved the failure.
- Interrupted journal rejects new preview before device access: direct engine guard PASS. Successful new-device formatting through TUI remains NOT RUN. Physical hardware and first node-profile startup remain separate gates.

## Actual TUI initial format end-to-end

- Added a second new project-owned 2GiB QCOW2 to the ARM VM, serial `JUSTVERIFY_UI_TEST`, preserving the first recovery fixture disk. VM was cleanly powered off, its old QEMU process exit checked, then restarted with the extra device. Tests resolve serial/size/eligibility and fresh signatures rather than kernel names.
- `sudo /opt/justverify-tests/bin/python tests/linux_storage_tui_format.py`: PASS actual nonprivileged Rust TUI PTY → production root storage API implementation → actual mkfs.ext4 → UUID-checked mount → private instances/volume marker/fstab commit. At 80×24, exact confirmation prompt and wrong-confirmation refusal were visible; wrong input and Esc preserved original signature scan. `.state/linux-storage-tui-format.log`.
- This test uses an isolated owner-enrollment fixture and isolated mount/fstab/state, temporarily replacing only the storage API process; TLS login was separately validated by `linux_storage_api.py`. No real user disk or original node volume was formatted. It does not prove first node-profile registration or installed Pi boot.
- New disk remains ext4, unmounted and classified for preservation. Existing node mount and Core/electrs/Tor/web/storage services active: `.state/ui-format-final-state.log`. Persistent VM fixture `/var/tmp/jv-ui-format-2afymm60`. The test refuses reuse of a nonblank disk; do not erase this fixture to manufacture repeated passes.

## Initial-profile volume eligibility

- Host debug and ARM VM release build: PASS (logs `.state/initial-volume-build.log`, `.state/initial-volume-linux-build.log`).
- `sudo python3 tests/linux_initial_volume.py` on the already formatted JUSTVERIFY_UI_TEST ext4 disk: PASS actual mount/UUID/root-journal eligibility; extra existing file, populated instances, incorrect UUID, writable marker, invalid owner, interrupted journal and unmounted target all refused. Existing proof file SHA256 and original marker restored; no node services changed. `.state/linux-initial-volume.log`.
- Owner metadata is an isolated enrollment fixture; complete actual TLS owner enrollment is covered separately. This test directly calls the production guard implementation with fixture paths, not the full version API/Core startup path.
- The first fixture attempt hit EXDEV moving its proof file across filesystems; test preservation was corrected to a cross-filesystem move and content hash restoration was verified. No production device/data was migrated.
- Complete first-version preview/apply with the new guard and startup gate: NOT RUN. Updated helper and binary are not installed into the live VM services yet.

## Production first selection → real Core/electrs integration

- `sudo python3 tests/linux_initial_profile.py`, ARM VM on dedicated JUSTVERIFY_UI_TEST ext4 volume mounted temporarily at the production data path. Production `allow_initial_selection` remains false. Isolated owner metadata and root provisioning record bind the genuine test UUID; existing VM profile/binaries/owner/mount are persistently backed up and restored.
- PASS first preview through actual unprivileged version service and sudo check_initial; adding an instance after preview caused apply refusal and preserved that directory. A fresh preview/apply committed Core31.1 regtest without the development bootstrap override.
- Initial run exposed real electrs cookie startup race. Added authenticated RPC ExecStartPre readiness; rerun PASS actual Core chain RPC, one real generated regtest block, electrs indexed height 1. Evidence `.state/linux-initial-profile-final.log`. Original failure evidence remains `.state/linux-initial-profile.log`.
- Earlier generated fixture instances were preserved in `/var/tmp/jv-initial-profile-rzh8imgo/previous-test-instances` before exercising fresh initial registration again; no reformat, test deletion, data discard or acceptance relaxation. Persistent recovery manifests/backups exist at `/var/tmp/jv-initial-profile-uxlqiolq` and `/var/tmp/jv-initial-profile-rzh8imgo`.
- Original node UUID/config/helper/binary/owner restored; version API stopped. RPC-readiness fix then installed for live VM electrs; original Core/electrs/web/Tor active and existing indexed height 2 confirmed: `.state/electrs-rpc-startup-restored.log`.
- This is first-profile service integration, not full boot/onboarding acceptance. Storage completion → automatic version-service availability, pre-registration Core startup gating, first-run TUI guidance and new image boot remain NOT RUN/incomplete.

## Registered-profile startup systemd integration

- `.state/linux-registration-startup.log`, `sudo python3 tests/linux_initial_profile.py`: actual Core/electrs/policy systemd start before registration stays inactive; production first preview/apply creates registration and starts real Core31.1 regtest/electrs; mined height1 indexed. Altering the registration UUID makes actual Core start fail with MainPID=0; restoring the marker allows startup.
- No relaxed startup/format criteria: prior dedicated fixture instances retained under `/var/tmp/jv-initial-profile-vmkkcfuu/previous-test-instances`. Existing node units/config/binaries/owner/UUID restored afterward. New gate units were used only during the test, not left installed over the unregistered legacy development profile.
- Firstboot change regression PASS using actual Linux firstboot, boot owner-file consumption, certificate-verified owner claim, physical PTY Enter gate/fixed TUI/no shell: `.state/firstboot-registration-regression.log`. Updated firstboot script installed in VM; original web identity restored by test.
- Registered-profile reboot, changed-config/selection startup fault variants, automatic storage→version-service availability and final image boot remain NOT RUN. The test above is actual systemd start/restart, not a reboot.

## Volume-to-profile preparation

- `.state/linux-profile-preparation.log`: actual committed-volume recovery completion calls the production profile-preparation callback, starts the real version service and leaves Core inactive; explicit preparation retry succeeds without formatting. Then production first preview/apply, Core31.1 regtest mined block/electrs height1, registration UUID fault/startup recovery all PASS.
- Owner/TLS/Unix API boundary regression PASS (`.state/profile-preparation-auth.log`); storage UI mutation guard tests PASS (`.state/profile-preparation-ui-tests.log`). Host build PASS (`.state/profile-preparation-build.log`).
- Existing profile restored after integration. Backup and prior generated fixture data preserved under `/var/tmp/jv-initial-profile-mo875z48`. New production storage server installed/restarted; original Core/electrs/web/Tor active. Live Rust/web processes remain previous versions.
- Actual B-key PTY exercise and new-image boot remain NOT RUN. Automatic callback was tested on already committed recovery completion, not another new format. New-format engine/TUI evidence remains the earlier dedicated disk test.

## Development image dev3

- Actual isolated ARM Linux build PASS: `.state/image-dev3-build.log`. New image contains verified version-tree Core31.1, electrs0.11.1, Tor0.4.9.11, GPG2.4.7, owner/storage/version services, fixed sudo helpers and startup registration gate.
- `sudo bash image/verify-pi.sh dist/justverify-0.1.0-dev3-rpi5-arm64.img.xz` PASS: read-only e2fsck, device identity absence, ARM executions, exact component hashes, helper permissions, all three sudo rules, production first-selection guard config, startup gates, enabled services and systemd analysis. `.state/image-dev3-verify.log`.
- Host copy SHA256 matches VM: `3571842365fdc706f5d2feaabb6ce94133baa8a1bb6deff7925efb86240b203c`. Artifact and checksum in dist; installed package inventory `dist/os-packages-dev3.tsv`.
- NOT RUN: actual Pi boot, complete onboarded image system, hardware/mobile/soak acceptance. NOT COMPLETE: fully pinned apt snapshots/wheel hashes/reproducible build and signed release. This is a development image, not the final release candidate.

## Actual TUI B → first profile review

- `sudo /opt/justverify-tests/bin/python tests/linux_initial_profile.py` with `tests/pty_initial_profile.py`: PASS actual non-root PTY S inventory/B starts the stopped production version service, V displays FIRST PROFILE, N selects regtest, Enter reviews, Esc cancels without an active selection or starting Core. `.state/linux-initial-profile-pty-final.log`.
- Following the PTY flow, actual preview-change rejection, first Core31.1/regtest apply, mined block/electrs height1, wrong-volume startup refusal and restored valid startup all PASS. Original node volume/config/binaries/owner restored; generated test data preserved at `/var/tmp/jv-initial-profile-zyho_rpz`.
- Initial PTY attempt sent Esc+V as one byte sequence interpreted as Alt+V. Test now waits for main screen after Esc before pressing V; input parsing was not weakened. Original failure log `.state/linux-initial-profile-pty.log` retained.
- Management-unavailable fallback now lists S and V so setup remains discoverable when collector is absent. ARM release build PASS. The existing dev3 image predates this fallback-label-only change; it already includes the B and first-profile implementation tested here.

## Actual registered-profile VM reboot

- Prepared a production-guarded Core31.1 regtest profile on the dedicated JUSTVERIFY_UI_TEST volume, stored the original files/ownership/modes/fstab/unit enablement plus a durable reboot checkpoint, and changed only the VM data fstab entry to the dedicated UUID. `.state/registered-reboot-prepare.log`.
- Actual `systemctl reboot`, new kernel boot ID verified. `.state/registered-reboot-verify.log`: mounted registered UUID unchanged; certificate, machine identity and both Tor hostnames retain their hashes; non-root startup gate passes; Core/electrs/version/storage/manager/policy/web/Tor services active; real Core regtest block height1 and Electrum subscribed height1 agree.
- `tests/linux_registered_reboot.py` restored original data UUID/fstab/profile/binary/helper/owner/units/enablement in finally. Persistent checkpoint `/var/tmp/jv-initial-profile-ksye2gzh/reboot.json` records verified and restored. Original indexed height2 confirmed afterward: `.state/registered-reboot-baseline.log`.
- This is a real generic ARM VM reboot with registered profile, not Pi hardware or dev3-image boot. Interrupted-transition reboot recovery still needs its own test. No physical medium was written.

## TUI interrupted-version recovery

- Host and ARM release builds PASS. Actual version API/TUI test on the dedicated initial-profile fixture injected phase=starting with target22.0 and prior31.1, stopped services, and temporarily renamed the target executable. `tests/pty_version_recovery.py` verifies state still returns active_error + needs_recovery.
- Actual PTY V/R displays interrupted status, reviews previous/target, Esc leaves journal unchanged, Enter recovers to the previous Core31.1 profile and starts its real services. Target executable remained unavailable throughout recovery and was restored afterward. `.state/version-recovery-tui.log` PASS.
- This is an injected durable-state fault plus real API/systemd recovery, not an actual SIGKILL or interrupted reboot. Earlier real engine SIGKILL evidence is separate; reboot during interrupted transition remains NOT RUN.
- Original VM volume/profile/binary/helper/owner/units restored; original Core/electrs/web/Tor active; target22.0 executable restored. Persistent baseline backup `/var/tmp/jv-initial-profile-hitpee2p`.

## Actual version apply SIGKILL → reboot → TUI recovery

- Test-only wrapper pauses the fixed root bridge immediately before target22 activation; all other requests delegate to the real helper. The actual version API apply performs preflight, data preparation and durable transition/active writes. After verifying phase=starting/active22, the entire version-service cgroup is killed with SIGKILL. Journal stays starting. This is not a journal injection. `.state/interrupted-boot-prepare.log`.
- Wrapper and pause marker removed and real helper restored before reboot. Actual VM reboot/new boot ID; mismatched registration prevents Core startup (MainPID=0 and non-root gate failure). Actual PTY V/R recovers prior31 profile using its separate data. Core/electrs preserved height1; UUID/certificate/machine identity/Tor hostnames preserved; services ready. `.state/interrupted-boot-recovery.log` PASS.
- Persistent checkpoint `/var/tmp/jv-initial-profile-8osrazyh/reboot.json`: interrupted=true, phase=verified, restored=true. Original fstab/data/profile/binaries/helper/owner/unit enablement restored. Original Core/electrs/web/Tor active; temporary test helper and pause file absent.
- The pause wrapper exists only in the test module and temporary VM files; product code has no test bypass. Hardware power-cut/Pi boot/full image acceptance are not proven by this generic VM process-kill/reboot test.

## Per-client node-read RPC over real TLS

- Extended `sudo python3 tests/linux_storage_api.py`: actual certificate-verified TLS owner login/CSRF, client issuance, real Core getblockchaininfo, unauthenticated refusal, forbidden stop/createwallet and batch refusal, enforced per-client request budget, client listing without secret/hash, plaintext secret absent from state/logs, and immediate revoked-client refusal PASS. `.state/rpc-client-tls.log`.
- Existing actual TLS/WebSocket/fixed TUI/security regression PASS after introducing the gateway module: `.state/rpc-gateway-web-regression.log`.
- Tested Core31.1 regtest through the VM's real cookie RPC. No Core settings or wallet mutations are forwarded; existing services/profile preserved. Test web process and credentials isolated; live web server not replaced.
- NOT RUN/incomplete: user-facing client issuance/QR, mobile application compatibility, per-client watch-only wallets, Tor RPC route, other Core-version gateway combinations, physical phone connection. Node-read gateway evidence is not mobile-wallet acceptance.

## TUI client issuance/revocation

- Actual Linux non-root PTY C/A/name issuance, credential popup, Esc hide, revoke cancellation, revoke confirmation PASS. Credentials captured only in test memory authenticated real certificate-verified TLS Core RPC; revoked credentials returned401. Secret absent from persisted client file and logs; hidden popup no longer contained it. `.state/client-tui-tls-final.log`, `tests/linux_client_tui.py`.
- Eight concurrent independent creator processes retained all eight records with mode0600: `.state/rpc-client-concurrent.log` PASS. Host build and ARM release build PASS.
- Initial UI test could not execute the binary inside builder's private home; fixed by copying it to the dedicated test directory. E navigation is now menu-only to avoid stealing the letter while entering client names. No filesystem permission was relaxed on the builder home.
- Original web identity/state/service restored; test state is private. The local helper and shared gateway module were installed in VM for the test, while the live server and TUI binaries remain their previous versions.
- QR/mobile payload, watch-only wallets, Tor RPC route and actual mobile app pairing remain NOT RUN/incomplete. Tested profile is node-read only.

## Actual terminal Electrum QR

- Actual non-root PTY Q at120×40: black/white half-block modules match the generator matrix; resize80×24 refuses clipping and shows enlarge guidance; Esc returns. `.state/electrum-qr-pty.log` PASS. Pyte renders ANSI colors as either names or exact RGB; assertion accepts their equivalent black/white representations.
- Reconstructed an image from the captured terminal module cells and decoded with zxingcpp; exact published onion:50001 payload PASS. `.state/electrum-qr-decode.log`. No public hostname or QR image is printed in evidence; private capture JSON kept in .state.
- Host/ARM builds PASS, qrcode8.2 installed in VM web venv and pinned in requirements. Physical camera/app import NOT RUN; this digital decode is not phone pairing.
- Source audit records official repository commit/file hashes and latest release metadata in catalog/mobile-source-audit.json. No third-party app code reused. FullyNoded transport/method compatibility and Nunchuk actual app entry remain unverified.

## RPC root route / real server restart

- ARM Debian VM, Core 31.1 regtest, verified TLS, non-root actual PTY: `sudo /opt/justverify-tests/bin/python tests/linux_client_tui.py` PASS (`.state/rpc-root-restart.log`).
- JSON-RPC 1.0 POST `/` query succeeds; anonymous 401, wallet/admin 403; GET `/` serves browser content. Client authentication persists after actual server process terminate/start, TUI cancel keeps it valid, revoke denies access, plaintext secret absent from stored records/logs.
- Additional GET check initially failed because isolated server fixture omitted static files. Fixture now copies the actual web directory structure and assets; assertion retained and passed. Product routing did not require weakening.
- This is isolated TLS server restart, not a new whole-VM reboot or installed mobile app test.

## dev4 image / generic ARM first boot

- Immutable dev4 compressed artifact SHA256 `eb44ed28fc3749ebc2df782c95d9129fc7f8a6a2cfb9508a11db3e6fa1804e03`; offline checks PASS (`docs/evidence/pi-image-dev4-verify.log`).
- Disposable copy, QEMU11.1.1 virt/HVF ARM64/3GiB/2CPU, external Debian6.12.107 kernel+initramfs+matching modules: firstboot identity, node registration gate, installed services, TLS pairing proof/owner claim and actual packaged TUI over authenticated WS PASS (`docs/evidence/image-dev4-virt-probe.json`).
- First attempt lacked external kernel modules and failed FAT mount; repeated with matching modules, no image acceptance check weakened. External kernel and module injection is a test accommodation, not Raspberry Pi firmware/kernel validation.
- Boot also exposed OS userconfig dialog stealing tty8; fixed in source for dev5, not silently ignored. Physical console, Pi EEPROM/firmware and actual Pi boot remain NOT RUN/BLOCKED.

## dev5 image first boot and reboot

- `image/build-pi.sh ... 0.1.0-dev5`, `image/verify-pi.sh dist/justverify-0.1.0-dev5-rpi5-arm64.img.xz`: PASS (`docs/evidence/pi-image-dev5-verify.log`). Host checksum matches builder `c97f8bf41e9cf589aa42c67a8f4118bbe8938e7d76461ae0afb7a4e129aa68b2`.
- `tests/prepare_image_boot_probe.sh` creates disposable copy; QEMU virt uses external Debian6.12.107 kernel/initramfs/modules. Two actual boots: first enrollment/TLS/TUI then reboot with unchanged identity and existing owner login/TUI PASS (`docs/evidence/image-dev5-virt-probe.json`). userconfig masked/PID0 on both boots. Original compressed image unchanged.
- Physical Pi, packaged Pi kernel/firmware, camera, mobile app and registered node profile in this specific image probe NOT RUN. Generic VM EEPROM failure is not counted as a Pi pass. Development-VM Core/electrs integration evidence remains separately scoped.

## Internal watch-only boundary / 32 actual Core versions

- `tests/watch_only_matrix.py <versions>` in ARM Debian VM with official verified Core22.0–31.1, all32 deployable versions PASS (`docs/evidence/watch-only-matrix.json`). Core30.0/30.1 remain upstream-withdrawn, not silently counted.
- Real blank private-key-disabled descriptor wallets; idempotent creation; mixed public/private batch rejected before import; public import and mined regtest balance; other client's empty descriptor/balance; direct key/backup/private export refusal; actual Core restart with persistent wallet state; unsafe preexisting wallet rejection; clean shutdown. Binary and implementation/test hashes attached.
- Initial Core22 private-export argument assumption failed; use Core-compatible public list normalization and independent ephemeral WIF rejection fixture. Initial HTTP keepalive/teardown interaction delayed exit; close test connections and stop gracefully, report PASS only after termination. No test assertion removed.
- Internal boundary only. Production disablewallet default unchanged; owner activation, client authorization/revocation coupling, public wallet gateway, PSBT and mobile app still incomplete.

## Watch-only profile transition and actual TUI

- Host cargo check and ARM release build PASS. Actual Core/electrs version-transition test with additional node→watch-only→node→watch-only→node sequence PASS (`.state/watch-profile-transition.log`): distinct chain/index paths, private-key-disabled test wallet persistence, original node height/index and disabled wallet restored. Existing failed-start rollback, data preservation and interrupted recovery assertions retained.
- Production systemd/root bridge/registration gate test PASS (`.state/watch-profile-production.log`); added actual TUI W mode/review/cancel and repeated affected integration PASS (`.state/watch-profile-tui.log`). Original development mount/configuration/binaries restored, fixture data preserved.
- Versions31.1 watch-only activation was exercised through production service wiring; all32 wallet engine checks remain independently documented. New physical Pi/image boot for this change NOT RUN. Full client wallet gateway/mobile still incomplete.

## Actual TLS wallet authorization and production TUI grant

- `tests/wallet_gateway_tls.py`, real Core31.1 regtest and aiohttp TLS server: owner CSRF and watch-only profile gating, idempotent grant, assigned wallet route/filtered lists, public descriptor import, mixed private batch denial without import, separate balances/descriptors, forbidden exports/admin, changed profile/volume denial, revocation, plaintext credential absence PASS (`docs/evidence/wallet-gateway-tls.log`). Previously assigned wallet unloaded and moved aside: regrant409/no empty replacement; restored file regrant succeeds. Registration changes in this isolated protocol test are explicit fixture changes, not a claimed mounted-volume swap.
- `tests/linux_initial_profile.py` invokes actual non-root PTY C/W grant review/cancel/confirm against a production-selected watch-only profile, then TLS getwalletinfo confirms private keys disabled. Two wallets survive mode transitions and revoke does not delete data; original node/services restored PASS (`docs/evidence/wallet-grant-production.log`). Initial fixture expected one wallet; updated to assert the exact two-wallet set before/after switching, retaining data-preservation checks.
- Actual TUI/service run includes profile+volume binding. Subsequent missing-wallet-history guard is covered by the isolated real TLS/Core test. Host check/ARM release build PASS. Latest dev5 image predates these changes; physical mobile and PSBT remain NOT RUN/incomplete.

## PSBT transaction permission and real TLS/Core matrix

- All32 verified ARM Core22–31.1 releases: `tests/wallet_gateway_tls.py <version>` real TLS funding, forced no-sign PSBT update, separate test signing wallet through internal RPC, finalization, mempool acceptance, broadcast, block confirmation and revoked-client denial PASS (`docs/evidence/psbt-tls-matrix.json`). Actual external hardware/mobile signer NOT RUN.
- Additional funding-option allowlist, solving_data rejection, conflicting fee units and explicit browser-Origin denial verified on Core22.0/31.1 in final regression. Amounts/fee rates are explicit decimal strings (BTC outputs, sat/vB fee_rate); no conversion inferred. Existing wallet/profile/volume/missing-data/secret checks retained.
- Production selected watch-only profile + actual PTY C/T review/cancel/grant, visible transaction-permission label and real TLS PSBT creation PASS. Original node/profile/data/services restored (`docs/evidence/psbt-final-regression.log`). Host check/ARM release build PASS.
- This proves the exercised PSBT workflow, not every wallet application's complete RPC sequence, coin-control feature or real phone/hardware pairing. dev5 image does not yet contain these changes.

## dev6 artifact and two-boot client/menu validation

- Build and readonly image verification PASS; artifact SHA256 `49f78e4faedf42db56acf7ef3dcb155d22d96173ff55a1965e18e12cddee5d6f` (`docs/evidence/pi-image-dev6-verify.log`). First extraction failed because /tmp tmpfs was too small; /var/tmp scratch fixed the environment dependency without deleting unrelated data.
- Actual QEMU virt firstboot/enrollment/client issuance/TUI C/T menu → reboot → preserved identity/client authentication/owner login/menu PASS (`docs/evidence/image-dev6-virt-probe.json`). Initial raw-stream menu observer failed; proper VT screen decoding passed the retained assertion. Test decoder/modules are outside the pristine artifact.
- This is generic image userspace, external Debian kernel. Pi hardware/firmware, actual phone and registered Core/electrs data profile in this particular image probe NOT RUN. Separate production-VM wallet/PSBT evidence is not relabeled as image-level integration.

## dev9 packaged remote RPC and two-boot recovery

- `sudo bash image/verify-pi.sh dist/justverify-0.1.0-dev9-rpi5-arm64.img.xz` PASS on the isolated ARM builder. Filesystem, exact packaged source/component hashes, identity absence, permissions, service enablement and ARM/Python runtimes are recorded in `docs/evidence/pi-image-dev9-verify.log`.
- Disposable dev9 copy with a newly created serial-gated data11 disk PASS on two actual QEMU ARM boots. The first boot used the production owner/storage/version/Core/electrs/web/Tor paths, reached Core31.1 regtest through the real RPC onion, enforced401/404 boundaries, created and matched the black/white Fully Noded Quick Connect matrix, and displayed remote and LAN TLS state through the actual browser WebSocket TUI. The second boot verified preserved identity, registration, client credentials, wallet/chain, services and real onion RPC before poweroff (`docs/evidence/image-dev9-data-probe.json`).
- Earlier fresh attempts failed on observer timing and remain documented: Tor circuit startup timeout, partial differential terminal frame and unsynchronized Escape transitions. Each was corrected in the observer without deleting assertions, replacing services with mocks or changing the packaged release artifact.
- Physical Raspberry Pi boot, actual mobile applications/camera/separate LAN, hardware signer and 24-hour operation are not covered by this result.

## 2026-09-12 일반 설정 UI

HTTP/TLS auth, Linux 실제 device API/암호 회전/세션폐기/설정 유지, 실제 Tor onion 관리 화면, 기존 Remote RPC 격리·재시작·장애복구, VM 실제 reboot/poweroff/cold start, GPG4개Toridentity backup/restore 및 legacy 호환 PASS. 실제 Pi responsive 화면·refresh/logout·정보 조회·backup snapshot·32개파일 SHA 일치 PASS. 실패 원인/재시험/정확한 범위는 DEVICE_SETTINGS.md. 새 이미지와 최종 릴리스 완료 아님.
