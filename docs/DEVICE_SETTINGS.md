# 일반 설정과 계정·기기 관리

2026-09-12 사용자 요청으로 구현한 웹 설정 화면. 독립 작성한 얇은 power-line SVG는 **로그아웃**이며, 실제 전원 종료는 설정의 **시스템 종료**다. 아이콘은 Apple/Umbrel 자산을 복사하지 않았다. 상단 로고21px 대비 로그아웃16.8px, 터치 영역44px, 중심 높이 차이0px를 실제 브라우저에서 확인했다.

## 사용

`http://justverify.local/` → 로그인 → **설정 → 일반**.

- 디바이스는 실제 device-tree model, 로컬 IP는 실제 인터페이스, Uptime은 `/proc/uptime`에서 읽는다. OS 버전은 이미지 빌드 때 기록한 `/etc/justverify/os-release.json`이다. 기존 Pi에는 설치 기록에 근거해 `dev15 (development)`를 기록했다. 현재 Core 버전을 OS 버전으로 표시하지 않는다.
- 계정명은 웹 관리자의 표시 이름이다. 웹 관리자 암호 변경은 현재 암호·새 암호·확인 입력을 받으며 모든 웹 세션을 폐기한다. SSH 계정/암호와 별개다. 실제 소유자의 암호는 취득하거나 변경하지 않았다.
- Teal `#50D4C7`, Amber `#FFB000`, Green `#00FF00`, Ice `#F0FFF8`. 강조 글자·테두리·버튼은 선택 색의 계열을 사용한다. 경고·종료 의미 색과 QR 흑백은 유지한다.
- 한국어 기본, English, 日本語. 웹 로그인·현황·일반 설정·Core 설정/버전·Electrs 라벨과 안내에 적용한다. 기존 ANSI 상세 터미널(스토리지/백업/진단/RPC) 문구와 공식 Core 옵션 원문은 별도이며 번역 완료 범위에 포함하지 않는다. 터미널 색상은 선택 테마를 적용한다.
- 계정명·색상·언어는 서버의 private `preferences.json`에 원자적으로 저장한다. 브라우저에는 로그인 전에도 적용할 색상/언어만 저장한다. 새로고침은 기존 유효 세션을 복원한다. 서버 재시작이나 암호 변경 후에는 재로그인이 필요하다.
- 재시작·종료는 작업 설명과 현재 암호 확인 후 좁은 root Unix API가 고정 `systemctl` 명령을 실행한다. Core/electrs의 정상 종료를 기다린다. 종료 후 다시 사용하려면 실제 기기의 전원을 켜야 한다.

## Remote Tor access

