# 설치 및 실행

현재 설치용 후보는 **dev16**이다. [dev16 설치·재기록 안내](INSTALL_DEV16.md)와 같은 버전 manifest/검증 보고서를 따른다. OS 한 벌을 NVMe에 balenaEtcher로 기록한 뒤 Pi5에 연결한다. 기본 접속은 http://justverify.local 이며 새 관리자 암호·확인값으로 처음 등록한다. SSH 계정 justverify / justverify는 웹 암호와 별개다. 새 이미지의 실제 Pi5 부팅은 아직 NOT RUN이며 전체 S0–S4 완료를 뜻하지 않는다.

원본 `dist/justverify-0.1.0-dev16-rpi5-arm64.img.xz`는577,803,744bytes(약551MiB), SHA256 `889bf8ace5b0aa8d5731ae92867e100867c44c1d0a46c3db585fc6276e373bdc`다. 지정 Pi에는 같은 이미지에 사용자의 SSH 공개키만 추가한 개인 복사본을 사용한다. 부팅한 시험 clone에는 시험 계정이 있으므로 설치 파일로 사용하지 않는다. 이전 dev15 원본에는 Pi initramfs resize 충돌이 있으므로 다시 기록하지 않는다.

아래 dev15 및 더 이전 개발 이미지 설명은 당시 기록이다. 현재 설치 절차와 인증 방식은 위 dev16 안내가 우선한다.

OS는 한 벌이다. 이미지에 포함된 데이터 영역은 첫 부팅에서 같은 NVMe의 남은 용량으로 확장된다. 최초 소유자 등록 후 V에서 Core 버전과 네트워크를 선택하면 동기화를 시작한다. 별도 SSD 포맷 절차는 이 설치 경로에 필요하지 않다. 모니터 없는 소유권 전달과 시험용 root SSH 준비를 포함한 실기 절차는 아직 완성 전이다. 현재 배포 이미지의 SSH는 기본 비활성화되어 있다.

실제 QEMU 단일 디스크 첫 부팅·재부팅·UUID 장애 차단/복구와 읽기 전용 이미지 검증은 PASS다. Pi5 펌웨어·HAT·NVMe, 모바일 앱/카메라, 모든 업데이트·복구 요건을 통과한 최종 이미지라는 뜻은 아니다. 실기용 기록 준비와 검증을 계속한다.

현재 파일은 **개발 이미지**다. 일반 사용자용 배포 후보가 아니며 Pi 실기에서의 부팅·소유권 전달·데이터 디스크 초기 설정을 아직 검증하지 않았다. 지정되지 않은 물리 디스크에 기록하지 않는다.

이전 `dist/justverify-0.1.0-dev9-rpi5-arm64.img.xz`는 오프라인 검증과 외부 Debian 커널을 사용한 가상 머신 최초 설정·Core/electrs·LAN TLS·watch-only 지갑·PSBT·Tor RPC·민감 Quick Connect QR·실제 재부팅 시험을 통과했다. SHA256은 `604f4d8e813995503a7791c8cc8b1a589bbff0a81829298f0ded1e5054001c5c`다. C/O에서 검토 후 원격 RPC를 켜고, C에서 새 클라이언트를 만든 뒤 Q로 Fully Noded용 QR를 표시한다. 실제 휴대폰 앱·카메라와 Pi 하드웨어 검증은 남아 있다.

dev11은 Core 설정·네트워크·인덱스와 전용 electrs 과거 블록 backend 수정을 포함한다. 빌드 소스 `11c8419`, SHA256 `160b202f895b10f15aa9e9ca33bead39b950f813c1ed3cfdffff2fcc8f168f74`. 읽기 전용 검증과 실제 QEMU 최초 설치·두 번 부팅 PASS. 결과는 `docs/evidence/image-dev11-data-probe.json`에 기록했다. dev10의 Tor 회선 시간 초과는 실패로 보존했다.

dev6의 최초 디스크 설정 직후 UUID 조회 결함은 dev7부터 수정됐다. 이미 커밋된 볼륨을 다시 포맷하지 않는다. dev8에는 개별 지갑 UTXO 잠금·해제와 LAN TLS 서비스가 추가됐고, dev9에는 검토형 원격 RPC 설정, 별도 Tor RPC onion 및 Fully Noded Quick Connect QR가 추가됐다. Pi 자체 커널·실기 부팅, 전체 필수 기능 및 배포 서명은 아직 완료되지 않았다.

