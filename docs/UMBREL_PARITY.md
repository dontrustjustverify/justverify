# Umbrel 설정·연결 소스 대조 (2026-09-12, 진행 중)

전체 대응 완료 판정: **미완료**. 이 표는 누락을 포함한 실제 상태이며 일반 네트워크/자원 설정 UI의 완성을 대신하지 않는다.

공식 GitHub 저장소를 직접 clone하여 검토했다. 제품 코드는 독립 작성이며 Umbrel 코드를 복사하지 않았다. Umbrel 두 저장소의 LICENSE.md는 PolyForm Noncommercial 1.0.0; electrs 0.11.1은 MIT다. 파일 해시: [upstream-audit.json](evidence/upstream-audit.json).

- [umbrel-bitcoin 2fe07948](https://github.com/getumbrel/umbrel-bitcoin/tree/2fe07948f99e101dbee95ce34e5947a69c441ee4): metadata/schema → config.ts → bitcoind manager 실제 적용 경로.
- [Umbrel bfa79ed2](https://github.com/getumbrel/umbrel/tree/bfa79ed24031b0065dd2f810411d58b82af1b95e): apps/app.ts의 앱별 데이터 경로·onion hostname·기기 seed 기반 앱 암호. 앱별 Core 설정은 umbrel-bitcoin 책임.
- [electrs 개발 HEAD da1860e6](https://github.com/romanz/electrs/tree/da1860e623587647542c5ad31164626b8a3cb3ed)와 [제품 0.11.1 / 35216c6d](https://github.com/romanz/electrs/tree/35216c6d30148be8e6763d913d437330f431fc03)를 구분했다. HEAD REST 요구사항을 0.11.1에 소급 적용하지 않는다.
- [Core v31.1 / 9be056a8](https://github.com/bitcoin/bitcoin/tree/9be056a8a72b624dae9623b2f7bded92c2a21c91). 전체 지원 버전의 실행 help/source는 catalog/runtime-options.json, catalog/policy-*.json, docs/evidence/core-matrix에 있다.

아래 기본값·범위는 Umbrel 현재 metadata에서 읽은 값이다. 범위 미지정은 무제한 안전을 뜻하지 않는다. JustVerify 정책은 선택 버전 Core 기본값을 상속하고 src/policy.rs에서 정수/고정소수점·overflow·충돌 검증 후 실제 선택 바이너리로 preflight한다. catalog의 range:null 및 SEMANTIC_REVIEW_REQUIRED는 아직 미완료인 근거 상태다. 일반 설정은 미구현 항목을 숨겨 완료로 처리하지 않는다.

| Umbrel 항목 | Umbrel 기본값 / 명시 범위 / 버전 제한 | 실제 변환 | JustVerify 현재 적용 및 차이 |
|---|---|---|---|
| `onlynet` | default=['clearnet', 'tor', 'i2p'] | clearnet→ipv4+ipv6, tor→onion, i2p→i2p 반복 onlynet | M outgoing: ipv4,ipv6,onion 선택 → 반복 onlynet 저장. Core22의 Tor 제외에는 파생 noonion=1. 입력/실제 preflight/원자 저장/재시작/getnetworkinfo 검증 구현. inbound/manual 제한 아님. |
| `proxy` | default=false | true→proxy=TOR_HOST:SOCKS_PORT; clearnet+tor 없으면 false | M outgoing:0/1 → direct 또는 고정127.0.0.1:9050. 실제 Core IPv4 P2P handshake 및 프로세스 TCP socket으로 Tor 경유 검증 PASS. 임의 proxy 주소 거부. |
| `privatebroadcast` | default=false; introducedIn='v31.1' | boolean→0/1; privacy network 없으면 false | 31.1 public-network startup tested with isolated networkactive=0.31.0 enable refused for official IP leak; regtest connect=0 and non-onion outgoing combinations refused. Actual private-broadcast transport NOT RUN. |
| `asmap` | default=false; introducedIn='v31.0' | enabled→asmap=1, disabled→생략 | M: embedded ASMAP31.x only, asmap=1 / noasmap=1. Actual startup bucketing logs and on/off tests PASS; arbitrary files and older file-based workflow not exposed. |
| `listen` | default=[] | 항상 listen=1; listenonion 및 i2pacceptincoming; 0.0.0.0 bind 유지 | M incoming: none/clearnet/tor/both derives network-scoped bind overrides; actual Core-owned sockets, LAN/RPC isolation, TUI, rollback and VM reboot PASS. Internal electrs P2P remains available. |
| `peerblockfilters` | default=true | true이면 blockfilterindex=true 강제 | M: requires explicitly reviewed blockfilterindex=1. Actual COMPACT_FILTERS service flag and index completion tested. |
| `blockfilterindex` | default=true | boolean→0/1 | M: Core default0 retained; bool enables basic filter index. getindexinfo, real getblockfilter and index completion/restart tested. |
| `peerbloomfilters` | default=false | 동명 Core 옵션; boolean→0/1 | M: Core default0 retained; actual BLOOM service flag on/off tested. |
| `bantime` | default=86_400 | 동명 Core 정수 옵션 | M: implemented through versioned resource catalog, input validation, preview, real Core preflight, atomic save and coordinated Core/electrs restart. Core defaults retained; accepted bounds and units shown. Actual startup log evidence distinguished from RPC. |
| `maxconnections` | default=125 | 동명 Core 정수 옵션 | M: implemented through versioned resource catalog, input validation, preview, real Core preflight, atomic save and coordinated Core/electrs restart. Core defaults retained; accepted bounds and units shown. Actual startup log evidence distinguished from RPC. |
| `maxreceivebuffer` | default=5000 | 동명 Core 정수 옵션 | M: implemented through versioned resource catalog, input validation, preview, real Core preflight, atomic save and coordinated Core/electrs restart. Core defaults retained; accepted bounds and units shown. Actual startup log evidence distinguished from RPC. |
| `maxsendbuffer` | default=5000 | 동명 Core 정수 옵션 | M: implemented through versioned resource catalog, input validation, preview, real Core preflight, atomic save and coordinated Core/electrs restart. Core defaults retained; accepted bounds and units shown. Actual startup log evidence distinguished from RPC. |
| `peertimeout` | default=60; min=1 | 동명 Core 정수 옵션 | M: implemented through versioned resource catalog, input validation, preview, real Core preflight, atomic save and coordinated Core/electrs restart. Core defaults retained; accepted bounds and units shown. Actual startup log evidence distinguished from RPC. |
| `timeout` | default=5000; min=1 | 동명 Core 정수 옵션 | M: implemented through versioned resource catalog, input validation, preview, real Core preflight, atomic save and coordinated Core/electrs restart. Core defaults retained; accepted bounds and units shown. Actual startup log evidence distinguished from RPC. |
| `maxuploadtarget` | default=0; min=0 | 동명 Core 정수 옵션 | M: implemented through versioned resource catalog, input validation, preview, real Core preflight, atomic save and coordinated Core/electrs restart. Core defaults retained; accepted bounds and units shown. Actual startup log evidence distinguished from RPC. |
| `dbcache` | default=450; min=4 | 동명 Core 정수 옵션 | M: implemented through versioned resource catalog, input validation, preview, real Core preflight, atomic save and coordinated Core/electrs restart. Core defaults retained; accepted bounds and units shown. Actual startup log evidence distinguished from RPC. |
| `prune` | default=0; min=0 | GB×953.674 반올림→MiB; txindex/txospenderindex 해제 | prune=0 고정. electrs0.11.1이 pruning 거부하므로 의도적 제한; 인덱서 중단 없는 prune 토글 금지. |
| `txindex` | default=true | boolean→0/1; prune와 충돌 | M: optional, Core default0; electrs does not require it. Actual index completion, raw transaction lookup and restart persistence tested. Index files retained on disable. |
| `txospenderindex` | default=false; introducedIn='v31.0' | 동명 Core 옵션; boolean→0/1 | M: only releases whose executed help exposes it (31.x). Actual confirmed spent-output lookup and index/restart persistence tested. |
| `datacarrier` | default=true | 동명 Core 옵션 | M 정책: 입력→diff→private preflight→atomic managed.conf→재시작/health. Core 기본값 1; 전체 행동 범위 검증 미완료 |
| `datacarriersize` | default=100_000; min=0; max=100_000 | 동명 Core 옵션 | M 정책: 입력→diff→private preflight→atomic managed.conf→재시작/health. Core 기본값 100000; 전체 행동 범위 검증 미완료 |
| `permitbaremultisig` | default=true | 동명 Core 옵션 | M 정책: 입력→diff→private preflight→atomic managed.conf→재시작/health. Core 기본값 1; 전체 행동 범위 검증 미완료 |
| `maxmempool` | default=300 | 동명 Core 옵션 | M 정책: 입력→diff→private preflight→atomic managed.conf→재시작/health. Core 기본값 300; 전체 행동 범위 검증 미완료 |
| `blockmintxfee` | default=0.001; min=0; max=2_100_000_000_000 | 동명 Core 옵션; sat/vB→BTC/kvB 정확한 고정소수점 변환 | M 정책: 입력→diff→private preflight→atomic managed.conf→재시작/health. Core 기본값 0.00000001; 전체 행동 범위 검증 미완료 |
| `minrelaytxfee` | default=0.1; min=0; max=2_100_000_000_000 | 동명 Core 옵션; sat/vB→BTC/kvB 정확한 고정소수점 변환 | M 정책: 입력→diff→private preflight→atomic managed.conf→재시작/health. Core 기본값 0.000001; 전체 행동 범위 검증 미완료 |
| `incrementalrelayfee` | default=0.1; min=0; max=2_100_000_000_000 | 동명 Core 옵션; sat/vB→BTC/kvB 정확한 고정소수점 변환 | M 정책: 입력→diff→private preflight→atomic managed.conf→재시작/health. Core 기본값 0.000001; 전체 행동 범위 검증 미완료 |
| `mempoolexpiry` | default=336 | 동명 Core 옵션 | M 정책: 입력→diff→private preflight→atomic managed.conf→재시작/health. Core 기본값 336; 전체 행동 범위 검증 미완료 |
| `persistmempool` | default=true | 동명 Core 옵션 | M 정책: 입력→diff→private preflight→atomic managed.conf→재시작/health. Core 기본값 1; 전체 행동 범위 검증 미완료 |
| `maxorphantx` | default=100; removedIn='v30.0' | 동명 Core 정수 옵션 | 30 help에서 무효 옵션 거부,31 제거. 기존 버전만; 지원 축소 아님. |
| `rest` | default=false | boolean→0/1 | M: default0; optional public-chain REST on existing loopback Core RPC listener. Actual on/off HTTP tested; no wallet-gateway forwarding route. electrs0.11.1 does not require REST. |
| `rpcworkqueue` | default=128; min=1 | 동명 Core 정수 옵션 | M: implemented through versioned resource catalog, input validation, preview, real Core preflight, atomic save and coordinated Core/electrs restart. Core defaults retained; accepted bounds and units shown. Actual startup log evidence distinguished from RPC. |
| `ipc` | default=false; introducedIn='v30.2' | config 제외, bitcoin -m node -ipcbind=unix 실행 | 채굴 IPC는 제품 범위 밖; 가짜 토글 없음. |
| `version` | default=LATEST | config에 쓰지 않고 선택 binary/manager 전환 | V: 검증한22~31.1; version/network별 독립 경로, 미검증 기존 데이터 재사용 거부. 선택/재부팅 증거 별도. |
| `chain` | default='main' | chain 및 [chain] stanza, 앱 env 포트 | V/초기등록: release.networks 제한, RPC/P2P/cookie/electrs network 함께 전환. testnet4는 지원 버전만. |

## 연결과 적용 경계

| 경로 | JustVerify 생성 설정 / 주소·프로토콜 | 검토 결과·근거 |
|---|---|---|
| Core RPC | 각 chain 기본 RPC 포트, 127.0.0.1 bind/allow, cookie | profile_helper.py. 외부 사용자가 Core cookie를 받지 않음 |
| LAN 앱 RPC | HTTPS /rpc 또는 할당 wallet 경로, 기기 TLS, 개별 Basic 자격증명 | web/rpc_gateway.py, wallet_gateway.py. 읽기/공개 descriptor/PSBT·broadcast 권한 분리; 임의 관리·개인키 RPC 거부 |
| onion 앱 RPC | 별도 RPC onion:8332 → 127.0.0.1:28443 | Tor 내부 HTTP + 클라이언트별 인증, 기본 listener 비활성, 관리 웹 경로 없음. C/O 재인증·review 후 활성화 |
| P2P onion | 별도 P2P onion:8333 → 선택 chain loopback P2P+1 포트 | incoming=tor일 때만 tagged backend를 열며 해제 시 backend를 닫음. 고정 onion identity는 보존; Electrum/RPC onion과 독립 |
| electrs backend | 선택 chain cookie/RPC/P2P, chain/version별 index 디렉터리 | 0.11.1: prune 금지, txindex 불필요, P2P 블록 취득. 최신 HEAD REST 요구와 다름 |
| LAN Electrum | justverify.local:50002, raw Electrum over TLS → 127.0.0.1:50001 | HTTPS가 아님. web/electrum_tls.py의 기기 cert, 사설 IPv4 제한. IPv6 LAN 제공은 미구현 |
| Tor Electrum | 별도 Electrum onion:50001, TCP over Tor → loopback50001 | QR은 plain host:port. TLS=false, 휴대폰에서 Tor SOCKS 필요. 자동 앱 import/camera 미검증 |
| RPC QR | btcrpc URI, 생성한 client id/secret, 선택 연결 경로 | Fully Noded 공식 소스 별도 고정 commit에 근거. 민감 QR 명시적 화면에서만 표시; 실제 앱 검증 미완료 |
| sync READY | Core IBD=false + Core/electrs 높이 + header double-SHA256 tip 일치 | 기존 높이만 비교하던 오류를 src/lib.rs에서 수정. 전체 sync 비율만으로 완료 판정 금지 |

Umbrel config.ts saves settings JSON, atomically writes generated conf and restarts its manager. JustVerify uses reviewed diffs, private selected-binary preflight, an atomic journal and coordinated Core/electrs/TLS restart with health checks. Resources and indexes now use this same path. Umbrel router-forwarding assumptions are not a host-native security boundary; incoming binds are controlled directly.

현재 제품은 Core의 자동 Tor HS 대신 별도 Tor identities를 사용한다. Tor P2P incoming, Tor 목적지 outbound, Clearnet 목적지의 Tor 경유는 서로 다른 기능이다. outgoing 선택·Clearnet Tor 경유는 별도 설정과 실제 P2P/TCP 시험으로 검증했다. incoming 선택 UI와 Core 프로세스 소켓 검증을 추가했으며 통합시험 중이다. I2P router는 미구현으로 유지하며 허위 토글을 추가하지 않는다.

## 확인된 기본값 차이와 선택 근거

Core31.1 defaults differ from Umbrel: maxsendbuffer1000 vs5000 kB, dbcache1024 vs450 MiB, rpcworkqueue64 vs128, and Core indexes/filter serving default off. JustVerify preserves per-version Core defaults while now exposing these controls through M. Effective limits, source-derived units and explicit product guards are in resources-<version>.json.

Outgoing 선택과 proxy는 M 편집기에서 제공한다. 32개 서명 검증 바이너리 각각3모드, 총96개 실제 preflight/getnetworkinfo/저장 왕복 PASS: [matrix](evidence/outgoing-preflight-matrix.log). 비권한 PTY review/cancel/apply와 실제 systemd Core/electrs/TLS 재시작을 시험했고 선택 proxy1의 실제 VM 재부팅 유지도 PASS. Clearnet 목적지를 Tor로 전송하는 기능은 [실제 P2P+TCP 경로](evidence/tor-clearnet-audit.log)로 별도 확인했다.

Tor P2P 주소의 외부 포트8333은 그대로 유지하고 내부 target을 선택 chain P2P+1의 `=onion` listener로 수정했다. 기존 일반 P2P listener로 전달하면 Core가 Tor incoming을 IPv4로 집계했다. regtest에는 loopback P2P와 tagged onion bind를 명시하며, 공개 chain은 Core 기본 tagged onion listener를 사용한다. [실제 incoming 분류](evidence/incoming-onion-profile-audit.log) PASS. incoming 허용/거부 선택 UI와 실제 bind 검사를 추가했으며 아래 기록으로 검증 상태를 추적한다.

Incoming validation: all four modes across32 verified Core binaries PASS128 actual startup/listener/file-roundtrip cases ([matrix](evidence/incoming-preflight-matrix.log)). Registered Linux Core31.1/electrs0.11.1 actual LAN/loopback/onion listeners, RPC isolation, indexed tip and nonroot PTY review/cancel/apply PASS ([integration](evidence/incoming-profile-audit.log)). Occupied onion port causes rejected startup, configuration rollback and service recovery PASS ([recovery](evidence/incoming-rollback-audit.log)). Selected Tor-only incoming and proxy1 persist through actual VM reboot ([reboot](evidence/incoming-reboot-audit.log)). This does not substitute physical Pi or separate-LAN/mobile tests.

Current resource/index evidence: [32-release resources](evidence/resource-preflight-matrix.log), [64 auxiliary starts](evidence/auxiliary-preflight-matrix.log), [actual resource/TUI services](evidence/resource-profile-audit.log), [actual index/filter/REST/ASMAP services](evidence/auxiliary-profile-audit.log). Private-broadcast anonymity, complete policy behavioral semantics, physical/mobile gates and final release validation remain incomplete.

## 실제 앱 배포 설정 추가 대조

[umbrel-apps 7345dcb4c01264fb63fa50c37fec888130c7e070](https://github.com/getumbrel/umbrel-apps/tree/7345dcb4c01264fb63fa50c37fec888130c7e070)의 bitcoin/exports.sh, bitcoin/docker-compose.yml, electrs/docker-compose.yml을 직접 확인했다. 해당 tree에 최상위 LICENSE는 없으며 코드를 복사하지 않았다. 앞선 개발용 compose 예제와 실제 설치 설정을 구분한다.

| 배포 경로 | Umbrel 실제 설정 | JustVerify 및 검증 |
|---|---|---|
| RPC 인증 | exports.sh가 rpcauth.py로 무작위 암호를 생성해 앱 .env에 보존(기존 제공 값은 이전 가능); config.ts에서 salt/HMAC rpcauth 생성 | Core loopback cookie; 별도 클라이언트 인증 HTTPS 제한 API. Umbrel 앱 로그인용 기기 seed 암호와 Core RPC 암호는 서로 다른 경로다. |
| RPC 접근 | Core container IP 및 loopback bind, APPS_SUBNET /16+127.0.0.1 allow, compose8332 publish | 외부 raw RPC 차단, HTTPS node/watch/transaction 명시 권한과 취소. REST는 내부 Core 전용. |
| P2P | 네트워크와 무관하게8333, tagged onion8334, 외부 비공개 whitebind8335 | Core 네트워크 표준 P2P 포트, onion+1, 전용 electrs backend+2. backend는127.0.0.1만, LAN/onion/QR에 광고하지 않는다. |
| electrs download | ELECTRS_DAEMON_P2P_ADDR가 whitebind 포트 우선; cookie용 Core 데이터 read-only mount; 별도 DB | profile_helper가 download,noban 두 권한만 있는 loopback whitebind와 electrs endpoint를 함께 생성. forcerelay/mempool 권한 없음. |
| 업로드 한도와 과거 블록 | 신뢰한 내부 연결로 역사 블록 제한 회피 | 기존 일반 P2P 연결에서 실제 인덱싱 실패를 재현 후 전용 backend로 수정. maxuploadtarget 값 자체는 유지. 과거 블록 생성→일반 연결 거부→동일 체인의 새 electrs 인덱스 완료→tip 일치 시험. |
| 외부 Electrum | electrs TCP0.0.0.0 publish + 별도 Tor | 내부50001, LAN TLS50002, onion50001. QR에 실제 전송 프로토콜 반영, 내부 backend 포트와 구별. |

근거: [Core31.1 net_processing.cpp](https://github.com/bitcoin/bitcoin/blob/9be056a8a72b624dae9623b2f7bded92c2a21c91/src/net_processing.cpp)의 historical block upload target 검사와 Download permission 예외. NoBan은 eviction 보호이며 inbound 슬롯을 독점 예약하지 않는다. 독립 구현이며 Umbrel whitebind의 암묵적 전체 권한을 그대로 복제하지 않았다. 이전 backend 메타데이터 없는 프로필에서는 유한 업로드 한도 적용을 거부한다.

### JustVerify 주소·포트 계약

| Core 네트워크 | 내부 raw RPC(127.0.0.1) | 일반 P2P | tagged onion backend(127.0.0.1) | electrs download backend(127.0.0.1) |
|---|---:|---:|---:|---:|
| main |8332|8333|8334|8335|
| test(testnet3, 지원 버전만) |18332|18333|18334|18335|
| testnet4(지원 버전만) |48332|48333|48334|48335|
| signet |38332|38333|38334|38335|
| regtest(격리 기본) |18443|18444|18445|18446|

일반 P2P 외부 bind는 incoming 선택으로 제어하며 regtest 기본은 loopback이다. 네트워크별 backend 변경과 Tor 전달 대상 변경은 profile_helper 한 경로에서 생성한다. 외부 P2P onion 포트는 모든 네트워크에서8333이고 선택 네트워크의 tagged backend로 전달한다.

외부 지갑 주소는 위 raw RPC/backend 표와 다르다. LAN RPC는 `https://justverify.local/rpc`(443, 개별 인증)이며 Fully Noded의 루트 JSON-RPC 경로도 같은 제한 게이트웨이다. RPC onion8332는 검토 후 활성화한 내부28443 RPC 전용 게이트웨이로 전달한다. Quick Connect는 `btcrpc://<개별ID>:<개별암호>@<RPC-onion>:8332?label=...`이며 실제 비밀정보는 문서/로그에 넣지 않는다. LAN Electrum QR는 `justverify.local:50002`와 SSL/TLS 선택 안내·기기 인증서 지문, onion Electrum QR는 `<Electrum-onion>:50001`과 지갑 단말의 Tor 경유 안내를 제공한다. 일반 host:port QR의 모든 앱 자동 가져오기를 주장하지 않는다. 실제 PTY QR 셀/해독·TLS 연결은 PASS이고 실제 휴대폰 앱/카메라는 BLOCKED다.
