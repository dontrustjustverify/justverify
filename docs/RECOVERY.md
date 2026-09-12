# 복구 및 재개

현재 beta1 설치·재기록은 [설치 안내](INSTALL.md)와 [한국어 README](ko/README.md)를 따른다. 이전 dev16 기록은 [dev16 안내](INSTALL_DEV16.md)에 보존한다. 동일 등록 볼륨에서 설정·Tor/TLS 신원·중단 저널 복구는 검증했으며, 새 UUID로 재설치한 볼륨에 이전 설정을 자동 이전하는 복구는 미완료다. 제품 전체 복구 완료를 의미하지 않는다.

- 개발 상태는 Git, `docs/STATUS.md`, `docs/ACCEPTANCE.md`, `docs/evidence/`에 저장한다.
- 호스트 개발 프로세스는 `.state/`에 격리한다. socket이 남았으면 PID와 해당 데몬 종료 여부를 먼저 확인한다. 살아 있는 데몬의 socket을 임의 삭제하지 않는다.
- VM 콘솔은 `.state/vm/console.log`, 디스크는 `.state/vm/disk.qcow2`다. QEMU가 종료됐을 때만 `scripts/vm_start.sh`로 다시 시작한다. 동일 디스크를 두 VM이 동시에 열지 않는다.
- Core/electrs 데이터 마이그레이션 뒤 바이너리만 이전 버전으로 바꾸지 않는다. 검증되지 않은 전환은 별도 데이터 경로가 기본이다.
- 실제 데이터 디스크가 누락되면 원래 mount를 복구한다. 시스템 디스크에 임시로 체인 데이터를 쓰는 우회는 하지 않는다.
- 최초 설정 코드/인증서/Tor 개인키는 `.state` 또는 기기 `/var/lib`의 비밀정보다. 진단자료/스크린샷/Git에 넣지 않는다.

암호화 백업·동일 등록 볼륨의 Tor/TLS identity 복원·중단 저널 복구는 실제 Linux 서비스에서 검증했다. OS 재설치 후 새 볼륨으로의 복원, 백업 반출입 UI, 단일 OS 업데이트 실패 복구는 아직 미완료다. 기존 디스크 부족 시험은 ACCEPTANCE.md의 범위를 따르며 전체 장애 복구 완료로 확대하지 않는다.

실행 세션이 끊긴 뒤 코드 작성이 자동 재개되는 실행기는 현재 구성하지 않았다. VM/서비스의 systemd 자동 시작과 에이전트 작업 재개는 별개다.

## 설정 변경 중단 복구

현재 개발 TUI에서 `M`은 mempool 정책 화면이다. 편집 후 `A`로 실제 Core 사전 기동 검증과 변경 내용을 보고 Enter로 적용한다. 시작 실패 시 동일 Core의 이전 설정을 복원한다.

관리 프로세스가 변경 중 강제 종료되면 다음 시작 시 `INTERRUPTED CHANGE`를 표시한다. `R`에서 복구 내용을 확인하고 Enter를 누르면 이전 설정을 복원하고 Core를 재시작하여 상태를 확인한다. Esc는 변경하지 않는다. binary/network가 바뀌었거나 설정 파일을 외부에서 수정한 경우 자동 복구를 거부한다. 이 절차는 Core/electrs 데이터 마이그레이션 복구가 아니다.

## Development image boot evidence and recovery limits

- dev9 retains V/R recovery to the prior version's separate data profile, C client revocation, explicit C/O remote-RPC recovery state, and S storage-plan recovery. Never erase or reformat a disk merely to clear an interrupted plan. Preserve the plan and data UUID, review recovery, and verify Core, electrs, Tor and the remote listener after completion.
- `tests/prepare_image_boot_probe.sh` creates only a disposable image copy for generic ARM boot. Use an external matching Debian kernel/initramfs/module tree; the packaged Pi firmware path is not exercised. The two-boot probe stores a private test password checkpoint inside that copy and must never be distributed as an installation image. Host copies should be mode0600.
- Keep the pristine compressed artifact and checksum separate from booted test disks. Recreating a disposable fixture is not a user-data recovery procedure. Physical power loss, SSD failures, Pi boot and encrypted backup restoration still require their own acceptance evidence.

## 유한 업로드 한도와 electrs 재인덱싱

업로드 한도를 설정했을 때 electrs가 과거 블록을 받지 못하는 결함을 dev11 소스에서 수정했다. 전용 loopback download backend를 통해 제한을 유지하며 인덱싱한다. 과거 버전 프로필에서 backend 메타데이터가 없으면 유한 한도 적용을 거부한다. 데이터/인덱스를 삭제하거나 업로드 제한을 무작정 해제하지 않는다. V에서 기존 동일 버전·동일 네트워크·동일 watch-only 프로필 재개를 검토해 일치한 Core/electrs 설정을 재생성하고, Core의 IBD와 electrs 높이·tip 일치까지 확인한다. 기존 데이터 형식을 바꾸는 다운그레이드의 복구 절차로 사용하지 않는다.

Tor 서비스 실행이나 bootstrap100%만으로 onion 연결 성공을 판정하지 않는다. 실제 인증된 RPC 요청과 익명/관리 요청 거부까지 확인해야 한다. dev10 이미지 시험의 회선 시간 초과는 실패 증거로 보존했으며, 회선 오류 해결을 위해 Tor 개인키나 인증서를 삭제하지 않는다. 기기 시간과 네트워크 상태, Tor 진단을 확인하고 주소가 유지된 상태에서 재검증한다. 진단 로그에는 식별 정보가 있을 수 있으므로 비공개로 보존한다.

## 단일 NVMe 첫 부팅과 저장장치 오류

dev15는 OS 한 벌과 같은 NVMe의 데이터 영역을 사용한다. 첫 준비가 중단되면 저장된 UUID 계획을 이용해 재부팅 시 재개한다. 파일시스템 확장 전 전체 e2fsck 검사가 실패하면 진행하지 않는다. 이미 등록된 데이터 UUID가 달라지면 서비스 시작을 차단하며 OS 영역에 체인을 대신 만들지 않는다. 오류를 없애려고 새 UUID를 등록하거나 재포맷하지 말고, 원래 볼륨·저널과 디스크 상태를 보존한다.

실제 이미지의 잘못된 UUID 주입 → 서비스 차단 → 시험에서 원래 UUID 복원 → 실제 재부팅·Core/electrs/Tor/TLS/지갑 연결 복구를 검증했다(`docs/evidence/image-dev15-volume-fault.json`). 이는 UUID 장애에 대한 명시적 시험 복구이며 물리 SSD 고장, 전원 차단, 다른 장치 데이터의 자동 채택을 검증한 것이 아니다.

B 메뉴의 암호화 백업은 블록체인을 포함하지 않으며 현재는 동일 등록 볼륨·버전 복원이 검증 범위다. 백업이 같은 NVMe의 boot 영역에 있으면 이미지 재기록 때 함께 지워진다. NVMe 재기록 전 외부에 백업을 보관하는 경로와 새 설치 복원은 아직 구현·검증 중이므로 재설치 복구 완료로 안내하지 않는다.
