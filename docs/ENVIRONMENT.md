# 실행 환경 (2026-09-12)

- 호스트: macOS Darwin 25.6.0, arm64, 프로젝트 쓰기 가능, 초기 여유 공간 390 GiB.
- Rust/Cargo 1.98.0. Python 3.13.15, Homebrew 사용 가능.
- 작업에서 설치: QEMU 11.1.1 (HVF 지원), GnuPG 2.5.22, Tor 0.4.9.12. 기존 사용자 서비스 자동 시작은 구성하지 않았다.
- Linux: 프로젝트 내 QEMU ARM VM, Debian 13 20260831-2587, kernel 6.12.107+deb13-cloud-arm64. 4 vCPU, RAM 6 GiB, 가상 디스크 32 GiB. 첫 부팅 및 systemd running 확인. SSH는 호스트 127.0.0.1:22222로만 전달.
- VM key/seed/disk/console은 `.state/vm/`에 보관, Git 및 제품 이미지 제외. 제품 키와 별개.
- 공식 HTTPS Core/Guix/GitHub/Crates/PyPI/OS 다운로드 가능. 31.1 공식 서명 및 SHA256 검증 완료(macOS/ARM Linux).
- 사용자 Pi4/Pi5 보유, NVMe Pi5 시험 제공 가능 확인. 이미지 준비 후 Mac에 SSD 연결→balenaEtcher 기록→사용자가 Pi5 장착/IP 제공→root 원격 검증을 허용했다. 현재 매체 식별/연결과 IP는 아직 미제공. 기존 SSH 설정에는 지정한 시험 호스트 설정이 없고 임의 장치 접속은 하지 않았다.
- 실제 휴대폰 앱/카메라: 접근 정보 없음. Pi 부팅/카메라/24시간 Pi 시험 BLOCKED.
- 물리 디스크 포맷·기존 노드 데이터 변경·공개 배포 없음.

증거: evidence/vm-first-boot.log, vm-base.json, core-31.1-*-download.json.