이전 dev12는 위 기능과 Core31 cluster 기본값 표시 수정을 포함한다. `dist/justverify-0.1.0-dev12-rpi5-arm64.img.xz`, SHA256 `902975da8186fb27f278eee46236e0ccb70e64c939a4a1c59dba7228551c2c46`. 실제 정책 API 기본값64 확인을 포함한 최초 설치·두 번 부팅 PASS. 소스/manifest/SHA256SUMS는 같은 dev12 이름이며 개발용·미서명 상태다.

## 개발 TUI 재현

프로젝트 경로에서 Rust 1.98.0과 Python 3.13을 준비한다.

```
cargo build --locked
python3.13 scripts/fetch_core.py 31.1 arm64-apple-darwin
python3.13 scripts/regtest_smoke.py
```

이 명령은 프로젝트 `.state/smoke`에 별도 regtest 데이터를 만들고 실제 TUI를 PTY로 실행·검증한 뒤 프로세스를 종료한다. 기존 Bitcoin 데이터는 사용하지 않는다.

## ARM Linux VM

호스트에서 `scripts/vm_start.sh`를 실행한 후 `scripts/vm_ssh.sh`로 프로젝트용 VM에 접속한다. QEMU/가상 디스크/전용 SSH 키가 필요하며 준비 스크립트는 `scripts/vm_prepare.py`다. VM은 Debian ARM 테스트 환경이며 Pi의 하드웨어 부팅을 대신하지 않는다.

## Pi 개발 이미지 빌드

고정 OS 정보는 `catalog/pi-base.json`, Core artifact 서명/체크섬은 `docs/evidence/core-31.1-aarch64-linux-gnu-download.json`이다.

ARM Linux 빌더에서 `cargo build --release --locked` 후:

```
sudo bash image/build-pi.sh /path/to/verified-base.img.xz /path/to/bitcoin-31.1 /path/to/target/release/justverify /path/to/electrs/target/release/electrs 0.1.0-dev16
sudo bash image/verify-pi.sh dist/justverify-0.1.0-dev16-rpi5-arm64.img.xz
```

이미지 빌더는 프로젝트 내 새 정규 파일에만 작업하고 기존 출력 파일을 덮어쓰지 않는다. 같은 태그가 이미 있으면 새 태그를 지정하고 검증 대상 이름도 바꾼다. host mount namespace에서 chroot를 사용하므로 격리된 개발 VM에서만 실행한다. 패키지 목록은 `dist/os-packages.tsv`에 기록한다. OS apt snapshot 및 Python wheel hash 전체 고정은 아직 미완료로 바이트 재현성을 주장하지 않는다.

## 이전 HTTPS 설치 경로 기록 — 기본 설치에는 사용하지 않음

압축 해제한 `.img`를 Raspberry Pi Imager의 사용자 지정 이미지로 지정하고, 사용자가 지정·삭제 허용한 대상 저장장치에 기록한다. 유선 LAN과 전원 연결 후 `https://justverify.local`로 접근하는 흐름을 목표로 한다. 장치별 인증서의 지문 확인이 필요하다. headless 준비 도구는 아직 CLI이며, 데이터 디스크 선택과 최초 프로필 등록은 TUI로 제공한다. 별도 데이터 mount가 없으면 Core 서비스를 시작하지 않도록 차단한다.

물리 기록, NVMe 직접 부팅, microSD+SSD, mDNS/IP 대체 및 실제 휴대폰은 아직 PASS가 아니다.

이전 개발 이미지는 보존되어 있다. 최신 상태는 이 문서 상단과 `docs/STATUS.md`에 기록한다. 실제 Pi 부팅은 BLOCKED다.

## HTTPS 초기 소유권 전달 — 선택적 개발 검증 경로

아래 코드는 별도 HTTPS 기기 코드 시험 경로다. 기본 LAN HTTP 설치에는 필요하지 않다.

