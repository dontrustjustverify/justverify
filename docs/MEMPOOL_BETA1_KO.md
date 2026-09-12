# 0.1.0-beta1 내장 멤풀 및 UI 변경

사용자 요청으로 별도 로컬 mempool 앱을 제품 범위에 추가했다. JustVerify의
비트코인코어 화면과 설정 API는 그대로 사용하며, 상단 멤풀 링크가 동일 기기의
HTTP 3006 포트를 연다. Core나 electrs의 공개 서버로 대체하지 않는다.

| 항목 | 공식 Umbrel 참고 | JustVerify 구현·차이 |
| --- | --- | --- |
| 앱 | umbrel-apps 01de454ee9a368245a2513afc8e84969bafb946a, 3.3.1-hotfix-1 | 공식 mempool 3.3.1 / 9332d9db97bcc7beed079acc8f79aa21c9b12a3b를 ARM 네이티브 빌드 |
| 접속 | 로컬 3006, electrum backend | 같은 LAN 포트. 선택한 Core 프로필의 cookie RPC와 loopback electrs 사용 |
| 데이터베이스 | MariaDB 컨테이너 | MariaDB 11.8.6, 비권한 사용자, private Unix socket; TCP SQL 미개방 |
| 메모리 | 소형 장치 1024MiB Node heap 및 RBF cache 보호 | 동일 heap 상한. 64MiB 초과 RBF cache는 삭제하지 않고 이름을 바꾸어 보존 |
| 서비스 준비 | Core 및 electrum 상태 의존 | IBD=false, txindex 동기화, Core/electrs tip 일치 후 시작. Core 중단 시 연결 대기 표시 |
| 데이터 | 앱 별도 데이터 | NVMe data 내 네트워크/Core버전/watch-only 별 SQL·cache. OS 영역과 분리 |
| 신규 설치 | Bitcoin 앱 txindex | 새 정책 파일에만 txindex=1 기본 지정; 기존 사용자 정책을 자동 변경하지 않음 |
| 변경 적용 | 앱 및 연결 backend 재시작 | 프로필 변경을 감지해 기존 DB를 닫고 별도 데이터 경로를 사용. Core 재시작 후 cookie 재조회 |
| 외부 시세 | upstream 선택 기능 | 비활성. 0원이라는 허위 값 대신 —; fiat 선택 숨김 |
| 언어 | upstream 다국어 | 영어·한국어·일본어 3개 실제 빌드, 미빌드 언어 선택 제거 |
| 접근 경계 | Umbrel 앱 경로 | LAN source/Host/Origin 검사; backend8999 loopback, 임의 RPC 중계 없음. 멤풀에는 별도 관리자 로그인 없음 |
| Tor 관리 | 별도 원격 접근 | 기존 JustVerify 관리 Tor 경로 유지. 내장 멤풀 3006은 LAN 전용 |
| 라이선스 | Umbrel 구현은 참고만 | AGPL 원본 전체 archive·수정 patch·lock·빌드 안내·LICENSE/COPYING을 /source/ 제공. MIT mining-pools 고지 포함 |

새 favicon은 손잡이 없는 원형 안의 큰 BTC이며 #FFB000을 사용한다. 헤더에는
요청한 전체 영문 문구를 표시하고 모바일에서는 줄바꿈한다. ‘글자색 선택’의
각 테마는 강조색, 밝은 본문, 낮은 채도의 보조 글자, 테두리와 배경을 구분한다.

## 실제 검증

`tests/mempool_live.py`는 서명 검증된 Core31.1, electrs0.11.1과 위 mempool을
격리 regtest에서 실행한다. SQL 생성과 migrations, 실제 Core/electrs tip,
HTTP로 서명 거래 전파, mempool 진입, 주소 잔액, 블록 확인, WebSocket,
Origin/Host 거부, SQL/backend 재시작, Core 중단·쿠키 교체·복구를 확인했다.
결과는 `evidence/beta1-mempool-regtest.json`에 저장한다. 첫 WS 시험의 캐시
정렬 가정 오류와 시험 포트 점유 실패는 로그에 보존하고, 테스트 기준을
낮추지 않고 새 독립 regtest에서 재시험했다.

이미지 부팅 검사는 설치된 systemd 단위·SQL socket·3006 웹·3개 locale·
Core tip 일치와 실제 재부팅을 추가 확인한다. 실제 Pi5 새 이미지 부팅,
공개망 전체 mempool 데이터 축적과 물리 휴대폰은 별도 검증이며 regtest
결과를 이들 항목의 통과로 확대하지 않는다.

## 사용·복구

- 처음에는 Core 전체 동기화와 txindex/electrs 인덱싱을 기다린다. 화면의
  100%나 서비스 active만으로 준비 완료라고 판단하지 않는다.
- 기존 설치에 txindex가 없으면 Core 설정에서 활성화하고 실제 인덱스
  완료를 기다린다. prune과 호환되지 않는 조합은 기존 preflight가 거부한다.
- 설정 백업은 설정·신원에 관한 백업이다. SQL/체인 데이터 백업으로
  표시하지 않는다. 멤풀 SQL과 cache는 해당 프로필 NVMe에 유지한다.
- 장애 시 설정의 문제 해결과 `journalctl -u justverify-mempool`을 확인한다.
  SQL/cache를 임의 삭제하지 않는다. 관리자 암호/쿠키/개인키를 로그로 공유하지 않는다.
- 전체 OS의 byte 재현 빌드, S4 실패 복구 및 물리 장비 게이트는
  `ACCEPTANCE.md`의 상태를 유지한다. 이 버전은 beta 설치 후보이다.