관리 화면용 별도 onion의 포트80을 loopback `127.0.0.1:28444`에 연결한다. 기본은 꺼짐이며, 켜면 Tor Browser에서 열 주소를 표시한다. Tor 안에서 HTTP를 사용하며 외부 LAN에 이 listener를 bind하지 않는다. [Tor 공식 onion 설정 안내](https://community.torproject.org/onion-services/setup/)의 서비스별 identity와 virtual-port mapping을 근거로 독립 구현했다.

이 토글은 기존 RPC onion8332→28443 또는 Electrs onion50001을 변경하지 않는다. 관리자 로그인, 정확한 onion Host/Origin, CSRF, 실패 시도 제한을 적용하고 Tor 쿠키를 LAN/HTTPS와 분리한다. onion 경로의 최초 등록과 직접 Core RPC는 차단한다. 끄면 Tor 세션과 stream을 폐기하며, 같은 Tor 세션에서 끄는 요청도 정상 응답 후 연결이 닫힌다.

`remote-web.json`은 적용 중/확정 상태를 구분해 저장하며 중단 상태는 닫힌 채 복구를 요구한다. 새 preference와 web onion identity는 암호화 백업에 포함된다. 기존 v1 백업에서 새 optional 항목만 없을 수 있으며 기존 필수 항목·서명/암호화·경로 검사는 유지한다. 옛 Tor 설정을 복구하면 웹 원격 접속은 준비되지 않을 수 있으며, 현재 canonical Tor 설정으로 갱신하기 전에는 켜지 않는다.

## 실제 검증

| 검증 | 환경 | 결과/증거 |
|---|---|---|
| HTTP/TLS 등록·인증·WS·CSRF·로그아웃·새로고침 | Mac 실제 서버/고정 TUI | PASS `.state/device-settings/lan-auth.log`, `tls-auth.log` |
| 이름·4개 테마·3개 언어 저장, 암호 교체/이전 암호 차단/세션폐기 | 격리 Linux 실제 웹/기기 API | PASS `api-retest.log` |
| Tor SOCKS 실제 onion HTTP 로그인·Core snapshot, Host/Origin 거부, RPC 분리 | Linux/Tor 공개망 | PASS `tor-probe.log`, `tor-reboot-disable-retest.log` |
| 기존 원격 RPC enable/disable/restart/occupied-port recovery | Linux 실제 Core31.1 regtest | PASS `remote-rpc-retest.log` |
| 실제 재부팅, 실제 poweroff와 VM 재기동, 설정 hash·서비스 유지 | Linux ARM64 VM | PASS `before-reboot.txt`, `after-reboot.txt`, `before-shutdown.txt`, `after-shutdown-start-retest.txt` |
| 4개 Tor identity의 실제 GPG 암호화·복구·중단 복구, legacy 호환 | 격리 실제 파일/GPG | PASS `backup-four-onions.log`, `backup-device-retest.log` |
| 실제 Pi backup context·identity snapshot 검증 | Pi5 | PASS `pi-backup-snapshot.log` (31 entries) |
| 모델/IP/OS/Uptime, desktop/mobile, theme/language/refresh/logout | Pi5 배포 코드 + 별도 시험 계정, 실제 browser 1200/390px | PASS `pi-desktop-amber.png`, `pi-mobile-ice-ja.png`; JS error 없음/가로 넘침 없음 |
| 배포한 web/관리 script/unit 소스 일치 | Pi5 | PASS32 files, manifest `af1f412a1dadd6bec23ce027a43d9f72a0228a53153c3d6ddbe162d557c6051c` |

명령: `tests/web_lan_onboarding.py`, `tests/web_security.py`, `tests/device_settings_api.py`, `tests/device_tor_probe.py`, `tests/device_power_probe.py reboot|shutdown`, `tests/backup_bundle.py`, `tests/backup_device_compat.py`, `tests/remote_rpc_control.py`. 전원 시험은 `justverify-dev` 격리 VM으로 제한한다. `tests/linux_device_fixture.py prepare|restore`가 원본을 보존/복원한다. API 시험과 UI 시험은 암호 교체 경합을 피하도록 순차 실행한다.

실패 기록도 보존했다: IP JSON 빈 객체는 실제 원인 수정, Mac 백업 fixture의 symlink 경로는 canonical 경로로 수정, VM 테스트 홈 접근권한은 root-owned 시험 설치 경로로 수정했다. Pi Tor config validation은 root가 아닌 실제 debian-tor 사용자로 재검증했다. 첫 background VM 재실행이 유지되지 않아 foreground 관리 세션으로 부팅했다. 반복 UI 입력/언어 변경 중 재클릭은 값을 명시 설정하고 저장 완료 후 검증했으며, 저장 중에는 컨트롤을 비활성화했다. 테스트 삭제나 mock 대체는 없다.

## 배포와 남은 범위

Pi 원본 파일은 `/root/jv-before-device-settings/paths.json`과 해당 번호 파일에 보존했다. 교체 전 웹은 `/opt/justverify/web-device-previous`에도 있다. 이후 추가한 backup_service 표시 문구만 이전 목록 밖이며, Git 이전 revision으로 되돌릴 수 있다. 복구 시 사용자 state와 Core/electrs 데이터는 지우지 않는다. Tor 새 identity를 유지하려면 rollback 시 web identity 디렉터리를 보존한다.

실제 Pi는 웹·관리·백업 서비스를 새 코드로 실행하며 Core31.1 mainnet IBD를 계속한다. 관측 blocks408969→409052→409946→412363, headers966652, IBD=true. 이 결과는 전체 동기화/electrs 인덱싱 완료가 아니다. 새 이미지 빌더에는 코드·root device service·OS version metadata를 연결했지만 이번 변경의 새 이미지 빌드/기록/부팅은 NOT RUN이다. Pi에서 이번 전원 버튼으로 종료하는 시험은 NOT RUN; 해당 동작은 VM에서 검증했다. 실제 모바일 앱/카메라, 전체 S4 릴리스 조건은 기존 미완료 상태다.
