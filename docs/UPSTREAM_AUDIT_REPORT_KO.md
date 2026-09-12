# JustVerify 공식 소스 대조 및 실행 검증

전체 배포 후보 완료 판정은 **미완료**다. 실제 Pi·휴대폰 시험과 남은 릴리스 기준을 통과했다고 주장하지 않는다. 아래는 실제 실행한 소프트웨어 감사 결과다.

## 변경과 출처

- Core/electrs 높이가 같아도 다른 tip이면 READY가 되던 문제를 수정했다. 현재는 IBD=false, 높이, Electrum 헤더의 double-SHA256 해시를 모두 확인한다.
- outgoing 네트워크 선택과 Clearnet의 Tor 경유를 구현했다. Core22의 onlynet/onion 우선순위 차이를 실제 실행으로 발견해 수정했다.
- incoming 선택을 실제 바인딩으로 적용한다. Tor P2P는 별도의 `=onion` 리스너로 전달해 IPv4로 잘못 집계되던 문제를 수정했다. 적용 후 Core 프로세스 소유 소켓을 검사하며, 불완전한 기동은 롤백한다.
- Core만 반복 재시작해 electrs가 실패 한도에 걸리던 문제를 수정했다. Core·electrs·TLS를 순서대로 재시작하고 Core의 인증된 RPC 준비 상태를 확인한다.
- 자원 설정 9개와 인덱스·피어 필터·REST·ASMAP을 버전별 카탈로그에 추가했다. 기본값과 단위를 명시하고, 로그 근거와 실제 RPC 적용값을 구분한다.
- 유한 업로드 한도가 과거 블록 인덱싱을 막는 결함을 실제로 재현하고, download/noban 권한만 있는 전용 loopback electrs backend로 수정했다. 외부 LAN/Tor 피어에 이 권한을 주지 않는다.
- Core31의 cluster 기본값에 최대값 설명이 함께 표시되던 카탈로그 문제를 수정했다. 기본값64·최대64를 구분하고 실제 정책 API에도 검사한다.
- 공식 소스의 실제 설정 필드 34개를 [설정 대응표](UMBREL_PARITY.md)에 연결했다. [필드 누락 검사](evidence/umbrel-table-coverage.json)도 남겼다.

| 구성 | 검토 버전·commit |
|---|---|
| umbrel-bitcoin | `2fe07948f99e101dbee95ce34e5947a69c441ee4` |
| Umbrel | `bfa79ed24031b0065dd2f810411d58b82af1b95e` |
| 제품 electrs | 0.11.1 / `35216c6d30148be8e6763d913d437330f431fc03` |
| 비교한 electrs 개발 HEAD | `da1860e623587647542c5ad31164626b8a3cb3ed` |
| 주 검증 Core | 31.1 / `9be056a8a72b624dae9623b2f7bded92c2a21c91` |
| 이번 이미지 애플리케이션 소스 | `9ec13c8` |

Umbrel 두 저장소의 PolyForm Noncommercial과 electrs의 MIT 라이선스를 확인했다. Umbrel 구현을 복사하지 않았다. 개발 HEAD의 REST 요구를 P2P 인덱싱을 사용하는 electrs0.11.1에 소급 적용하지 않았다. 버전·파일 해시는 [출처 증거](evidence/upstream-audit.json)에 있다.

추가 배포 소스: umbrel-apps commit `7345dcb4c01264fb63fa50c37fec888130c7e070`. 실제 exports/compose를 확인해 RPC 무작위 암호 생성과 내부 electrs P2P 경로를 구분했다.

## 실제 검증

| 검증 | 결과·범위 |
|---|---|
| outgoing 설정 | 서명·체크섬 검증한 Core32개 버전 ×3모드, 실제 기동/RPC/저장 PASS |
| incoming 설정 | 같은32개 버전 ×4모드 PASS; 실제 Linux API·TUI·소켓·electrs·롤백·재부팅 PASS |
| 자원 설정 | 32개 버전 PASS; 실제 업로드 바이트 한도, 연결 한도, ban 유지 시간, TUI와 서비스 재시작 PASS |
| 인덱스·필터·REST·ASMAP | 버전별 지원 범위에서32개 버전 ×켜기/끄기 PASS; 실제 인덱스 완료, 조회, 비트와 HTTP 동작 PASS |
| 과거 블록·업로드 한도 | 32개 Core 버전에서 일반 P2P의 실제 과거 블록 제공 거부를 재현하고, 동일 한도에서 전용 backend의 새 electrs 인덱싱65블록·tip 일치 PASS |
| RPC와 지갑 권한 | Core22.0·31.1의 실제 HTTPS 게이트웨이37개 공개 메서드 PASS; 익명·권한 외·폐기된 인증 거부 포함 |
| Core RPC 목록 | Core31.1의151개 help 조사. 모든151개 메서드의 동작을 실행했다는 뜻은 아님. 상세 미검증 목록은 [RPC 감사](RPC_AUDIT.md)에 기록 |
| 공개 testnet4 | 실제 IBD 완료, Core/electrs 높이·tip 일치, 최근 블록 시간, 독립된 tip 조회 PASS |
| 재부팅 | 등록된 가상 데이터 볼륨의 실제 VM 재부팅 후 설정·기기 식별·Core/electrs·RPC 연결 유지 PASS |

