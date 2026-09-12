# Tor 시간 초과: VM과 Pi 비교

## 후속: 새 dev16 Pi 실기 연결 (2026-09-12)

새 이미지를 NVMe에 기록하고 Pi5에서 부팅한 뒤, 독립 builder Tor client에서 새 Pi의 P2P handshake가6.400초, 실제 재부팅 후16.853초에 성공했다. 같은 Pi의 RPC onion도 변경하지 않은 패키지 gateway와 임시 node-read 계정으로 실제 Core `getblockchaininfo` HTTP200을12.537초에 받았다. 무인증401·허용 밖 읽기RPC403·관리 경로404도 확인했다. 운영 Remote RPC 설정은 원래 비활성이고, 시험 계정 폐기·임시 listener 종료를 완료했다.

이는 새 Pi에서 실제 P2P·인증 RPC 연결을 확인한 결과다. 아래 기존 VM RPC descriptor 게시 timeout을 수정하거나 같은 VM의 재시험을 통과한 결과는 아니다. Mainnet은 IBD 중이며 electrs 전체 인덱싱·실제 모바일 연결 완료와도 구분한다. 자세한 결과는 [Pi 실기 보고서](PI5_DEV16_VALIDATION.md)와 [증거](evidence/dev16-pi-hardware.json)에 있다.

## 원래 조사: 재설치 전 Pi와 실패 VM (2026-09-12)

아래 원래 조사에서는 재설치 전 Pi의 Tor P2P 연결을 실제 외부 클라이언트에서 정상 확인했다. VM 전체의 Tor 장애도 아니다. 실패는 VM의 RPC용 onion 게시·연결 준비 단계에서 재현됐다. 이 조사 당시에는 새 dev16 이미지를 Pi에 기록하거나 Pi 설정을 변경하지 않았다.

| 경로 | 실제 관측 |
|---|---|
| 별도 builder Tor → 현재 Pi P2P onion | PASS. SOCKS 연결3.447초, Bitcoin version/verack/ping/pong까지8.691초 |
| 실패한 VM의 Tor client → 현재 Pi P2P onion | PASS. 연결18.276초, Bitcoin 통신까지21.587초 |
| 별도 builder Tor → VM Electrs onion | PASS. 연결4.881초, electrs0.11.1/프로토콜1.4 및 regtest height1 응답6.286초 |
| VM Tor client → 같은 VM RPC onion | FAIL. SOCKS greeting 성공 뒤 CONNECT 응답을30초 기다리다 timeout. HTTP/RPC 요청 전 단계 |
| RPC 대상의 내부 loopback gateway | 앞선 실제 요청200/regtest PASS. 인증된 로컬 서비스 자체는 동작 |
| Pi 시계·Tor | NTP yes, Tor0.4.9.11, bootstrap100%, 경고/오류0 |
| VM 시계·Tor consensus | UTC10:49:59, consensus10:00–13:00 유효. Europe/London 표시의1시간 차이는 BST 시간대이며 실제 시계 오차 아님 |

## 확인한 원인과 확정하지 못한 부분

Tor 내부 로그에서 `Intro circuits aren't yet all established (2/3)` 대기가 반복됐다.240초 control event 관측 중 RPC는 descriptor CREATED/REQUESTED만 있었고 UPLOAD/UPLOADED는 없었다. 같은 구간에 P2P와 Electrs descriptor 게시 성공은 있었다. RPC introduction circuit 실패는 TIMEOUT4회, DESTROYED2회였다. 장시간 준비 후에도 동일 SOCKS CONNECT timeout이 재현됐다.

[Tor0.4.9.11 공식 소스](https://gitlab.com/torproject/tor/-/blob/f3d28b2e0978ca075ec324834bec077673478ded/src/feature/hs/hs_service.c#L3438)의 `should_service_upload_descriptor`는 선택한 introduction 경로가 모두 준비되지 않으면 주소 설명서 게시를 보류한다. [공식 control protocol](https://spec.torproject.org/control-spec/replies.html#hiddenservice-descriptors)의 HS_DESC 이벤트를 사용해 게시와 조회를 구분했다.

따라서 관측한 실패 경로는 **onion의 introduction 경로 형성 실패/지연 → descriptor 게시 대기 → 클라이언트의 SOCKS CONNECT 시간 초과**다. RPC 암호, Core 동기화, 잘못된 HTTP/HTTPS 접속에서 난 오류가 아니다. 다만 특정 Tor 중계기나 네트워크 구간 중 어느 곳이 introduction circuit 실패를 일으켰는지는 확정하지 않았다. Tor0.4.9.11 자체 결함, VM 전체 네트워크 결함, 모든 Pi Tor 접속 장애라고 단정할 근거는 없다. 기본 bootstrap100%만으로 개별 onion 준비를 판단하면 안 된다.

원래 조사 당시 Pi에서 확인한 범위는 P2P onion이었다. Pi RPC 인증 요청 및 새 이미지의 onion은 당시 NOT RUN이었고, 위 후속 실기 시험에서 별도로 확인했다. 기존 VM 실패 보고서를 PASS로 바꾸지 않았다.

## 보존과 재개

공개 요약은 [실행 증거](evidence/tor-vm-pi-diagnosis.json)에 있다. 주소가 포함된 control/info 원본과 명령은 `.state/tor-rootcause/`에 비공개 보존했다. Tor tag tor-0.4.9.11의 commit은 f3d28b2e0978ca075ec324834bec077673478ded다. 소스는 동작 확인만 했으며 재사용하지 않았다.

추적용 control socket은 인증 쿠키가 필요한0700 디렉터리의 Unix socket으로만 열었다. 최초0755 디렉터리 시도는 Tor가 거부했고 권한을 느슨하게 하지 않고 경로를 수정했다. 시험 종료 후 추가 systemd 설정을 제거하고 원래 서비스·onion 신원 보존을 확인했다. 시험 VM만 정상 종료했으며 실제 Pi와 기존 노드 데이터는 변경하지 않았다. 설치 이미지는 이번 조사로 변경되지 않았다.

후속 원인 분석은 같은 실패 clone/키를 보존한 상태에서 서비스별 introduction circuit 경로·실패 시점과 relay 상태를 대조해야 한다. 주소 재생성, introduction 경로 수 감소, 인증 완화, 시험 timeout 결과의 PASS 치환으로 해결하지 않는다.
