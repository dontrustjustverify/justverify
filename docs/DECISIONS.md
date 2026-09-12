# 설계 결정

## 2026-09-12 설정 계층·favicon·채굴 풀·이미지 축소

최신 사용자 요청에 따라 일반 설정 아래 백업 및 복원/문제 해결을 두고 저장장치 관리는 접힌 고급 기능으로 유지한다. RPC 수집 오류만 보는 진단을 Core RPC 상태로 정확히 명명한다. 독립 작성한 Amber BTC 돋보기 favicon을 로컬 제공한다. 채굴 풀은 MIT 고정 데이터와 로컬 coinbase로만 추정하며 충돌/미식별/조회 실패를 구분한다. 이미지의 미사용 Qt/upstream 시험 바이너리와 다운로드 캐시를 제외하고 빈 ext4 공간을 정리한다. 원본/개발 테스트/운영 데이터는 보존한다. 세부 근거·출처·제약은 MINER_AND_IMAGE_DEV16.md.

## 제품 Tor RPC와 Fully Noded Quick Connect

- Tor는 P2P, Electrum, RPC에 서로 다른 v3 onion identity를 사용한다. RPC onion의 외부 8332는 `127.0.0.1:28443`의 제한된 gateway에만 연결하며 Core cookie·관리자 API·TUI·정적 파일을 노출하지 않는다. onion 주소는 항상 생성하되 listener는 소유자가 명시적으로 켜기 전까지 닫혀 있다.
- 비권한 TUI와 웹 프로세스는 owner-only 0700 상태 디렉터리의 0600 Unix socket으로 설정 상태·미리보기·적용을 전달한다. Linux `SO_PEERCRED` UID가 서버 UID와 일치해야 하고 적용 시 관리자 암호를 다시 확인한다. 암호는 stdin과 요청 메모리에만 있으며 argv·설정·로그에 넣지 않는다.
- Fully Noded commit `d0d1502eef2840c0457aa321b88cf606ee8b4650`의 `Docs/Quick-Connect-QR.md`와 `QuickConnect.swift`를 근거로 `btcrpc://user:password@host.onion:8332?label=...`을 생성한다. 새 클라이언트 암호는 앱 호환을 위해 192-bit hex로 발급한다. 민감 QR은 클라이언트 발급 직후 Q를 다시 눌러야만 보이며 Esc로 돌아가면 재표시할 수 없도록 기존 일회성 화면 수명을 따른다. 제3자 코드는 복사하지 않았다.

## 원격 RPC 설정의 저장 및 적용

- HTTPS 소유자 세션/Origin/CSRF 검증 후 `/remote-rpc`에서 상태와 미리보기를 제공한다. 적용은 관리자 암호를 다시 확인하고,120초 일회성 검토 토큰과 이전 파일 digest를 대조한다. 암호는 설정에 저장하지 않는다.
- `remote-rpc.json`은 private state 안에 원자적으로 저장한다. `applying`→listener 시작/정지→`committed` 순서이며 미완료 상태를 읽은 새 서버는 포트를 열지 않는다. 적용 실패 시 현재 listener를 닫고 HTTPS 관리 경로에서 재검토할 수 있게 한다. 마지막 committed enable만 자동 복원한다.
- TUI C/O와 private IPC, 제품 Tor RPC onion 매핑 및 실제 프로세스 재시작 복원을 연결했다. OS 재부팅과 새 설치 이미지 검증은 뒤이어 수행한다. 개발용 `--tor-rpc` 시험 모드는 별도다.

## Tor RPC 전송 경계 — 기본 비활성

