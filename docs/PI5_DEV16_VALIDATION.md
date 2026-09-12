# dev16 Pi 5 설치 후 검증 — 2026-09-12

결과는 **실기 초기 검증 통과, 전체 릴리스는 PARTIAL**이다. 새 NVMe 이미지의 부팅·확장·설정·재부팅과 아래 연결 시험을 실제 Pi에서 수행했다. Mainnet 전체 동기화와 electrs 전체 인덱싱, 실제 휴대폰 연결 및 남은 릴리스 기준은 완료하지 않았다.

## 대상과 설치물

- Raspberry Pi 5 Model B Rev1.0 /8GB, GeIL P3A2TB, IP192.168.10.47.
- 설치 raw: `justverify-dev16-pi5-private.img`, 6,444,548,096bytes.
- raw SHA256: `2e65e50b536c9fac6e48e8e63fcdff8b3d0d1dcfe891642bd54c87d9cbdecefe`.
- 조립 소스 b3c5f5b46d1a42042cfd675cc2130aa0bde4e449, 앱 SHA256 `8cfa9b71ac44586ad7c10c846adfab2acd3631200efa11f0ff11d6b203c7fd1c`. 설치된 웹 정적 파일13개도 현재 소스와 바이트 일치.
- 실제 커널6.18.34+rpt-rpi-2712, Core31.1.0, electrs0.11.1(35216c6d30148be8e6763d913d437330f431fc03), Tor0.4.9.11 고정 이미지.
- OS5GiB와 데이터 파티션1,994,492,288,512bytes 분리. 새 데이터 UUID `6c03c044-c89d-410e-9da9-5a48a8920d5e`. A/B OS 없음.

## 실제 결과

| 검증 | 결과와 범위 |
|---|---|
| NVMe 직접 부팅·첫 데이터 확장 | PASS. 이전 디스크와 다른 새 데이터 UUID, 지정 NVMe 모델/serial 재확인 |
| 최초 관리자 등록·자동 노드 시작 | 등록 완료 상태와 실제 main/31.1 프로필을 관측. 사용자 암호를 읽거나 변경하지 않음 |
| IP 및 mDNS HTTP | `http://192.168.10.47/`, `http://justverify.local/` HTTP200. 실제 브라우저 로그인 화면도 확인 |
| 기본 SSH | root 공개키 및 justverify 기본 암호 로그인 PASS. 새 설치 host key는 별도 known_hosts에 보관 |
| 비권한 실제 TUI | Pi 패키지 바이너리와 실제 mainnet 수집기로120/80/42열, 주요 박스·리사이즈·정상 종료 PASS |
| 물리 콘솔 프로세스 | justverify UID로 실제 TUI가 tty1 입출력에 연결됨. HDMI 화면 사진/글리프 육안 확인은 NOT RUN |
| 웹 인증·새로고침·고정 TUI | 설치된 웹 코드를 justverify로 별도 loopback 시험 계정에서 실행. 로그인/세션 재조회·CSRF/Origin 거부·로그아웃 폐기·실제 TUI WebSocket PASS. 사용자 실제 계정의 인증 세션은 사용하지 않음 |
| Favicon·QR·LAN TLS | 운영 HTTP에서favicon3종 바이트 일치, 실제LAN/Tor payload 디지털QR 해독 일치. LAN50002 TLS 인증서와 hostname 검증, QR fingerprint 일치 PASS |
| 설정·버전 카탈로그 | 실제 서비스의 버전34개/현재 Core31.1 설정43개 조회. 음수maxmempool preview HTTP409 거부. 이번 실기에서 mainnet 설정/버전을 바꾸지는 않음 |
| Tor P2P | 독립 builder Tor에서 실제 Bitcoin version/verack/ping/pong PASS. 첫6.400초, 실제 재부팅 후16.853초 |
| Tor RPC | 동일 Pi RPC onion에 임시 node-read 계정과 패키지 그대로의 gateway를 연결. 독립 Tor에서 인증 조회200, 무인증401, 허용 밖의 읽기 RPC403, 관리 경로404 PASS(12.537초). 시험 후 계정 폐기·listener 종료. 운영 Remote RPC 설정은 기본 비활성 그대로 |
| 실제 재부팅 | 웹의 power preview/apply와 실제 제한된 기기 API로 실행. 약44.6초 후 새 boot ID/SSH 확인. 설정·owner·TLS/SSH·Tor identity 등14개 해시와 데이터 UUID 유지, 바이너리/정적 파일 불변 |
| 체인 재개 | 재부팅 전265712 → 후273501. 이전 tip이 현재 체인의 같은 높이 조상임을 실제RPC로 확인. 서비스14개 active |
| 수집기 장애 복구 | manager만 SIGKILL, Core 프로세스 유지. 새 manager PID/재시작 수 증가/신선한 RPC snapshot까지4.81초 PASS. 두 번의 의도적 fault가 NRestarts=2에 포함됨 |
| 새 설정 백업 | 현재 기기 설정28개를41,063bytes 암호화 백업으로 생성·복호화 검사. Mac 전송 SHA256도 일치. 실제 restore는 NOT RUN |

웹 검증은 임시 계정과 운영 수집기/연결 주소를 사용했다. 사용자 관리자 등록·암호·선호 설정 및 운영 Remote Tor 설정은 바꾸지 않았다. 재부팅으로 기존 웹 세션은 종료되며, 단순 브라우저 새로고침의 세션 유지와 구분한다.