Core31.0의 privatebroadcast IP 유출 문제는 [공식31.1 릴리스 노트](https://bitcoincore.org/en/releases/31.1/)와 대조했다.31.0에서 이 기능을 켜는 것은 거부하며,31.1의 공개 네트워크 설정 기동은 격리 시험을 통과했다. 이 시험으로 실제 privatebroadcast의 익명성을 검증했다고 주장하지 않는다.

## 거래와 동기화 증거

| 네트워크 | txid | 관측 결과 |
|---|---|---|
| 격리 regtest | `c5bf0538cb2bd11e154e1ebca657ebae8cb743d83417c480271bc55a4d41b243` | 실제 생성·자금 배정·서명·Electrum 브로드캐스트·mempool·채굴·지갑0→1→3회 확인 PASS. 높이104에서 Core 인덱스와 electrs tip 일치. 재시작 후 confirmed spent-output 조회와 블록 필터 유지 |
| 공개 testnet4 | `50fae20278c3230093255e222d7a30e10d20fc77f68f6e07fcd7d91890ac7578` | 블록151996 포함, 마지막 관측6회 확인. Core 지갑·독립 조회·electrs history 일치. Electrum Merkle proof를 Core 블록 헤더와 대조해 PASS |
| 공개 testnet4 자금 출처 | `ef9a651a6999b844ae42c6c692e7bd4486506db9adada696f69e0200e7edd77e` | 별도 생성한 테스트 지갑에 faucet 테스트 자금을 받아 사용. mainnet·실제 자금 사용 없음 |

공개 testnet4에서는 한때 같은 누적 작업량의 분기 때문에 독립 조회의 tip이 달랐다. 분기를 강제로 무효화하지 않았으며 다음 블록에서 정상 수렴한 과정을 남겼다. Core가 허용하는 미래 블록 시각도 실제 시간 차와 함께 기록했다. 과거 미확인 상태를 확인된 것으로 소급 표시하지 않는다.

- [공개 동기화·거래·Merkle 증거](evidence/public-testnet4-audit.json)
- [분기 관측 기록](evidence/testnet4-fork-observation.json)
- [서명 거래·인덱스·재시작 증거](evidence/signed-chain-index-restart-audit.json)
- [전체 요구사항과 명령·증거 연결](ACCEPTANCE.md)

## 설치 이미지와 남은 기준

최종 개발 이미지 **dev12**: 이미지 조립 `a87289a`, 동일 Rust 코드·Cargo.lock을 확인해 재사용한 바이너리 빌드 `11c8419`, 관측 `770b8e8`. SHA256 `902975da8186fb27f278eee46236e0ccb70e64c939a4a1c59dba7228551c2c46`. 읽기 전용 검사·실제 최초 설치·재부팅 후 Core/electrs/Tor RPC·TUI·QR·정책 기본값64 확인 **PASS**. [설치](INSTALL.md), [복구](RECOVERY.md), [부팅 증거](evidence/image-dev12-data-probe.json).


새 dev10 이미지는 빌드와 읽기 전용 검증을 통과했다. SHA256은 `621c6bfaed51b373147fa1aa86b777a99afc9035ad057f3b34bdaa32cc642fe9`다. 실제 첫 부팅은 통과했으나 두 번째 부팅의 Tor SOCKS 연결 시간 초과로 전체 이미지 시험은 FAIL이다. bootstrap 준비 상태를 별도 확인한 dev10b 시험도100% 이후 회선 시간 초과로 실패했다. 과거 블록 backend 수정은 dev11에 반영했고, dev11은 읽기 전용 검사 및 실제 최초 설치·두 번 부팅을 통과했다. dev11 SHA256은 `160b202f895b10f15aa9e9ca33bead39b950f813c1ed3cfdffff2fcc8f168f74`, 앱 빌드 소스는 `11c8419`, 관측 코드는 `c9b05e9`다. 인증된 실제 Tor RPC도 양쪽 부팅에서 통과했으며 이전 실패 기록을 지우지 않았다.

실물 Pi5의 EEPROM·저장장치 부팅, 실제 휴대폰 앱과 카메라 QR, 별도 LAN에서의 인증서 신뢰 흐름, 대상 Pi의24시간 시험은 남아 있다. 백업/복구 WIP, 원자적 시스템 업데이트, 정책 전체의 의미·행동 검증, 새 환경 재현 빌드와 신뢰할 릴리스 서명도 전체 RC 기준에서 미완료다. 기존 백업 작업 파일과 사용자 변경은 보존했으며 이번 이미지에는 미검증 백업 구현을 넣지 않았다.

장비 쪽 최소 필요 조건은 접근 가능한 Pi5와 삭제 허용 범위가 식별된 시험 저장장치, 실제 Fully Noded/Nunchuk 휴대폰과 별도 LAN·카메라 시험 경로다. Linux VM·sudo·실제 Core/electrs·공개 테스트 자금은 직접 확보해 검증에 사용했으므로 현재 해당 권한이나 testnet 자금 요청은 없다. 프로젝트 릴리스의 신뢰할 서명은 아직 제공하지 않았으며 개발용 자체 서명을 신뢰한 릴리스 서명으로 대체하지 않는다. 소프트웨어 쪽 미완료 항목은 장비 문제와 별도로 위에 기록했다.

추가 릴리스 준비로 Rust 외부 의존성326개 중323개 패키지의 라이선스 원문을 수집했다. `docs/evidence/rust-license-inventory.json`에 정확한 버전·표현식·파일 해시·가능한 경우 registry VCS commit 기반 URL을 연결했다. 나머지3개 및 OS/Python/native 소스 제공·고지 의무는 미완료이며, 전체 법적 배포 검토 완료라는 뜻은 아니다.
