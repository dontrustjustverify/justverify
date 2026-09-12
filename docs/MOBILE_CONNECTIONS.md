# 모바일 연결 상태

## 실제 검증된 범위

- 현재 소스는 C/O에서 원격 RPC 상태·미리보기·관리자 암호 재확인·적용을 제공한다. 별도 제품 RPC onion의 8332가 제한된 loopback gateway에 연결되며 기본 listener는 닫혀 있다. 실제 비권한 TUI, 제품 systemd Tor onion, Core 조회, 프로세스 재시작 복원과 비활성화를 검증했다 (`docs/evidence/remote-rpc-tui-tor.log`). OS 재부팅과 새 이미지는 아직 남아 있다.

- 선택적 Tor RPC listener를 Core22.0/31.1로 검증했다. HTTPS와 호출 한도를 공유하며 관리자/정적/TUI 경로는 제공하지 않는다. 격리 Tor와 제품 systemd Tor 양쪽에서 실제 v3 onion→Core31.1 조회·배정 watch-only 지갑·인증 차단 PASS (`docs/evidence/tor-rpc-transport.log`, `docs/evidence/remote-rpc-tui-tor.log`). dev8에는 아직 포함되지 않았고 실제 모바일 앱은 남아 있다.

- dev8 이미지 시험 사본(외부 Debian 커널)의 최초 설정과 실제 재부팅에서 LAN TLS Electrum 조회, Q/L 연결 화면, 지갑/PSBT/coin-control API 및 인증 유지 PASS (`docs/evidence/image-dev8-data-probe.json`). 아래 dev7 이후 소스 변경은 dev8에 포함됐다. 별도 LAN 단말·실제 모바일 앱·카메라는 아직 미검증이다.

- Core 31.1 + electrs 0.11.1: Tor SOCKS → v3 onion → 실제 Electrum headers 조회 PASS (`docs/evidence/onion-electrum.json`).
- 배포 가능한 Core 22~31.1의 32개 조합: 실제 Electrum 거래 전송→Core mempool→이력→블록 확정→인덱서 재시작 PASS. 모바일 앱 실행 증거와 구분한다.
- TUI Q 또는 C→Q는 기기에서 게시된 Tor Electrum `host:50001`을 일반 텍스트 QR로 표시한다. 120×40 실제 PTY 모듈과 디지털 decoder 원문 일치 PASS; 80×24에서는 잘린 QR 대신 화면 확대를 안내한다 (`.state/electrum-qr-pty.log`, `.state/electrum-qr-decode.log`). 실제 카메라 인식은 BLOCKED.
- TUI C에서 개별 node-read RPC 클라이언트 발급·일회성 비밀번호 표시·폐기 확인/취소를 구현했다. 실제 TLS Core 조회, 서버 프로세스 재시작 후 인증 유지, 폐기 후 401, 비밀번호 원문 비저장/로그 부재 PASS (`.state/rpc-root-restart.log`).

## 주소와 권한

Q 화면에서 T는 Tor TCP `onion:50001`, L은 LAN TLS `justverify.local:50002`를 선택한다. Tor 경로는 지갑 기기의 Tor SOCKS 설정이 필요하고 TLS는 아니다. LAN 경로는 지갑에서 SSL/TLS를 선택하고 기기 인증서를 신뢰해야 한다. 화면에 인증서 SHA256을 표시하며 인증서 검증을 끄도록 안내하지 않는다. 두 QR 모두 일반 host:port 텍스트이며 Nunchuk 자동 가져오기나 FullyNoded btcrpc 형식으로 표시하지 않는다.

LAN TLS 서비스는 등록된 볼륨/프로필 이후에만 시작하며, electrs의 localhost TCP로 연결한다. 별도 `justverify-electrum-tls` 비권한 서비스가 기존 기기 인증서를 사용한다. IPv4 사설 대역·링크 로컬·loopback만 허용하며 IPv6는 현재 제공하지 않는다. 실제 개발 VM에서 신뢰한 인증서 연결과 실제 electrs header 일치, 신뢰하지 않은 인증서·평문·비LAN 출발 주소 거부, electrs/TLS 재시작 및 연속 프로필 전환을 검증했다 (`docs/evidence/electrum-tls-profile.log`). QR은 실제 PTY 셀 추출 후 디지털 decoder로 검증했다 (`docs/evidence/electrum-lan-qr-decode.json`). 이 변경은 dev7 이후 소스이며 새 이미지 부팅, 별도 LAN 단말/mDNS, 실제 앱의 인증서 등록과 카메라 시험은 남아 있다.

RPC는 기기 HTTPS 서버의 POST `/rpc`와 POST `/`, 그리고 opt-in Tor RPC onion의 동일 경로에서 같은 제한 게이트웨이를 사용한다. HTTPS GET `/`만 브라우저 화면이며 Tor onion에는 GET·관리·정적·TUI 경로가 없다. 클라이언트별 Basic 인증을 사용하고 새 클라이언트는 `node-read`이며 추가 권한은 아래 순서로 부여한다. Core cookie는 loopback 내부에만 쓰고 외부 클라이언트에 전달하지 않는다.

## Watch-only 및 거래 권한 — 개발 검증 경로