로컬 콘솔 방식은 화면에서 Enter를 누르면 해당 장치의 인증서 SHA256과 일회성 코드를 표시한다. HTTPS에서 관리자 등록이 끝나면 코드를 삭제하고 콘솔을 고정 TUI로 바꾼다. 공통 기본 암호를 쓰지 않는다. 실제 Pi 디스플레이/브라우저 신뢰 UI는 아직 검증 대기다.

모니터 없는 개발 검증에는 다음 도구가 있다. 아직 일반 사용자용 GUI 준비 도구를 대체한 것은 아니다.

1. `python3 scripts/prepare_owner.py /private/location/justverify-owner.json`으로 장치마다 새 소유권 파일을 만든다. 개인 복사본은 설치 PC에 보관하고, 대상 이미지의 boot partition에 `justverify-owner.json`이라는 이름으로 복사한다. 이 파일에는 초기 소유권 비밀정보가 있으므로 공유하거나 Git에 넣지 않는다.
2. 첫 부팅은 장치에서 TLS key/certificate를 생성하고 파일을 private state로 가져온 뒤 boot 복사본을 삭제한다. 이미 소유권이 등록된 장치의 소유자를 이 파일로 바꾸지 않는다.
3. `python3 scripts/verify_pairing.py justverify.local --owner-file /private/location/justverify-owner.json --certificate-out /private/location/justverify-certificate.pem`은 소유권 파일을 사용하여 실제 TLS peer 인증서를 검증한다. 이 단계에서는 비밀 코드를 서버에 전송하지 않는다. 증명이 맞지 않으면 중단한다.
4. 검증된 인증서를 OS/브라우저의 신뢰 절차에 따라 등록한 뒤 `https://justverify.local`에 접속하여 소유권 파일의 일회성 코드로 관리자 암호를 설정한다. 지원 브라우저별 실제 신뢰/가져오기 UI 검증과 안내는 남아 있다.

이 경로의 암호학적 확인·HTTPS 등록 및 Linux 스크립트 실행은 시험했다. 데이터 디스크 선택과 최초 프로필 등록은 별도 ARM VM에서 실제 서비스 통합 검증을 통과했다. 실제 Pi 첫 부팅과 일반 사용자용 headless 준비 GUI는 아직 완료하지 않았다.

## 이전 개발 이미지 dev3

- 파일: `dist/justverify-0.1.0-dev3-rpi5-arm64.img.xz` (약856MiB). 검증: 해당 디렉터리에서 `shasum -a 256 -c justverify-0.1.0-dev3-rpi5-arm64.img.xz.sha256`.
- SHA256: `3571842365fdc706f5d2feaabb6ce94133baa8a1bb6deff7925efb86240b203c`.
- 소유자 등록·저장장치 설정·버전별 Core 경로·첫 프로필 확인·기동 조건을 포함한다. 의도한 순서는 소유자 등록→TUI S 데이터 디스크 검토/확인→V 버전·네트워크 선택/확인이다. S의 B는 버전 서비스 준비만 재시도한다.
- 실제 Pi에 기록/부팅한 검증은 아직 없다. 이 흐름은 VM에서 구성요소별 및 서비스 통합으로 검증했으며, dev3 이미지에서의 전체 설치 성공을 뜻하지 않는다. 지정되지 않은 실제 디스크에 기록하지 않는다.

## 이전 개발 이미지 dev4

- 파일: `dist/justverify-0.1.0-dev4-rpi5-arm64.img.xz`. SHA256 `eb44ed28fc3749ebc2df782c95d9129fc7f8a6a2cfb9508a11db3e6fa1804e03`. 같은 폴더에서 `shasum -a 256 -c justverify-0.1.0-dev4-rpi5-arm64.img.xz.sha256`로 확인한다.
- dev3에 V/R 이전 별도 프로필 복구, C 개별 node-read RPC 발급/폐기, Q Tor Electrum 주소 QR, 최신 웹 gateway를 추가했다. C는 완전한 모바일 지갑 지원을 의미하지 않는다.
- 읽기 전용 파일시스템 검사, Core/electrs hash, 최신 TUI/web byte 일치, 서비스 구성, 공통 identity 부재 및 QR/gateway runtime import PASS (`docs/evidence/pi-image-dev4-verify.log`). OS 패키지는 `dist/os-packages-dev4.tsv`에 기록한다.
- 서명된 최종 배포 후보가 아니다. 실제 Pi 설치/부팅, 물리 지갑·카메라, 모든 정책/설정, backup/update 및 재현 빌드 acceptance는 미충족이다.