## 실제 regtest 지갑 거래

운영 mainnet 프로필과 서비스는 유지하고 별도 데이터 디렉터리·loopback19543/19544/19501에서 설치된 Core/electrs 바이너리를 justverify UID로 실행했다. 네트워크는 regtest, 외부 피어 연결 없음. 송신/수신 테스트 지갑과101개 블록으로 테스트 자금을 만들었다.

`createrawtransaction → fundrawtransaction → signrawtransactionwithwallet(complete=true) → testmempoolaccept(allowed=true) → Electrum blockchain.transaction.broadcast` 순서를 실제 실행했다. Core mempool과 Electrum 미확인 이력, 수신 지갑 확인 수0을 확인했다. 두 블록을 추가해0→1→2 확인 및 수신 잔액1 BTC(오직regtest)를 검증했다.

- 네트워크: 격리 regtest.
- txid: `5c68bc124d2ab0edf21a739dc16d338b9181afe7f5974aaef899eca0db03ab73`.
- 확정 높이102, 마지막 높이103/확인 수2.
- Core/electrs 일치 tip: `66712609a2df6231e4405a57ae69235fb32f7ac0b22549cbd4dd35e3e01c68f1`.
- electrs 재시작 후 이력 유지 PASS. 실제 Pi 재부팅 후 동일 체인·지갑·인덱스를 다시 열어 높이/tip/확인 수/잔액 유지 PASS.
- 시험 프로세스를 종료하고 로그·결과를 Mac에 보존한 뒤 시험 지갑 개인키와 데이터만 제거했다. mainnet 거래 생성이나 실제 자금 사용은 없었다.

이번 regtest에서 실제 호출한 Core RPC는 `getblockchaininfo`, `getnetworkinfo`, `createwallet`, `getnewaddress`, `getaddressinfo`, `generatetoaddress`, `getbestblockhash`, `createrawtransaction`, `fundrawtransaction`, `signrawtransactionwithwallet`, `testmempoolaccept`, `decoderawtransaction`, `getrawmempool`, `gettransaction`, `getbalances`다. Electrum은 `server.version`, `blockchain.headers.subscribe`, `blockchain.transaction.broadcast`, `blockchain.scripthash.get_history`를 검증했다. 이 목록은 전체 Core RPC 카탈로그 검증 완료를 뜻하지 않는다. 기존 버전별 RPC 조사와 미검증 범위는 ACCEPTANCE.md의 별도 결과를 유지한다.

## 동기화 증거와 남은 기준

최종 저장 관측 시각2026-09-12 12:50:06 UTC: mainnet blocks303442/headers966678, IBD=true, peers10. tip `00000000000000004b97a41f4ecca9de8829aa5045bdf86fa283ab6cdaf0f8f2`. Core는 계속 동기화 중이다. electrs는 process active이지만 Core IBD를 기다리며, 실제 Electrum 응답/전체 인덱스 준비를 아직 확인하지 못했다. TLS 접속 성공을 인덱싱 완료로 세지 않았다.

남은 항목은 mainnet IBD 종료와 electrs 높이·tip 일치, 실제 휴대폰 카메라·지갑 연결, HDMI 실제 표시, 전체 동기화 이후24시간 운영 및 ACCEPTANCE.md의 정책 의미/업데이트 실패/새 볼륨 복원/OS 재현 빌드 게이트다. 이전 VM RPC onion 게시 timeout 기록도 삭제하거나 PASS로 바꾸지 않았다. 이번 실제 Pi에서는 별도의 인증 RPC 연결이 성공했다.

## 실패·재시험 및 증거

시험 실행기에서 PTY 종료 중 출력 미수집, 리사이즈 시 UTF-8 decoder 초기화, root 소유 데이터 루트에 시험 디렉터리 생성, 임시 웹 재시작 직후 접속, manager 첫 sample 전 빈 snapshot, ps의 USER 열 축약을 각각 발견했다. 출력 배출·decoder 유지·시험 전용 상위 폴더·준비 확인·신선한 sample 대기·숫자 UID 검사로 고쳤으며 정상 종료·정확한 데이터·권한 기준을 유지했다. 실패 로그와 원인을 `.state/pi5-install/dev16-*`에 보존했다. 제품 코드는 이번 검증에서 변경하지 않았다.

- 공개 요약: `docs/evidence/dev16-pi-hardware.json`, `dev16-pi-regtest-transaction.json`.
- 읽기 관측기: `tests/pi_readonly_observe.py`. 실행: 승인된 Pi SSH를 통해 `python3 - < tests/pi_readonly_observe.py`를 원격 stdin으로 전달하고 결과를 Mac JSON에 저장.
- 독립 지갑 시험: `tests/pi_regtest_transaction.py --state <새 jv-validation- 디렉터리>`. 설치된 Pi 바이너리 전용. 기존 상태 재사용/삭제를 하지 않는 시작 guard 포함.
- 재부팅·TUI·Tor·웹·장애·원본 로그와 실행기: `.state/pi5-install/dev16-*`.
- 새 암호화 백업: `.state/pi5-install/dev16-postboot-backup/`. 백업 및 별도0600 암호 파일은 개인 자료이며 Git/설치 이미지에 넣지 않았다. 기존 dev15 재설치 전 백업도 그대로 보존했다.
- 배포 이미지와 서명 번들은 불변. 새 시험 코드와 이번 실기 증거는 별도 저장소 checkpoint다.