1. V 화면의 W로 watch-only 모드를 선택하고 Enter로 별도 데이터·인덱스 경로를 검토한다. 최초 선택은 새 동기화와 저장공간이 필요하다. 기존 node 데이터를 같은 경로에서 변경하지 않는다.
2. C의 A로 클라이언트를 발급한다. 비밀번호는 한 번 표시된다. C/W에서 현재 버전·네트워크·배정 지갑을 검토하고 지갑 조회·공개 descriptor 가져오기 권한을 부여한다.
3. 거래 준비와 전파가 필요하면 C/T에서 별도 거래 권한을 검토한다. 기존 조회 권한에 자동 추가하지 않는다. 목록에 `watch-only + transactions`로 표시한다.
4. `/wallet/<배정된 이름>`은 그 클라이언트의 지갑만 허용한다. 다른 이름, 개인키 가져오기·내보내기, 노드 서명과 관리 RPC는 거부한다. PSBT 처리의 sign은 false로 고정된다. 서명은 별도 서명자에서 수행한다.
5. C/R로 클라이언트를 폐기하면 접근을 차단하되 지갑 데이터는 보존한다. 권한은 프로필과 볼륨 UUID에 묶인다. 기존에 배정한 지갑 파일이 없어지면 빈 지갑을 대신 만들지 않는다.

32개 Core 버전에서 실제 TLS PSBT 자금 선택→서명 없는 처리→별도 시험 지갑 서명→전파→확정을 검증했다 (`docs/evidence/psbt-tls-matrix.json`). 시험 서명자는 격리 regtest의 별도 키 지갑이며 실제 휴대폰·하드웨어 서명자가 아니다. 개별 거래 옵션 및 대상 앱의 전체 호출 순서는 추가 검증이 필요하다. `fee_rate`는 sat/vB, `feeRate`는 BTC/kvB이며 동시에 지정할 수 없다.

현재 소스는 UTXO 잠금 조회(`listlockunspent`)와 잠금·해제(`lockunspent`)도 지원한다. 조회는 watch-only 권한, 변경은 C/T 거래 권한이 필요하며 배정된 지갑에만 적용한다. `unlock`과 선택한 `transactions`만 허용하고, 영구 잠금 옵션은 제공하지 않는다. 잠금이 재시작 후 유지된다고 표시하지 않는다. `unlock=true`에 거래 목록을 생략하면 배정 지갑의 잠금을 모두 해제한다. 32개 Core 버전의 실제 TLS 시험에서 권한 차단, 자금 선택 제외, 해제 후 자금 선택, 지갑 간 격리, 잘못된 입력의 상태 보존을 검증했다 (`docs/evidence/coin-control-tls-matrix.json`). 이 변경은 dev7 이미지 이후 소스이며 다음 이미지에 포함해야 한다.

## 공식 앱 소스 조사

출처 commit·파일 SHA256·관측한 release 태그는 `catalog/mobile-source-audit.json`에 있다. 조사한 기본 브랜치 commit이 해당 release 바이너리와 같다고 추정하지 않는다. 제3자 코드는 제품에 복사하지 않았다.

| 앱 | 조사 결과 | 남은 작업 |
|---|---|---|
| Nunchuk Android | 서버 주소 입력과 별도 proxy 설정을 확인 | 해당 release 앱 설치, Tor 설정, 연결·거래, 카메라 QR 및 자동 가져오기 지원 여부 확인 |
| FullyNoded | QuickConnect는 host/port/credentials를 저장한다. MakeRPCCall은 기본 HTTP, 저장된 cert가 있으면 HTTPS를 사용하고 지갑 요청에는 `/wallet/<name>`을 붙인다 | 인증서 등록·앱별 필수 RPC 및 coin-control 호환·실제 앱 시험 |

FullyNoded의 [요청 구성 소스](https://github.com/Fonta1n3/FullyNoded/blob/d0d1502eef2840c0457aa321b88cf606ee8b4650/FullyNoded/Helpers/URL%20Requests/MakeRPCCall.swift)와 [명령 목록](https://github.com/Fonta1n3/FullyNoded/blob/d0d1502eef2840c0457aa321b88cf606ee8b4650/FullyNoded/Helpers/Commands.swift)을 조사했다. 명령 목록에 있다는 이유로 모든 메서드를 허용하지 않는다. 구현된 watch-only·PSBT 경계를 실제 앱의 가져오기·거래 흐름과 대조해야 한다.

동일 commit의 `Docs/Quick-Connect-QR.md`와 `QuickConnect.swift`에서 `btcrpc://<rpcuser>:<rpcpassword>@<onion>:<port>?label=...` 형식과 실제 파싱 필드를 확인했다. C/A 발급 화면에서 Q를 명시적으로 눌렀을 때만 이 민감 QR을 표시한다. 실제 PTY 모듈과 별도 decoder 원문 일치는 PASS지만 설치된 앱의 스캔 성공은 아직 주장하지 않는다.

동일 commit의 `UTXOViewController.swift` 256–258행과 `LockedViewController.swift` 43·94–95행에서 실제 잠금·조회·해제 호출 경로를 확인했다. 고정 파일의 URL과 SHA256을 카탈로그에 추가했다. 앱 코드는 재사용하지 않았다. 앱 설치본·인증서 등록·전체 호출 순서가 검증됐다는 뜻은 아니다.

## 미충족 acceptance

실제 Nunchuk/FullyNoded 설치본 연결, 카메라, 별도 LAN 단말 및 모바일 인증서 신뢰, FullyNoded 전체 호출 순서는 완료되지 않았다. Tor RPC와 Quick Connect 형식은 소프트웨어 시험 범위에서 통과했다. 휴대폰 접근은 BLOCKED이며 나머지 소프트웨어 구현·시험은 계속할 수 있다. 개발 Tor 개인키와 RPC 비밀번호는 Git·이미지·진단자료에 포함하지 않는다.