dev4 일반 VM 부팅에서 OS 사용자 생성 화면이 함께 실행되는 결함을 발견했다. 전용 콘솔 표시를 방해할 수 있어 dev5에서 해당 서비스를 차단했다.

## 이전 개발 이미지 dev5

- 파일: `dist/justverify-0.1.0-dev5-rpi5-arm64.img.xz`. SHA256 `c97f8bf41e9cf589aa42c67a8f4118bbe8938e7d76461ae0afb7a4e129aa68b2`.
- 같은 폴더에서 `shasum -a 256 -c justverify-0.1.0-dev5-rpi5-arm64.img.xz.sha256`로 확인한다. OS 패키지 목록은 `dist/os-packages-dev5.tsv`다.
- dev4 기능을 포함하며 기본 OS의 사용자 생성 화면을 비활성화했다. 소유자 등록은 JustVerify 콘솔 또는 위 headless 준비 절차를 사용한다. 공통 Linux 암호나 자동 셸을 제공하지 않는다.
- 아직 개발 이미지다. 일반 ARM VM 시험은 Pi용 커널·펌웨어·실제 설치 매체 검증을 대신하지 않는다. 물리 Pi/휴대폰 및 남은 소프트웨어 acceptance가 통과하기 전까지 최종 배포 후보로 사용하지 않는다.

## 이전 개발 이미지 dev6

- 파일: `dist/justverify-0.1.0-dev6-rpi5-arm64.img.xz` (약872MiB). SHA256 `49f78e4faedf42db56acf7ef3dcb155d22d96173ff55a1965e18e12cddee5d6f`.
- 같은 폴더에서 `shasum -a 256 -c justverify-0.1.0-dev6-rpi5-arm64.img.xz.sha256`로 확인한다. OS 패키지 목록은 `dist/os-packages-dev6.tsv`다.
- V/W 별도 watch-only 프로필, C/W 개별 지갑 권한, C/T 별도 PSBT 준비·거래 전파 권한을 포함한다. 기존 노드 데이터와 지갑 권한을 자동 변경하지 않는다. 상세 절차는 `docs/MOBILE_CONNECTIONS.md`를 따른다.
- read-only 파일시스템·공식 Core/electrs hash·최신 소스/실행파일 일치·공통 인증정보 부재·Python 지갑/PSBT 모듈 import 검사를 통과했다. 최초 검사 공간 부족은 `/var/tmp` 사용으로 수정했으며 이미지 내용은 변경하지 않았다.
- 서명된 최종 배포 후보가 아니다. 실제 Pi 설치·부팅, 모바일/카메라 및 남은 필수 기능·검증은 미충족이다. 부팅 후 인증정보가 생성된 시험 복사본 대신 위의 원본 압축 이미지만 설치 후보로 사용한다.


### SSH 기본 접속 (사용자 요청 설정)

LAN에서 `ssh justverify@justverify.local` 또는 `ssh justverify@<LAN-IP>`로 접속한다. 초기 암호는 `justverify`이며 로그인 후 `passwd`로 변경할 수 있다. 변경한 암호는 재부팅 시 초기화하지 않는다. 사설 LAN 외부에서는 암호 로그인을 허용하지 않으며 root는 공개키만 허용한다. 기존 좁은 관리 API 외에 무제한 sudo는 제공하지 않는다. 웹 접속은 `https://justverify.local/`이며 HTTP는 이 주소로 안내한다. 기기별 자체 인증서의 최초 신뢰 확인은 필요하다.


### 현재 LAN 브라우저 설치 흐름

`http://justverify.local/` 또는 `http://<LAN-IP>/`를 연다. 처음에는 새 관리자 암호(12자 이상)와 새 암호 확인만 입력하고 시작하기를 누른다. 일회성 코드 입력은 필요 없다. 이후에는 관리자 암호 한 칸과 로그인 버튼만 표시된다. SSH 암호와 브라우저 암호는 별개다. 사용자 요청의 LAN HTTP 모드는 암호화되지 않은 연결이며 최초 LAN 등록자가 관리자 계정을 설정한다. HTTPS와 외부 RPC의 TLS는 별도 유지한다.