- `server.py --tor-rpc`는 개발용으로 고정 loopback28443에 RPC 전용 listener를 추가한다. 별도 앱에는 POST `/`, `/rpc`, `/wallet/<name>`만 있으며 관리자 등록/로그인/설정/터미널/정적 파일 경로를 넣지 않는다. 일반 HTTPS 앱의 동일 Gateway 객체를 재사용하므로 클라이언트 인증·분당 호출 제한·동시 요청 제한·폐기 상태가 공유된다.
- Tor onion→loopback 서비스 매핑은 [Tor 공식 구성 안내](https://community.torproject.org/onion-services/setup/)를 근거로 한다. 이번 실제 시험은 격리된 Tor 인스턴스의8332→127.0.0.1:28443 경로를 사용했다. Core RPC로 직접 전달하거나 HTTP listener를 LAN에 바인딩하지 않는다. Tor 경유만으로 무제한 RPC를 허용하지 않는다.
- 기본 CLI와 배포 unit에서는 아직 꺼져 있다. 제품의 소유자 검토/활성화·비활성화 UI와 재부팅 상태 저장을 연결하기 전에는 기본 외부 RPC를 켜지 않는다. 실제 onion 전송 시험 성공은 그 사용자 흐름 완료나 모바일 앱 인증서/가져오기 호환을 의미하지 않는다.

## LAN Electrum TLS 서비스

- electrs는 계속 `127.0.0.1:50001`에서만 받는다. 별도 비권한 TLS 중계가 `0.0.0.0:50002`에서 기존 기기 인증서를 사용한다. 관리 HTTP/RPC를 이 포트로 전달하지 않으며, upstream은 고정 localhost Electrum뿐이다. 요청 내용은 기록하지 않는다.
- Python 출발 주소 검사와 systemd IPAddressAllow/Deny를 함께 사용해 loopback/RFC1918/IPv4 링크 로컬만 허용한다. IPv6는 아직 제공하지 않는다. 최대32 연결,64KiB 스트림 버퍼,5초 연결/handshake,15초 drain,600초 idle 제한을 둔다. 인터넷 직접 공개 서비스로 설명하지 않는다.
- 등록 마커와 실제 마운트/프로필 검증 후 시작한다. electrs의 WantedBy/PartOf로 생명주기를 연결하되, 명시적 버전 전환은 TLS도 stop/reset-failed/start 완료를 기다린다. 자동 장애 재시작 제한은 유지한다. 연속 전환에서 발견한 start-limit 및 비동기 시작 문제를 이 경로에서 수정했다.
- Q/L은 일반 LAN host:port QR, SSL 선택 안내와 공개 인증서 지문을 표시한다. Q/T는 기존 Tor 경로다. 앱 자동 가져오기나 자체서명 인증서의 앱 호환성을 추정하지 않는다. 실제 휴대폰 시험은 별도다.

## 모바일 지갑의 UTXO 잠금 경계

- 고정 FullyNoded 소스의 UTXO 잠금/해제 화면에서 실제 `listlockunspent`·`lockunspent` 호출을 확인했다. 전자는 watch-only 조회에, 후자는 명시적으로 부여한 거래 준비 권한에 포함한다. 기존 node-read나 watch-only 조회 권한만으로 잠금을 변경하지 못한다.
- 잠금 변경은 외부 지갑 이름과 무관하게 배정된 지갑 경로로 전달한다. Core 22~31.1 공통 인수 `unlock`, `transactions`만 허용한다. bool·outpoint 전체를 먼저 검증하며, 영구 잠금 옵션이나 재부팅 후 유지 보장은 제공하지 않는다. 개인키·서명 경계는 변하지 않는다.
- 실제 TLS/Core 32버전 시험에서 모든 사용 가능 코인 잠금→자금 선택 불가→일부 해제→자금 선택 성공, 동일 주소를 관찰하는 다른 지갑과의 격리, 잘못된 입력의 상태 보존을 확인했다. 앱 설치본 호환성은 여전히 별도 검증이다.

## 설치 직후 마운트 UUID 조회 수정

- dev6 실제 이미지 사용자 공간 시험에서 저장장치 커밋 후 `findmnt UUID`가 비어 프로필 준비가 실패했다. 마운트 source가 종료된 mount 프로세스의 `/proc/self/fd/6`였으며, UUID 기반 fstab으로 재부팅하면 준비가 성공했다. 재부팅을 요구하는 우회로 완료 처리하지 않는다.
- 포맷과 서명 검증은 기존 잠긴 파일 디스크립터를 유지한다. 마운트 source만 `/dev/block/<major>:<minor>`로 기록하고, 열린 장치의 번호와 source의 block-device 번호를 마운트 직전에 비교한다. 마운트 후 대상 파일시스템의 장치 번호 검증도 유지한다. 디스크 이름 순서에 의존하지 않는다.
- 새 파일로 만든 실제 ext4 루프 장치에서 디스크립터를 닫은 직후 root와 비권한 justverify의 UUID 조회를 검증했다. 기존 디스크는 포맷하지 않는다. dev6 배포 파일은 변경하지 않으며 수정된 설치 이미지는 새 버전으로 빌드한다.

2026-09-12 — 원본 세 문서를 보존하고 새 Git 저장소를 구성했다.

- 기본안 Rust/Ratatui, 비권한 수집 데몬 + Unix socket, systemd, 브라우저 고정 TUI를 채택한다.
- 개발 데이터는 프로젝트 `.state/`, 다운로드는 `.cache/`로 격리하고 Git에서 제외한다. 기존 Bitcoin 데이터 경로는 사용하지 않는다.
- 최초 검증은 macOS arm64의 실제 Core regtest, 이후 QEMU ARM Linux VM에서 systemd와 이미지 빌드를 검증한다. Pi 5와 VM 검증은 별개다.
- 공식 다운로드 페이지에서 31.1을 확인했다. 전체 릴리스 목록은 공식 배포 디렉터리로 수집하고 누락 릴리스는 공식 태그와 대조한다. 미검증 조합을 지원으로 표시하지 않는다.
- Core 서명자 신뢰의 최초 근거는 공식 다운로드 안내에서 직접 예시로 제시한 fanquake 키 fingerprint E777299FC265DD04793070EB944D35F9AC3DB76A다. 키 파일은 고정 guix.sigs commit에서 받는다. 서명 및 파일 SHA256 모두 일치해야 압축을 해제한다.
- 데이터 재사용은 조합별 증거가 있어야 허용한다. 기본 전환은 network/version별 독립 데이터 및 electrs 인덱스 경로다.
- 실기 접근 정보가 현재 없으므로 Pi 부팅/카메라/24시간 시험은 BLOCKED로 유지한다. 그 외 개발은 계속한다.

서명 검증 첫 시도: 31.1의 SHA256SUMS.asc에는 fanquake 서명이 없고 Ava Chow 서명만 있어 실행을 차단했다. 공식 https://bitcoincore.org/en/contact/ 에서 Ava Chow fingerprint 152812300785C96444D3334D17565732E08E5E41를 독립 확인하고 고정 키 목록에 추가했다. 임의의 다운로드 동봉 키를 신뢰하거나 서명 실패를 무시한 것이 아니다. 최초 실패 로그는 evidence/core-signature-initial.log에 보존한다.

VM 개발 기반은 Debian 13 genericcloud arm64 20260831-2587 (공식 SHA512 고정), Pi 제품 기반과 구분한다. electrs 공식 tags/API 조회 결과 최신 published tag는 v0.11.1이며 문서에 언급된 0.12는 현재 조회와 차이가 있다. 실제 고정 소스와 호환시험을 근거로 선택한다.

브라우저 브리지는 Python aiohttp + stdlib PTY로 구현한다. 관리 수집과 실제 TUI는 Rust로 유지하고, TLS/인증/프로세스 수명만 작은 별도 서비스로 격리한다. 런타임 CDN 없이 xterm 6.0.0을 integrity 고정하여 포함했다. 세션은 서버 메모리에만 저장하고 1시간 만료, secure/HttpOnly/SameSite 쿠키, exact Origin, 로그아웃 CSRF, 로그인 제한, 최대 4개 PTY를 적용한다. first-setup token은 기기별 생성 파일로만 보관한다. 최종 headless 소유권 전달 및 브라우저 신뢰 UX는 추가 구현·검증 대상이다.

과거 릴리스 서명 범위: 공식 배포의 SHA256SUMS.asc는 릴리스마다 다른 Guix 재현 빌더 서명을 제공한다. fanquake/Ava만으로 34개를 검증할 수 없다. 공식 다운로드 안내가 연결한 guix.sigs의 동일 고정 commit에서 등록 빌더 공개키 목록을 검토하여 배포 검증의 신뢰 집합으로 고정했다 (`catalog/trusted-builders.json`: 이름, primary fingerprint, key-file SHA256, 고정 원본 URL). 최소 한 등록 빌더의 유효한 서명을 요구한다. BADSIG/EXPSIG/EXPKEYSIG/REVKEYSIG는 거부한다. 0xb10c 키는 b10c.me 게시 fingerprint, guggero는 GitHub 프로필이 연결한 Keybase 공개키와 추가 대조했다. 키 집합 변경은 manifest 검토가 필요하며 서명 파일이 가져온 미등록 키를 자동 신뢰하지 않는다.

구버전 압축에는 정상 libbitcoinconsensus 상대 symlink가 포함된다. 모든 링크를 거부한 초기 구현을 Python 3.13 tarfile data filter로 변경하여 압축 밖으로 나가는 링크/경로는 거부하고 정상 내부 링크만 허용한다.

거래 통합시험 수정: OP_TRUE를 직접 출력으로 사용하는 거래는 표준성 정책에서 거부됐다. 표준 P2WSH(OP_TRUE) 시험 출력 및 witness를 사용하고, 반복 regtest의 반감기에 맞춰 실제 coinbase 금액에서 수수료를 뺀다. electrs 0.11.1이 제공하지 않는 get_mempool 대신 공식 구현의 get_history에서 height<=0을 검증한다. 시험 기준(실제 mempool 거래 인식)은 유지한다.

멀티서명 검증 수정: 하나의 SHA256SUMS에 여러 독립 서명이 들어 있다. 모든 서명을 파싱한 뒤 각 NEWSIG 그룹을 따로 판정한다. 만료/폐기/오류 서명은 신뢰 증거에서 제외하고, GOODSIG와 VALIDSIG를 동시에 가진 현재 유효한 고정 신뢰 키가 최소 하나 있어야 한다. 다른 빌더의 만료 서명이 정상 빌더의 유효 서명까지 무효화한 초기 버그를 수정했다. BADSIG는 전체 차단한다. 만료 서명을 통과 처리하는 것은 아니다.

Core 30.0/30.1 공식 바이너리 부재는 네트워크 오류가 아니다. 공식 2026-01-05 공지 https://bitcoincore.org/en/2026/01/05/wallet-migration-bug/ 에서 wallet migration 데이터 삭제 버그 때문에 철회했음을 확인했다. 전체 목록에는 남기고 `UPSTREAM_WITHDRAWN`과 원인을 표시한다. 비공식 미러에서 가져와 지원 성공으로 바꾸지 않는다. 나머지 32개 ARM Linux 공식 바이너리는 실제 검증한다.

Core 30부터 natpmp 기본값이 켜져 있음을 릴리스 노트에서 확인했다. JustVerify 이미지의 기본값은 `natpmp=0`으로 명시하여 공유기 포트를 자동 개방하지 않는다. 첫 개발 이미지는 이 변경 전 artifact이므로 재빌드 필요.

## 2026-09-12 — 정책 변경 경계와 상시 네트워크 서비스

- 정책 API는 비권한 `justverify` 사용자 및 0700 Unix socket 디렉터리에서 동작한다. root 권한은 인자 없는 고정 Core 재시작 helper만 sudoers로 허용한다. API의 임의 경로/명령/추가 필드는 거부한다.
- 변경 내용은 실제 선택 Core를 별도 private staging data에서 먼저 시작하여 확인한다. 요청 revision, preview 내용, 실제 binary SHA256을 묶은 일회성 receipt로 저장/재시작을 제한한다. RPC 관측 가능한 값과 아직 행동시험이 없는 정책 효과를 구분한다.
- fsync/atomic rename journal로 중단 지점을 남긴다. 시작 실패 및 프로세스 강제 종료 복구는 동일 binary/network의 이전 설정만 복원하며 데이터 마이그레이션을 되돌리지 않는다. TUI에서 복구 내용을 확인한 뒤 적용한다.
- Core32개 verified ARM 실행파일 hash를 catalog에 기록하고 policy service 및 이미지 조립에서 실제 파일을 대조한다. electrs source archive/commit/Cargo.lock 및 현재 통합시험 binary hash는 `catalog/electrs.json`에 고정한다. 새 build는 별도 integration evidence 없이 tested hash를 교체하지 않는다.
- electrs는 data mount 아래 전용 index에 쓰고 자동 재인덱싱을 비활성화한다. 기본 Electrum 및 monitoring listener는 loopback이다. Tor는 별도 비권한 systemd 서비스로 실행하며 P2P/Electrum onion identity를 분리한다. 공개 hostname만 `/run/justverify-tor`로 복사하며 private key 디렉터리는 0700을 유지한다.
- 현재 네트워크 서비스 추가는 LAN TLS/앱 pairing, Tor-only 정책, firewall 및 모바일 검증의 완료를 뜻하지 않는다. 이 항목은 남은 제품 작업이다.

## 2026-09-12 — 실제 버전 전환 엔진

- `src/versions.rs`는 선택한 version/network의 Core data, electrs index, policy 파일을 분리한다. 다른 버전의 데이터 디렉터리를 재사용하거나 이동하지 않는다. 동일 버전으로 돌아오면 해당 버전의 기존 데이터를 재개한다. 신규 버전의 추가 디스크 사용 및 최초 동기화를 preview에 표시한다.
- binary hash는 공식 signature/checksum 검증 결과가 있는 catalog와 매번 대조한다. private preflight 후 selector revision/정책 revision을 묶고, 파일 lock 및 durable transition journal로 stop→selector 저장→Core/electrs 기동 순서를 관리한다.
- 실패 복구는 **이전 데이터에 다른 바이너리를 적용하는 rollback이 아니다.** target 데이터는 그대로 남기고 이전 바이너리가 이전 전용 경로를 다시 연다. target 바이너리가 유실된 경우에도 이전 검증 바이너리로 복구할 수 있다. active selector의 외부 변경은 거부한다.
- 기존 active data 디렉터리 유실을 새 빈 데이터 생성으로 대체하지 않는다. data root inode/device 변경도 감지하여 다른 파일시스템 경로로의 쓰기를 거부한다. 실제 제품 서비스의 mount guard는 별도로 계속 적용해야 한다.
- 버전 엔진은 현재 라이브러리와 실제 프로세스 통합시험까지 구현했다. 운영 TUI/API 및 systemd profile 전환은 다음 작업이며, 현재 VM 상시 profile이나 dev2 이미지의 버전을 바꾼 것이 아니다.
- 운영 연결은 비권한 서비스에서 preflight/data 관리를 수행하고, root helper는 검증된 version/network 식별자만 받아 고정 서비스의 profile을 변경하는 방향이다. 임의 명령·path를 privileged API 인자로 받지 않는다. 정책 변경과 버전 전환은 운영 coordinator에서 함께 직렬화해야 한다.
- electrs의 IBD 대기는 정상 동기화 상태다. 테스트에서 완전히 빈 regtest chain으로 full index readiness를 요구한 최초 조건은 실패했다. 빈 높이 0을 실제 확인한 뒤 블록을 생성하여 동기화된 fixture로 만들고, production과 같은 electrs 기본 대기 설정으로 전환/복구를 검증했다. 최종 코드에는 skip-block-download-wait 테스트 우회가 없다.

## 2026-09-12 — 운영 버전 API와 TUI 연결

- `version_service.rs`는 비권한 사용자로 실행하고 Unix socket에서 state/preview/apply/recover만 받는다. 일회성 preview는 5분 만료, 추가 request 필드 거부, fixed profile bridge를 통한 systemd 관리로 제한한다. 정책 apply/recover와 version apply/recover는 `/var/lib/justverify/config/operations.lock`을 공유하여 직렬화한다.
- root bridge `scripts/profile_helper.py`는 stdin의 action/version/network만 허용한다. 데이터 mount, trusted artifact hash, version/network/electrs 조합, marker 및 경로를 다시 확인한다. Core/electrs/collector/policy profile을 고정 위치에 쓰며 data 파일은 비권한 측이 먼저 준비해야 한다. root가 사용자 data 파일을 생성하지 않는다.
- systemd `ProtectSystem=strict`가 sudo 자식에도 상속되어 처음에는 /etc profile 저장이 거부되었다. version service에서 두 고정 root-owned 경로 `/etc/justverify`, `/etc/systemd/system`만 writable mount 예외로 둔다. 일반 파일 권한은 그대로 root-only이고 비권한 서비스가 직접 쓰는 권한을 얻는 것은 아니다. sudo는 인자 없는 fixed bridge만 허용한다.
- runtime security 옵션은 실제 version별 help 목록(`catalog/runtime-options.json`, help SHA256 포함)으로 결정한다. 존재하는 natpmp/upnp만 0으로 설정한다. 임의 major 지식으로 옵션 유무를 가정하지 않는다.
- 동일 network의 version 변경에서는 Tor를 재시작하지 않는다. 최초 시험에서 불필요한 Tor 반복 재시작이 start-rate limit을 소진했다. P2P target이 변경될 때만 Tor를 다시 적용하여 수정했고 identity는 유지한다.
- IBD 중 electrs의 정상 대기를 전체 인덱싱 완료로 표시하지 않는다. native version commit은 선택/프로세스 시작이 확인된 상태이며, collector의 index height/readiness가 별도 준비 상태다.
- TUI V는 major별 최신 patch, P 확장 patch 목록, N network, Enter preflight/review/apply, Esc 취소를 제공한다. 지원 상태와 artifact 다운로드 필요 여부를 표시한다. 현재 자동 다운로드 연결은 남아 있다.
- active selector가 없는 기존 설치를 운영 기본값으로 덮어 전환하지 않는다. 초기 등록이 필요하다는 오류를 반환한다. disposable VM 시험에서만 root configuration의 `allow_initial_selection=true`로 알려진 시험 프로필을 전환하고 원본 설정을 복원한다. 제품 onboarding에서 verified baseline selector를 등록하는 절차는 다음 구현 항목이다.

## 2026-09-12 — 공식 다운로드를 운영 버전 선택에 연결

- `src/download.rs`는 비권한 background worker로 고정 fetch script만 실행한다. API는 version 식별자만 받으며 URL·architecture·경로를 요청으로 받지 않는다. 1개 작업만 허용하고 state/download-status.json에 단계 상태를 저장한다. fetch에는 600초 상한을 둔다. 정상 서비스 재시작에서 미완료 단계는 interrupted로 표시하며 자동 성공이나 자동 재개로 처리하지 않는다.
- `fetch_core.py`는 기존 trusted builder fingerprint/key hash 및 공식 SHA256SUMS signature 검증을 유지하면서 cache/evidence 경로를 분리했다. keyring/cache는 fcntl lock으로 직렬화하여 이전 호출자의 child가 남더라도 두 writer가 동시에 쓰지 않는다. 실패한 서명 검증을 우회하지 않는다.
- root `install_core.py`는 검증 catalog에 존재하는 version 식별자만 받고, staging 경로의 모든 하위 component를 O_NOFOLLOW로 열어 regular file만 읽는다. unprivileged bytes는 root로 실행/추출하지 않는다. pinned executable SHA256을 다시 확인한 bytes만 fixed installation directory에 atomic 저장한다.
- service의 UMask=0077이 root helper의 mkdir에도 적용되어 최초 설치 디렉터리가700이 된 문제를 발견했다. 공개 실행파일의 root-owned 상위 디렉터리를 명시적으로755로 설정하여 비권한 Core 실행을 허용했다. 데이터·자격증명 디렉터리 권한을 넓힌 것이 아니다.
- state snapshot은 download phase를 먼저 읽고 설치 목록을 확인하여 complete와 설치 여부 표시 사이의 역전 가능성을 줄인다. TUI V에서 P 확장 목록, D 다운로드, 진행/완료 단계를 제공한다. 다운로드 자체는 active profile/services를 바꾸지 않는다.
- VM에 실제 설치한 GnuPG는2.4.7/libgcrypt1.11.0 (apt install evidence). 이미지에도 해당 검증 도구 및 helper/sudoers/data path 통합이 필요하며 현재 dev2에 포함되었다고 주장하지 않는다.

## 2026-09-12 — 소유권 전달 및 TLS 첫 신뢰

- 공통 secret/certificate를 이미지에 넣지 않는다. `prepare_owner.py`는 각 장치용 random 32-byte token 파일을 새로 만들며 덮어쓰기를 거부한다. 첫 부팅은 장치에서 TLS identity를 만들고 boot owner 파일을 private state로 소비/삭제한다. boot filesystem 삭제를 sync한 뒤 첫 부팅을 마친다.
- `/pairing-proof`는 초기 미등록 상태에서만 현재 인증서 DER hash에 대한 HMAC-SHA256 증명을 제공한다. key는 owner setup token이고 domain은 `JustVerify TLS pairing v1`이다. 자체 인증서를 받은 개발용 확인 도구는 실제 TLS peer DER와 owner 파일로 MAC를 검증하며, 그 전에는 어떤 인증 secret도 전송하지 않는다. 성공 후 반환된 인증서를 신뢰 경로에 설치하고 정상 검증 TLS로 소유권을 등록한다.
- 이 proof를 가져오는 연결 자체는 아직 신뢰되지 않았기 때문에 개발용 도구의 해당 연결에만 PKI 검증을 보류한다. 실제 peer certificate와 owner-keyed MAC를 검증하는 것이 첫 신뢰를 만드는 단계다. admin login에는 검증되지 않은 TLS를 쓰지 않는다. 다른 인증서로 proof를 재사용하는 MITM 시험을 거부한다.
- 소유권 등록 후 proof는404, setup token은 삭제한다. admin record는 파일 및 parent directory fsync 후 token을 삭제하고 다시 directory를 fsync하여 power-loss 저장 순서를 강화했다.
- TLS 생성 도중 key/certificate 일부만 남은 미등록 장치는 재생성하여 복구한다. 정상 pair는 재실행해도 유지한다. 이미 등록된 장치의 missing/mismatched identity는 묵시적으로 바꾸지 않고 명시적 복구를 요구한다.
- physical console은 stdin/stdout이 실제 tty일 때만 동작하며 Enter 후 setup code를 표시한다. systemd StandardOutput=tty로 journal에 secret을 보내지 않는다. 등록 후 fixed Rust TUI로 exec하며 shell로 복귀하지 않는다. 실제 Pi tty1 및 브라우저 신뢰 GUI 검증은 남아 있다.

## 2026-09-12 — 저장장치 선택 전 읽기 전용 분류

- `disk_inventory.py`는 실제 lsblk topology/UUID/serial/WWN/partition UUID/read-only/mountpoints를 읽어 review용 inventory를 만든다. 포맷·mount·fstab 쓰기는 하지 않는다.
- `/`, `/boot`의 backing device와 해당 파티션은 보호한다. 시스템이 있는 물리 디스크 전체 초기화는 막되, 같은 NVMe의 별도 데이터 파티션까지 일괄 금지하지 않는다. NVMe 직접 부팅에서 OS/data 분리를 지원하기 위해 파티션을 개별 검토 대상으로 유지한다.
- 기존 mount 및 nested mapper 사용, read-only 장치, duplicate filesystem UUID, 기존 partition table/미지원 filesystem은 별도 상태로 표시한다. 식별자가 없는 신규 장치는 자동 대상으로 삼지 않는다. 외부 장치 label의 control/bidi 문자를 제거한다.
- lsblk의 FSTYPE 없음은 빈 디스크 증거가 아니다. 신규 검토 상태도 root 권한의 별도 signature scan과 explicit confirmation이 필요하다고 표시한다. 이후 작업 전에 장치 identity 및 내용을 다시 확인해야 한다. inventory의 review_action은 변경 권한을 뜻하지 않는다.
- TUI S는 현재 이 읽기 전용 inventory를 표시한다. 선택/format/mount 및 최초 profile 등록은 아직 연결하지 않았다. 이 화면만으로 onboarding 완료라고 보고하지 않는다.

## 2026-09-12 — 変更 없는 signature/content review

- root `storage_probe.py`는 inventory의 name+identity digest를 다시 확인하고 read-only fd를 연다. 고정 wipefs --no-act 및 blkid -p 결과만 사용하며 scan 후에도 identity를 대조한다. 보호/사용 중인 장치는 provisioning review로 진입하지 않는다.
- signature 없음도 유용한 데이터가 없다는 증거가 아니므로 `NO_KNOWN_SIGNATURES_CONTENTS_NOT_PROVEN_EMPTY`로 표시한다. ext4 contents review는 ro,noload,nodev,nosuid,noexec으로 private 임시 경로에 mount하고, 열린 block fd와 mount의 device identity를 대조한다. 디렉터리 분류/개수만 반환하고 사용자 파일 이름·내용을 내보내지 않는다.
- 기존 파일이 있으면 보존 대상으로 분류한다. 이 helper는 format/attach/fstab 변경 권한을 제공하지 않는다. 실제 provisioning은 별도 명시적 plan/confirmation과 재검증이 필요하다.
- 전용 provisioning 시험매체 `.state/vm/provision-test.qcow2`(2GiB)를 새로 만들고 serial JUSTVERIFY_TEST_DATA로 VM에 연결했다. VM 정상 종료/재시작 후 기존 system/data/services는 복구했다. 장치 추가로 root의 kernel name이 vda에서 vdb로 바뀌었다. 이름에 의존하지 않는 inventory 분류는 계속 맞았고, 시험의 과거 hardcoded 장치 이름을 실제 mount 기반 검증으로 수정했다.

## Initial volume provisioning transaction

- New `scripts/volume_setup.py` is an internal provisioning engine; it is not yet exposed through a privileged API or TUI. A root-owned durable preview binds the stable hardware identity, original signature scan, destination, fstab content, filesystem UUID, and exact device erasure confirmation. Unrecognized contents are explicitly described as erased; absent known signatures never means proven empty.
- Formatting is attempted once. The journal records `formatting` before mkfs, then `formatted`, `mounted`, and `committed`. Recovery verifies the original uniquely identified device and planned ext4 UUID, runs read-only e2fsck when unmounted, and completes mount/ownership/fstab without invoking mkfs. An incomplete filesystem needs manual review; no automatic destructive retry or repair.
- Existing populated/mounted destinations and existing target fstab entries are rejected by initial setup. This is not a migration or existing-node adoption path. Production callers must authenticate the owner; API and first-profile integration remain pending.

## Authenticated storage API boundary

- `web/server.py` POST `/storage` requires the existing owner session, exact HTTPS Origin, and session CSRF token. Only inventory/preview/apply/recover with exact string field schemas are forwarded to `/run/justverify-storage/api.sock`. Transport failure is an uncertain result; callers retain the plan ID and recover instead of resubmitting format.
- `scripts/storage_service.py` is a root service with a fixed socket and no command-line arguments. Linux peer credentials must be root or justverify, and owner enrollment must exist. Requests cannot specify executable, mount destination, fstab path, or state directory. Public plans exclude saved host fstab content. The local justverify account remains trusted to operate the node; this is not a sandbox against arbitrary code already running as that account.
- Root journals now live in `/var/lib/justverify-storage` (root:root 0700), outside the justverify-owned `/var/lib/justverify` tree. Existing development-only fixture plans are not automatically migrated.
- The storage unit intentionally shares the host mount namespace. ProtectSystem/ProtectHome/ReadWritePaths would introduce a filesystem namespace and could hide mounts from Core/electrs; they are not used for this narrow mount service. NoNewPrivileges, AF_UNIX-only socket families and fixed request semantics remain. VM service and PID1 mount-namespace IDs were checked equal.

## TUI volume selection and recovery

- TUI S now uses the owner-gated Unix storage API instead of executing read-only inventory every draw. Enter on an eligible new device requests a persistent preview; a separate review requires typing the exact device erasure confirmation before apply. Protected/existing devices are preserved.
- A background request thread keeps the TUI responsive during formatting/recovery. Exiting the screen does not cancel the root transaction; the screen says so. Stored plan IDs and interrupted phases are returned through sanitized inventory metadata for recovery after process exit. R reviews the interrupted volume and Enter resumes UUID-bound recovery without reformatting.
- The engine refuses a new preview/apply while another interrupted volume exists. Root journal recovery takes precedence over formatting an alternate disk. Initial node profile registration is still required after volume completion.

## Dedicated initial-format UI test medium

- `.state/vm/provision-ui-test.qcow2` is a second project-owned disposable 2GiB disk, attached conditionally with serial JUSTVERIFY_UI_TEST. The earlier JUSTVERIFY_TEST_DATA disk remains intact for recovery evidence. Kernel names may shift with added devices and are never format selectors.
- `tests/linux_storage_tui_format.py` deliberately requires the dedicated serial, size, unmounted state, REVIEW_NEW and a fresh no-known-signature scan. The end-to-end TUI test is destructive only on that new medium; after success it refuses rerun against the resulting ext4 volume. Format through TUI does not waive first-profile or full-install acceptance gates.

## Initial profile eligibility without legacy-data bypass

- Production version API no longer merely refuses all first selections. When no active selection exists and the development-only `allow_initial_selection` override is false, preview and apply both invoke the fixed root helper action `check_initial`.
- This action performs no service stop/start or configuration write. It requires an enrolled owner record, mounted root-controlled volume and journal directory, root-controlled marker with the actual mounted filesystem UUID, matching committed provisioning journal with no interrupted transaction, expected volume layout and empty instances. Additional files or pre-existing instance data block initial registration. Legacy data must not be silently adopted by enabling the test override.
- This is the eligibility boundary only. Initial service activation/startup ordering, initial selection through the complete production flow and image boot remain separate work. The existing root helper's activate path still supplies the actual Core/electrs profile after version engine preparation.

## Core RPC readiness before electrs startup

- Actual first-profile integration exposed a cold-start race: systemd Type=simple marked Core started before its cookie existed, and electrs exited immediately opening the absent cookie. `After=justverify-core` alone is insufficient readiness.
- `scripts/wait_core_rpc.py` runs unprivileged as electrs ExecStartPre, waits up to 120s for authenticated loopback getblockchaininfo with the selected network, and emits no cookie/credential content. electrs is launched only after Core RPC is usable. The unit has a 150s startup timeout; IBD itself does not block the readiness helper.
- Index readiness is still distinct from RPC readiness. The initial regtest test mines one real block, then demands electrs header height 1 within a bounded deadline; it does not treat service active or Core IBD as indexed success.

## Registered-profile startup gate

- Core, electrs and policy units require `/etc/justverify/node-ready.json`, then execute unprivileged `node_ready.py` before their process starts. Manager/web stay available to show setup and errors.
- The fixed root activate helper writes the registration marker only after validated instance preparation and complete configuration writes. It binds mounted UUID, exact instance, binary SHA256 and hashes of bitcoin.conf/electrs.toml/profile.json. The startup guard compares these with current active selection, mounted filesystem and existing directories. Missing registration, wrong volume or incomplete config/selection update prevents startup; it never creates missing data.
- Firstboot no longer creates legacy core/electrs data directories merely because some filesystem is mounted. It creates only private application state directories. Volume and per-version data preparation remain explicit setup operations.
- This gate does not itself complete initial setup or automatically repair interrupted version transitions. Version recovery remains the dedicated journaled operation; auto availability of version service after storage setup and boot-time transition recovery ordering still need integration.

## Storage completion → version service preparation

- Production storage service invokes a fixed profile-preparation callback after committed apply/recovery. It verifies the mounted provisioned UUID and matching committed root record, refuses interrupted volume transactions, reloads systemd after fstab changes, and starts/checks only justverify-versions. It does not start Core.
- Failure leaves the volume committed and reports profile_ready=false. The explicit owner-authenticated `prepare_profile` action and TUI B retry only this step, avoiding another format. TUI V identifies the first profile and prompts version/network review.
- Isolated storage test servers omit the systemd callback so their nonproduction mount/fstab fixtures do not change live services. Production callback behavior is tested against the actual production mount path and systemd version service in the initial-profile integration test.

## Development image includes initial registration/version services

- Image builder installs Core31.1 in the verified version-tree layout, with the legacy core path as a compatibility symlink. Copied runtime/catalog/web files are root-owned and not group/world writable; source workspace ownership must not leak into the image.
- Package profile/download helpers and exact no-argument sudo rules, production versions config (bootstrap override false), fetch script, GPG/CA and filesystem tools. Enable versions together with storage; mount conditions keep it inactive until storage exists, and Core registration gating remains separate.
- Verifier now checks these artifacts, sudo syntax, enabled services, root ownership, production config, startup gates, and absence of node-ready/active registration in the shipped image.
- This remains a development image. Apt repository snapshots and wheel hashes are not yet fully locked; recording installed versions is not equivalent to a reproducible release build. Actual Pi boot and complete release acceptance remain required.

## Durable registered reboot test checkpoints

- The isolated initial-profile test can retain a successful registered fixture only when explicitly run with the test-only JV_KEEP_REGISTERED_FOR_REBOOT=1 flag. It writes persistent original-file metadata/backups, original mount UUID and unit enablement, identity hashes and boot ID before reboot.
- Verification/restoration is a separate process so SSH/session loss during reboot does not lose the recovery procedure. The verifier compares the actual new boot, mounted UUID and running RPC/index state before restoring the baseline. The ordinary initial-profile test still restores in finally; failed preparation restores fstab before remounting the original data.

## Version recovery remains visible when target validation fails

- Version state now returns a separate active_error and durable transition summary. Failure to validate the current target artifact must not hide the prior-profile recovery operation. Preview/apply continue to perform full validation; this changes observability, not artifact trust.
- TUI V exposes R with a review/cancel step. Recovery uses the existing journaled engine: restart prior binary with its own separate data; preserve target data; if no prior profile exists, leave services stopped. It does not infer downgrade compatibility or recreate a missing target executable.

## Reboot while a version transition is durable but not activated

- Test the actual engine boundary by pausing a temporary privileged bridge wrapper after the engine persists starting/target selection, then killing the real service cgroup and rebooting. Do not synthesize a journal when claiming SIGKILL evidence.
- The existing registration gate blocks mismatched selection/configuration on reboot. Recovery is explicit through TUI R and uses the old version's separate data; the test confirms it requires no compatibility assumption or data rollback. Temporary wrapper is restored before reboot and baseline recovery remains durable across the SSH disconnect.

## Per-client RPC gateway foundation

- `web/rpc_gateway.py` adds a deliberately named node-read scope: a fixed set of chain/mempool queries, no wallet/admin/mutation methods. It is not presented as full Fully Noded or Nunchuk RPC compatibility. Watch-only wallet integration and mobile payload/UI remain separate work.
- Owner-session + exact Origin + CSRF is required to create/list/revoke clients through `/rpc-clients`. Each client gets an independent random identifier and 256-bit secret; only its SHA256 digest is stored in the private web state. Secrets are returned only at issuance. Revocation is checked on every query and again before returning an in-flight result.
- `/rpc` accepts those Basic credentials over the existing mandatory TLS server. It forwards only allowlisted JSON-RPC requests to the profile's loopback Core endpoint using the local cookie, never forwarding the external credential to Core. No batches; four concurrent upstream calls, 30 requests/client/minute, 15s upstream timeout, 4MiB response limit. Core secrets and transport failures are not returned as diagnostic details.

## Local TUI client issuance and shared client storage

- TUI C manages node-read clients: named issuance, one-time credential popup, explicit revoke review/cancel. E retains existing Electrum/Tor detail access and is active only outside input/review/popups. The popup states the limited scope and certificate authentication requirement; it is not a mobile-wallet compatibility claim.
- `web/manage_clients.py` is a fixed no-argument non-root helper for the already trusted local TUI account. It requires private owned web state and owner enrollment. It shares the same client store with the authenticated web management API; it does not provide a shell or accept paths/commands.
- Client create/revoke now hold a private advisory file lock across read/modify/atomic-write, preventing lost records when TUI and web processes write concurrently. Authentication reads either the old or new complete atomic file.

## Mobile source audit and plain Electrum QR

- Audited official repositories at pinned commits in `catalog/mobile-source-audit.json`: Nunchuk Android `1f07b4e2f9d30ff2c6ad7ad797885ba862d98e22`, FullyNoded `d0d1502eef2840c0457aa321b88cf606ee8b4650`. Latest release metadata observed android.2.8.5 / v2.1.0; audited default-branch commits are not asserted identical to those release binaries. No mobile app was installed or tested.
- FullyNoded QuickConnect parses URI host/port/user/password and stores host:port; its inspected parser does not preserve our `/rpc` path or establish HTTPS gateway compatibility. Do not generate a purported working FullyNoded QR from the node-read gateway yet. Nunchuk Android network code accepts Electrum server selection and has separate proxy settings; inspected files do not establish generic endpoint QR auto-import.
- Q (also C→Q) displays the actual published Tor Electrum hostname:50001 as plain address text QR. It states Electrum TCP over Tor, no TLS, wallet-device Tor SOCKS proxy required, no RPC credentials, and no verified app auto-import. No unreachable LAN Electrum endpoint is invented.
- QR uses pinned qrcode8.2, four-module quiet zone, black/white half-block terminal rendering. Small screens show the address and enlarge instruction rather than a clipped QR. Main screen contains no QR graphic.

## Core-compatible root RPC path and client persistence

- FullyNoded's pinned MakeRPCCall.swift uses the host root for node RPC and appends `/wallet/<name>` for wallet calls; HTTPS is selected only with a stored certificate. Add POST `/` as an alias of the exact same authenticated node-read gateway while preserving GET `/` for the browser. This is transport groundwork, not FullyNoded wallet support.
- Do not enable every command enumerated by the app. The default Core remains wallet-disabled; future watch-only provisioning must isolate each client wallet and reject private-key import before opening wallet routes. No wallet endpoint is added here.
- Verify client credentials survive an actual TLS process restart using the same private state, then verify TUI revocation invalidates them. Keep these results separate from whole-device reboot and physical app evidence.

## Disposable image boot probe

- Supplement offline image verification by booting a disposable raw copy on QEMU virt with the builder's Debian ARM64 kernel/initramfs. Only the copy receives a test-only systemd probe; the distributed image stays immutable.
- Probe firstboot-generated identity, registration gate, installed manager/web services, verified TLS ownership claim and actual packaged TUI over authenticated WebSocket. Output booleans and exception type only, never setup/session/password contents. Power off after recording the result.
- This tests image userspace startup on a generic virtual machine. It does not validate the packaged Raspberry Pi kernel/firmware, Pi peripherals, real installation media, mDNS on a physical LAN or phone pairing. Those acceptance gates remain separate.

## Disable the inherited OS user-creation dialog

- Actual dev4 generic image boot exposed `userconfig.service` starting alongside our ownership console. Inspection of the packaged unit and `/usr/lib/userconf-pi/userconf-service` showed it opens tty8 and runs chvt before interactive username/password dialogs. It can steal the physical display from the fixed tty1 flow.
- Disable and mask this OS dialog in the appliance image. JustVerify's non-root system account and explicit owner enrollment remain the supported path; no default Linux password or auto-login shell is introduced. Add offline mask verification and actual-boot masked/PID0 checks.
- Preserve dev4 and its positive web-firstboot results with this defect recorded. Build dev5 as a new artifact and repeat the affected boot path; do not rewrite dev4 in place or claim its console flow passed.

## Watch-only descriptor wallet boundary

- Add `web/watch_only.py` as an internal component requiring an already-authorized client and selected loopback RPC adapter. Wallet name is derived only from a validated 32-hex client ID; no external path or arbitrary wallet name is accepted. Default production profiles remain wallet-disabled until explicit profile activation is implemented.
- Create blank descriptor wallets with private keys disabled and persistent load-on-startup. Every operation verifies wallet name, descriptors=true and private_keys_enabled=false; existing private-key wallets are refused. Interrupted creation can be retried using the stable name without deleting data.
- Before importing any descriptor batch, inspect every entry with Core getdescriptorinfo and reject any private-key input. Core can still return per-entry errors for other semantic import failures; this does not claim atomic descriptor imports. Direct key import/export, arbitrary backup paths and signing methods are absent from the boundary.
- Core22 listdescriptors has no private argument. Normalize public-only requests to the no-argument form, reject private=true, and verify against real binaries instead of assuming modern RPC signatures. Official createwallet/getdescriptorinfo documentation: https://bitcoincore.org/en/doc/22.0.0/rpc/wallet/createwallet/ and https://bitcoincore.org/en/doc/22.0.0/rpc/util/getdescriptorinfo/ .
- This internal component is not yet a public wallet gateway or full FullyNoded integration. Owner-approved wallet profile activation, client lifecycle coupling/revocation, PSBT workflow, UI and actual mobile tests remain required.

## Watch-only profile selection uses the version transaction

- Extend Instance with an optional watch_only boolean, omitted when false so existing node markers/selections remain compatible. A watch-only profile uses `instances/<network>/<version>-watch-only/` with its own Core data, electrs index and managed policy; node data remains at the existing path. This costs a separate synchronization/index and is stated during review.
- Reuse preview token/revision checks, durable version transition, service stop/start/readiness and prior-profile recovery. Do not toggle wallet support in an existing chain directory or introduce a second conflicting restart transaction.
- Fixed root bridge accepts only a boolean mode and constructs the path; validates the exact instance marker, verified binary and network. It emits disablewallet=0 only for the explicit watch-only profile. Startup gate binds mode and path to root registration. Default remains node/disablewallet=1. Wallet-capable local Core is not exposed unrestricted; client gateway still denies wallet creation until lifecycle integration is ready.
- TUI V/W selects mode, Enter reviews the separate profile, Esc cancels. This is profile activation only; named client wallet authorization, revocation and wallet RPC/PSBT/mobile remain separate required integration work.

## Profile- and volume-bound wallet grants

- Owner `/rpc-clients` grant_watch_only requires existing owner session/Origin/CSRF. TUI C/W uses the fixed non-root helper, reviews version/network/assigned wallet and submits the reviewed profile fingerprint; changes after review reject the grant. New clients remain node-read until explicitly granted.
- `wallet_gateway.py` uses the root profile and registration marker. Bind permission to profile bytes plus registered volume UUID, verify registration config hash before and after upstream calls, and reject changed profile/volume. Only the assigned client-derived wallet route reaches loopback Core; external wallet names cannot redirect requests. No external credentials are forwarded.
- Expose public descriptor import and the verified wallet read subset; filter listwallets/listwalletdir to the assigned wallet. Keep wallet creation/admin/private export/signing outside client RPC. Owner provisioning creates only private-key-disabled descriptor wallets and is idempotent. PSBT and full mobile app flow are not completed by this subset.
- Revocation denies subsequent/in-flight response access and preserves wallet data. Retain profile grant history: if a previously assigned wallet disappears, regrant refuses to create an empty replacement. Restore missing data before regrant. A new explicit grant on a different profile can create that profile's separate wallet.
- Import checks all descriptors for private keys before persistent wallet mutation; other Core per-entry import errors are still possible. Enforce existing RPC request/concurrency/size limits and bounded wallet operation timeout. Interrupted/timed-out import may have completed in Core; do not claim rollback.

## Explicit transaction permission and no node signing

- Keep existing watch-only grants limited to public import/queries. Add a separate owner grant_transactions and TUI C/T review for PSBT preparation and broadcasting externally signed transactions. Persist transaction permission per profile/volume fingerprint; old grants do not acquire it automatically. Client list explicitly labels transaction permission.
- Verify assigned watch-only wallet before PSBT work. walletprocesspsbt always sends sign=false; explicit sign=true is rejected. Funding options are restricted to reviewed common Core fields; solving_data is excluded so it cannot bypass public descriptor validation. fee_rate remains sat/vB and feeRate BTC/kvB; reject simultaneous fields, perform no floating-point conversion, and use explicit decimal strings in tests.
- Expose Core PSBT create/fund/update/decode/analyze/combine/join/finalize, raw decode, mempool acceptance and broadcast only after separate permission. No private-key signing RPC is exposed. Core validates the signed transaction; the gateway does not implement consensus or sign.
- RPC clients without browser Origin remain supported; when Origin is present, require the configured origin to prevent cross-site browser requests. Existing authentication/revocation/profile/volume/concurrency/size/time limits apply to transaction calls.
- A broadcast or timed-out mutation may have completed upstream. Do not promise rollback or deletion on client revocation. External hardware signing and exact wallet-app compatibility remain separate evidence requirements.

## Full image verifier scratch on persistent storage

- dev6 verification exposed that `/tmp` is a small tmpfs in the builder and contained preserved regtest fixtures. Compressed image extraction can exceed RAM-backed temporary storage even with sufficient root-disk space.
- Allocate the verifier's dedicated full-image scratch under `/var/tmp`, keep its existing trap cleanup and read-only mount/e2fsck checks. Do not delete unrelated fixtures or weaken checks to accommodate space.
- Disposable prepared images are root-private after the fixture umask change. Transfer them through already-authorized sudo cat on the isolated builder; keep host test copies mode0600 and separate from pristine distributable artifacts.

## Observe terminal state, not differential output strings

- Ratatui sends updates against previous screen contents; a visible menu phrase need not exist as one substring in the raw WebSocket stream. For image boot C/T menu verification use pyte0.8.2/wcwidth0.8.3 to maintain actual120x40 terminal state with incremental UTF-8 decoding.
- These pinned observer modules are test-only additions to a disposable copy; the pristine image and production runtime are unchanged. Retain the same menu/content assertion and both boot phases. Never capture credential popup text in the probe; only the client list is opened.

## Source audit and public-testnet isolation (2026-09-12)

- Keep official upstream snapshots separate from product code. Record Git commit plus hashes, and distinguish latest electrs development REST architecture from packaged0.11.1 P2P architecture; avoid changing required services based on an unshipped version.
- Run public testnet4 Core31.1/electrs0.11.1 in a new private host directory because Linux builder has only5.6GiB free. Keep wallets/key material out of reports and git. Testnet signing wallet is a test fixture, not a change to the product watch-only boundary.
- Height alone cannot establish Core/electrs agreement. Compute the Electrum80-byte header's Bitcoin double-SHA256 hash and compare to Core bestblockhash, preserving Core IBD check. A racing block can temporarily report INDEXING and will be rechecked on the next sample.

## Outgoing network semantics and dependent service restart

- Route onion destinations through the product's fixed SOCKS endpoint; `proxy=1` in the editor means Clearnet through that same local Tor service, never an arbitrary endpoint. Unlike Umbrel's UI restriction, transport through Tor need not enable onion destinations; these are distinct choices. I2P is refused until a router exists.
- Core22 documents that `onlynet` alone does not exclude onion when onion/proxy is set. Render derived `noonion=1` for an explicit selection excluding onion; expose the effect in review. A live includeconf precedence probe and actual22/31 preflight verify it. Mirror base config plus include file during preflight instead of hiding production default interactions with CLI overrides.
- An owner-reviewed Core configuration change deliberately stops electrs and TLS before restarting Core. electrs0.11.1 exits when its P2P channel disconnects; letting repeated configuration changes look like crashes exhausts its retry limit. Restart affected services explicitly while preserving bounded automatic crash recovery.


## 2026-09-12 incoming selection and effective socket evidence

- Incoming selection is independent of outgoing onlynet/proxy. The UI `listen` selector is a JustVerify composite, not a literal Core boolean: none/clearnet/tor/both derives network-scoped `nobind=1` and a finite binding list while the base `listen=1` stays enabled for electrs P2P. Clearnet uses IPv4+IPv6 wildcard on the selected chain P2P port; no clearnet uses loopback. Tor adds loopback P2P+1 tagged `=onion`. RPC bindings are untouched.
- This intentionally differs from Umbrel's router-port-forwarding assumption: disabling Clearnet actually removes the nonloopback listener. Tor identity remains persistent; disabling Tor incoming closes its backend, not the separate Electrum/RPC onion services. No automatic Core Tor identity management.
- `bind` is network-scoped, including in includeconf. The managed file uses an explicit chain stanza. Parser rejects mismatched/extra binding directives or a selector whose derived bindings differ. Resetting to default removes the managed override and restores the reviewed base profile.
- Preflight remaps incoming bindings to fresh loopback ports, preventing temporary public exposure. Real systemd post-restart verification reads the selected Core process's owned Linux listening sockets and compares P2P addresses exactly; this is kernel evidence, not a claimed RPC setting value. A mismatch enters the existing configuration rollback path. VM integration independently probes LAN/loopback/onion ports and checks indexed tip.
- Initial Core26.2 matrix failure was an occupied adjacent test port; Core logged successful normal bind and failed onion bind. The test correctly refused success. Reserve both adjacent P2P ports while allocating the RPC port; retain the failed private stage and rerun. Production Core may continue with a subset of bindings, which is why process-socket verification is necessary.


## 2026-09-12 resource/index controls and private broadcast

- `catalog/resources-<version>.json` comes from that release's executed help and official init.cpp hash. Core defaults are retained (for example dbcache450/1024 MiB and RPC queue16/64 differ between22 and31). Units are explicit: buffers use1000 bytes, upload target and dbcache use1048576 bytes. Parser rejects native multiplication/width overflow and known clamps. Numeric accepted ranges are product bounds, not a claim that every number is a Core documented safe deployment size. dbcache is additionally capped at75% of Linux device RAM; this is not a performance guarantee.
- maxconnections minimum12 keeps inbound capacity for electrs in addition to automatic outbound connections; it does not reserve an exclusive peer slot. The effective startup limit must match the request, rather than accepting Core FD-limit clamping. Source references: versioned init.cpp and [Core31.1 net.h](https://github.com/bitcoin/bitcoin/blob/9be056a8a72b624dae9623b2f7bded92c2a21c91/src/net.h). Resource configuration receipts distinguish log evidence from actual getnettotals bytes; integration additionally checks real ban duration and indexer continuity. Extreme-load/performance behavior remains unverified.
- Optional txindex/basic blockfilter index/txospenderindex are explicit selections, with peerblockfilters requiring a reviewed blockfilterindex selection. They build asynchronously; getindexinfo presence is startup acceptance, not completion. Real tests separately require synced=true and matching height. Turning an index off retains its files. electrs0.11.1 still requires unpruned data and does not need txindex. Prune remains fixed0 intentionally.
- Embedded ASMAP is exposed only for Core31.x whose executed help describes it; enabled uses asmap=1, disabled uses Core's explicit noasmap=1 to avoid interpreting0 as a filename. File paths are not accepted. Core startup bucketing logs verify the result. REST can be enabled only on the existing loopback Core RPC listener; wallet gateways have no REST forwarding route. No I2P or mining IPC dummy switches were added.
- [Core31.1 release notes](https://bitcoincore.org/en/releases/31.1/) document the31.0 private-broadcast IP leak. JustVerify refuses enabling that feature on31.0 while preserving31.0 version selection and default-disabled operation. Isolated regtest connect=0 also refuses enabling it explicitly. Public-network preflight switches only this case to networkactive=0 (connect=0 is incompatible); Core networking must be observed disabled.31.1 main/testnet4/signet startup PASS, but private-broadcast transport/anonymity is NOT TESTED and never implied by preflight.

### Dedicated electrs historical-download backend

Actual Umbrel app deployment uses an unpublished trusted P2P port. Core31.1 historical upload-limit logic refuses historical blocks without Download permission. Reproduced this with actual mined14-day-old regtest blocks and maxuploadtarget1MiB; ordinary P2P refused and fresh electrs indexing failed as expected. Same chain/cap with download,noban loopback whitebind indexed65 blocks and exact tip. Use network P2P+2 with only those permissions, no mempool/forcerelay, explicitly bind normal/onion because whitebind disables implicit listeners. Profile metadata and actual process-owned sockets verify port placement. This backend is not an external address or QR payload. Core22–31 matrix and registered/reboot verification tracked separately; host31.1 PASS.

### Policy default token parsing

Core31.0/31.1 help says `default: 64, maximum: 64` for limitclustercount. The generated default incorrectly included the comma and maximum annotation. Parse only the default token (like the resource catalog), retain the full official description, and leave the existing maximum64 validation unchanged. All32 generated policy catalogs' non-null scalar defaults now parse numerically. This is a display/catalog correction, not a change to Core's policy.


### Backup boundaries and policy evidence (2026-09-12)

Encrypted backup content is untrusted even with a correct passphrase. Restore checks a root-pinned canonical profile, the currently registered data UUID/instance and verified binary, and validates policy through the fixed Rust parser before replacement. The same bytes are hashed and decrypted; rollback files and directory entries are synced before the applying journal. Owner reauthentication precedes sensitive operations. Commit requires live Core RPC and trusted Electrum TLS whose indexed header matches Core at that height; an index still catching up is not called fully synchronized. Same-volume recovery is tested; reinstall/adoption recovery remains separate work.

Policy persistence tests unload the test wallet before restarting: a wallet can re-submit its unconfirmed transactions, which would otherwise conflate wallet startup with mempool.dat loading. Core30+ returns datacarrier for the aggregate OP_RETURN budget; Core22 returns scriptpubkey for an oversized single output and multi-op-return for multiple outputs. Tests preserve these version-specific expectations and confirm that a mempool-policy-rejected data transaction can still enter a valid block.

### Pi5 A/B 조사 기록 — 2026-09-12 사용자 지시로 폐기

The following was an abandoned proposal, not the current installation design. It proposed separate inactive/active boot+root slots and shared device state/data on the user-provided NVMe. Verify the complete signed artifact before inactive-slot writes; retain current slot and current Core/electrs data paths. Trial boot uses firmware tryboot, and only actual health verification changes the persistent default. Boot failure must return to the prior slot, without pretending Core/electrs data migration can be reversed. Shared state/schema and selected Core/electrs compatibility must be checked before trial; the first update format must reject any unvalidated data-format transition.

The firmware mechanism is documented in [official autoboot source](https://github.com/raspberrypi/documentation/blob/5e2c40fe1125bb8ff7374de2c11c94761084eb1f/documentation/asciidoc/computers/config_txt/autoboot.adoc). Reviewed the official rpi-system-update example at a5b32dad7579e949e77ef95edcfa1a7df8773274 (Apache-2.0): it uses a Buildroot/container boot-image layout, so no implementation was copied into the existing native Pi OS application. Firmware2712 release notes at279e8b86fd038f026a8daad1223305a15a7d1f2b describe GPT handling, including4K-sector fixes. Actual EEPROM/HAT/NVMe geometry and trial fallback still require the offered Pi5. No EEPROM/OTP change or live disk write has been performed.

### 단일 NVMe·단일 OS 설치로 확정 (2026-09-12)

사용자가 OS 두 벌과 별도 기기 상태 영역을 두는 A/B 구성을 명시적으로 거부했다. 최종 설치 경로는 깨끗한 NVMe 한 개에 balenaEtcher로 JustVerify 이미지를 기록하고 Pi5에 연결해 부팅하는 방식이다. 두 번째 OS 슬롯, tryboot 전환, 별도 상태 파티션은 구현·배포하지 않는다. 미통합 A/B 실험 소스와 시험은 `.state/ab-experiment-retired-20260912/`에 보존했으며 단일 OS 검증 결과로 계산하지 않는다.

첫 부팅에서 같은 NVMe의 용량 확장·데이터 경로 준비와 서비스 시작을 자동 처리한다. 별도 데이터 SSD나 Linux 명령 입력을 정상 설치의 전제로 삼지 않는다. 기기별 신원과 소유자 등록은 유지하고, 최초 체인 동기화는 부팅 완료와 구분한다. 업데이트 실패 복구 요구는 유지하되 A/B 설계를 다시 도입하지 않는다. OS 부팅 불능 시 검증된 이미지 재기록 및 암호화 백업 복원을 포함하는 단일 OS 복구 경로를 구현·검증하며, 자동 롤백과 재설치를 구분하여 문서화한다. dev13의 별도 데이터 디스크 VM 검증은 이 단일 NVMe 설치 검증을 대신하지 않는다.

단일 OS 구현은 boot/root/data의 GPT 세 파티션으로 구성한다. root에는 OS와 기기 상태를 함께 두고, 마지막 data 파티션만 첫 부팅에서 NVMe의 남은 공간으로 확장한다. root의 고정 메타데이터와 실제 root 파티션의 부모 장치를 대조한 후 공장 데이터 marker 및 파일시스템 UUID를 검증한다. 런타임 포맷은 없으며 다른 디스크는 대상으로 선택할 수 없다. 공장 UUID를 기기별 무작위 UUID로 바꾸는 작업은 root 저널을 먼저 저장하여 중단 후 같은 UUID로 재개한다. 기존 외장 데이터 포맷용 확인 절차와 이 경로를 혼합하지 않는다. data 마운트는 첫 부팅 서비스에서 매 부팅 검증 후 수행하고, 마운트 실패 시 후속 서비스의 firstboot 의존성 및 기존 node-ready gate로 기동을 차단한다.

### 지정 Pi5 시험 매체의 root 접속 (2026-09-12)

사용자가 해당 2TB NO NAME NVMe 전체 삭제와 Pi5 root 원격 시험을 명시 허용했다. 배포 dev15 원본은 SSH 비활성 상태로 보존하고, tests/prepare_pi_test_image.py가 새 비공개 복사본에 Mac 전용 Ed25519 공개키와 개별 최초 소유권 파일을 넣는다. SSH는 공개키 root 접속만 허용하고 암호·keyboard-interactive 로그인을 차단한다. 개인키는 Mac .state/pi5-install에만 보관하며 이미지·VM·Git에 전달하지 않는다. SSH 호스트키는 이미지에 없고 실제 기기 첫 부팅에서 생성하여 이후 유지한다. 개인화 복사본에는 최초 소유권 비밀정보가 있으므로 공개 배포하지 않는다.

첫 개인화 이미지 VM 시험의 실제 Tor onion timeout은 실패로 보존했다. 동일 이미지의 새 복사본에서 기존 시간 제한과 전체 검사를 유지한 재시험이 최초·재부팅 모두 통과했고, 두 부팅의 실제 root 공개키 SSH 및 호스트키 보존도 별도 검증했다. 이는 Pi 펌웨어·실기 검증을 대체하지 않는다.


### Pi5 initramfs 자동 resize 충돌 (2026-09-12)

실제 Pi5 첫 부팅에서 Raspberry Pi OS initramfs resize_early가 GPT Fix/Ignore 입력을 요구했다. 단일 OS 이미지 변환 시 upstream `resize` 커널 인자를 제거한다. root p2 고정/마지막 data p3 확장은 JustVerify factory_volume만 담당한다. upstream 스크립트를 삭제하거나 GPT 경고를 무조건 승인하는 방식으로 해결하지 않는다. read-only 이미지 검증에 실제 boot cmdline 검사를 추가한다. generic QEMU initrd 및 별도 cmdline 테스트가 이 경로를 누락했으므로 Pi 부팅 기준은 계속 별도 유지한다.


### 사용자 요청 SSH 기본 계정 예외 (2026-09-12)

사용자가 명시적으로 justverify/justverify SSH 기본 로그인을 요청했다. 기존 공통 암호 금지 기본안에 대한 사용자 지시 예외로 적용한다. 사설 LAN 주소에서 justverify 암호 로그인만 허용하고 root는 공개키만 유지한다. 최초 SSH 초기화 시 한 번만 암호를 설정하며 이후 비밀번호 변경을 덮어쓰지 않는다. SSH host key는 기기에서 생성한다. 기존 좁은 sudo API만 유지하며 무제한 sudo를 추가하지 않는다. 웹 터미널은 여전히 고정 TUI 프로그램이다. 운영 시 공통 암호 변경을 안내한다.

### Pi 실기 웹 접근 및 이미지 크기

실기에서 HTTPS443은 정상이고 HTTP80은 listener가 없어 IP만 입력한 브라우저 접근이 실패했다. HTTP GET/HEAD는 고정 https://justverify.local/로만 redirect하고 사용자 Host/경로/쿼리를 반영하지 않는다. 암호 처리와 관리 UI는 HTTPS에만 있다. 자체 인증서의 최초 신뢰와 mDNS 불가 시 IP 대체 경로는 별도 검증 항목으로 남긴다.

원본 raw9,120,514,048 bytes는 실제 파일량과 다르다. unbooted factory 이미지에서 apt 목록/캐시와 pip 캐시를 제거하고 루트 ext4를5GiB로 줄인 후 GPT/data 위치를 재구성한다. 2GiB 런타임 swap backing 파일과 업데이트 여유를 고려해 최소 파일시스템 크기까지 축소하지 않는다. Pi kernel/firmware와 Core/electrs 실행 파일은 그대로 보존한다. 압축은 xz -6으로 변경한다.


### 사용자 지정 LAN HTTP 및 간소화 최초 등록 (2026-09-12)

사용자가 인증서 초기 접속 문제를 없애기 위해 HTTP 및 Umbrel처럼 새 암호/암호 확인만 입력하는 최초 실행을 명시 요청했다. --http-lan-port80 --lan-onboarding 설정으로 사설 LAN에서 최초 등록 시 기기 코드를 요구하지 않는다. 최초 LAN 등록자가 관리 계정을 설정하는 모델이며 기존 소유권 코드 의무 기본안에 대한 사용자 지시 예외이다. HTTP 관리 세션/암호는 전송 암호화되지 않으므로 인터넷 공개용 경로로 설명하지 않는다. 기존 HTTPS443 및 외부 RPC TLS 경로는 유지하고 HTTP listener에는 직접 Core RPC route를 제공하지 않는다. HTTP/HTTPS cookie 이름을 분리해 이전 Secure cookie가 HTTP 로그인을 막는 문제도 방지한다.

최초 등록은 /setup에서 확인값 일치 및 암호 길이를 검증하고, 등록 후에는 /login만 사용한다. /auth-status는 등록 필요 여부만 반환한다. 실패 메시지는400입력불일치/401잘못된암호/409이미등록/429재시도시간으로 구분한다. 최초 등록 후 관리자파일을 덮어쓰지 않는다. 서버 재시작 후 동일 암호 재로그인도 실제 HTTP 서버 시험에서 검증했다.


## 2026-09-12 — 영상 기반 Core 중심 내비게이션

사용자 요청으로 설치를 상위 메뉴에서 제거하고 기기 설정으로 통합했다. 메인은 실제 블록 헤더 기반 구획형 TUI이며 Core 안에 버전/정책/피어를 둔다. 공식 Umbrel commit2fe07948 참조만 하고 코드/리소스는 재사용하지 않았다. 상세와 검증 경계는 UI_REDESIGN.md 참조. 헤더6개를 tip 변경 시만 수집해 대용량 getblock 응답과 반복 부하를 피한다.


## 2026-09-12 — 반응형 브라우저 표시와 이미지 QR

사용자가 영상처럼 보더·개별 헤더·반응형 배치·작은 바차트를 명시 요청했다. 이 최신 지시를 기존 메인 차트금지보다 우선해 CPU/RAM 자원 meter만 허용한다. 브라우저 현황은 native와 동일한 Snapshot의 별도 반응형 DOM 표시이며, 관리·설정은 기존 고정 비권한 TUI를 유지한다. UI가 실제 수집 값을 바꾸거나 체인 상태를 추정하지 않는다.

CSP의 style-src self만으로는 xterm 동적 style 요소가 적용되지 않아 한글 폭/정렬/색상이 붕괴했다. style-src에 unsafe-inline을 허용하되 script-src self, 인증, CSRF, 세션, Origin, RPC 분리, 데이터 textContent 출력은 유지한다. [xterm 공식 보안 지침](https://xtermjs.org/docs/guides/security/)의 동적 JS/innerHTML/외부 리소스 금지 원칙을 따른다. PNG는 코드로 결정적으로 생성하며 생성형 이미지 도구를 사용하지 않는다.

LAN/Tor 선택은 사용자 관점에서 연결 방식이며 설정 주소와 서비스 실행은 분리해서 보여준다. inactive 서비스의 QR은 연결대기 표시를 포함하고, 실제 카메라/앱 가져오기 성공을 주장하지 않는다. HTTP에서도 QR PNG를 저장할 수 있게 clipboard secure-context API에 의존하지 않는다.

## 2026-09-12 — 초기 노드 자동 시작과 브라우저 설정

- 사용자 요청6항목에 따라 브라우저는 Electrs / 버전 변경 명칭과 Core 현황의 피어 목록을 사용한다. F4/키보드 전체 피어 상세 API는 유지하며 상위·하위 browser 메뉴에서 중복 피어 버튼만 제거한다.
- refresh는 기존 HttpOnly cookie를 `/session`에서 검증하고 CSRF 값을 복원한다. 비밀번호·세션 토큰을 JS 저장소에 넣지 않는다. 기존 절대 만료1시간과 로그아웃 폐기를 유지하며 web 프로세스 재시작/기기 재부팅은 재로그인이 필요하다.
- 초기 owner 등록만으로 Core가 시작되지 않았던 제품 흐름을 수정한다. 인증된 화면 진입 후 `/node-start` POST가 선택 상태를 확인한다. 선택 없음 + 신뢰한 새 빈 볼륨인 경우에만 이미지의 고정 기본 profile 버전·네트워크를 기존 storage/versions API로 등록한다. 실제 Pi 기본31.1/main/node 모드를 시작했다. root guard, mount UUID, owner, binary hash, empty volume 검증을 우회하지 않는다. 활성 선택/기존 데이터는 자동 전환하지 않고 미완료 journal은 명시 복구 대상으로 남긴다.
- `/policy`, `/versions`는 same-Origin + session + CSRF 및 요청 schema를 확인하는 좁은 웹 어댑터다. 기존 Rust catalog/preflight/단위변환/미리보기 token/operation lock/원자적 저장/재시작·상태 확인을 그대로 호출한다. 설정용 browser 화면을 native HTML로 만들어 마우스 및 모바일 터치 조작을 제공한다. 실제 로컬/SSH TUI와 고정 PTY 경로는 보존한다.
- boolean은 switch, incoming/outgoing은 독립된 경로 switches, 수치는 단위를 표시한 문자열 입력이다. 수수료는 sat/vB 문자열로 전달하며 기본 Core BTC/kvB를 BigInt로 표시 변환한다. 큰 정수 범위는 JSON 문자열로 전달해 브라우저 Number 반올림을 피한다. 기본값·저장 요청값·현재 편집값을 표시하고 actual RPC로 조회할 수 없는 값까지 관측됐다고 표현하지 않는다.
- 버전 카드는 클릭 선택/hover 강조, 네트워크 선택, 바이너리 다운로드·서명 검증, 전환 영향 검토, 적용 순서다. 현재와 동일한 선택은 변경 버튼을 제공하지 않는다. Core/electrs 데이터의 별도 경로 보호를 유지한다.
- 공식 Umbrel Bitcoin `2fe07948f99e101dbee95ce34e5947a69c441ee4`의 settings/{Toggle,Form,InputField,SaveSettingsDialog} UX와 로컬 pinned settings metadata를 참고했다. 스위치·수치 입력·저장 검토의 기능 구성만 독립 구현하고 PolyForm Noncommercial 소스/스타일/리소스를 복사하지 않았다.
- Core IBD 중에는 electrs 프로세스 실행만으로 지갑 연결 준비 완료를 표시하지 않는다. 실제 snapshot의 IBD 및 Core/electrs tip READY 상태를 연결 페이지에도 전달한다.

## 2026-09-12 일반 설정·원격 웹 접속

- 최신 사용자 요청으로 responsive 웹 설정과 독립 SVG 로그아웃, 저장 가능한 테마/언어/웹 계정 관리를 추가한다. 원래 문서의 큰 UI 금지보다 사용자의 이후 구체적 요청을 우선했다. Apple/Umbrel 아이콘·코드를 복사하지 않았다.
- Remote Tor access는 RPC와 분리된 관리 화면 서비스다. 공개 onion도 owner authentication이 필요하며, 별도 loopback listener와 cookie/Host/Origin 경계가 적용된다. 기본 off.
- root 전원 API는 명령 enum과 Unix peer uid만 허용한다. 비권한 웹은 현재 암호와 일회용 세션-bound review를 검증한 뒤 호출한다. shell 명령을 전달하지 않는다.
- 인증 실패 5회/5분 제한을 유지하면서 성공한 인증은 실패 횟수에서 제외한다. 기존 시험은 성공까지 실패 횟수로 세던 잘못된 기대를 수정하고 실제 5회 실패 후429를 검증한다.
- 버전 정보는 실제 이미지 metadata를 읽는다. legacy Pi dev15 표시는 설치 증거에 근거한 migration metadata이며 새 release 완료를 뜻하지 않는다. 상세 설계/범위/증거는 DEVICE_SETTINGS.md.

## 2026-09-12 — Bundled mempool and publication request

The owner explicitly added the mempool explorer to the installation-image scope, superseding the earlier exclusion of a web explorer. JustVerify's own node overview remains separate. A LAN link opens the bundled app at port 3006, matching the verified Umbrel app manifest. Native Node.js, the official mempool frontend/backend, its Rust GBT module and private MariaDB are packaged during build; no first-boot package download or Docker base-image stack is required.

Upstream mempool v3.3.1 is pinned to `9332d9db97bcc7beed079acc8f79aa21c9b12a3b`. Umbrel's app configuration reference is `01de454ee9a368245a2513afc8e84969bafb946a`; its README reference is `bfa79ed24031b0065dd2f810411d58b82af1b95e`. Umbrel code and design assets are not copied. Mempool is separately distributed under its own AGPL terms, with corresponding source, build modifications, lockfiles and notices. All versions and the mining-pools snapshot are in `catalog/mempool.json`.

The backend is patched to bind only to loopback. The independent LAN proxy exposes its fixed explorer API, WebSocket and static assets on 3006; it does not proxy Core RPC. The proxy rejects non-LAN addresses and foreign Host/Origin values. SQL uses an OS-authenticated private Unix socket and no network listener. Core cookies remain local. Runtime files are confined by systemd; blockchain data is read-only for this additional service. Unlike Umbrel's sample SQL credentials, there are no baked database passwords.

Fresh Core profiles request `txindex=1`, needed for mempool's historical transaction retrieval. Existing profiles keep their configuration. The service observes IBD, txindex readiness and actual electrs tip agreement before starting backend indexing. The frontend remains available with a preparation message. SQL/cache paths are separate per network, Core version and watch-only profile; profile changes stop the old child processes before opening the next path. A 1 GiB V8 heap cap follows the Pi memory constraint; oversized disposable RBF caches are renamed and retained for diagnosis. Core block/mempool acceptance policy is not patched.

The embedded frontend includes English, Korean and Japanese. Lightning, Liquid, paid acceleration and external fiat-price data are disabled because they are outside the requested Bitcoin node scope. Mining-pool metadata is a fixed local snapshot. Frontend/API requests use the local instance and never silently fall back to mempool.space. This choice is independent of Core's Tor network policy.

Release naming uses `justverify-0.1.0-beta1.img.xz` for the Pi5 image. The beta label keeps incomplete hardware/mobile/long-run release gates explicit. README.md is English, with linked `docs/ko/README.md` and `docs/ja/README.md`. The owner's requested GitHub account was authenticated in the browser as `dontrustjustverify`; the installed connector belongs to a different account and will not be used to publish to the wrong owner.
