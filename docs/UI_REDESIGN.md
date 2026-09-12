# Bitcoin Core 중심 화면 (2026-09-12)

사용자 제공 2025년 영상의 요약/최근 블록/피어/시스템 구획을 실제 TUI로 재구성했다. 공식 [Umbrel Bitcoin](https://github.com/getumbrel/umbrel-bitcoin/tree/2fe07948f99e101dbee95ce34e5947a69c441ee4) home/index.tsx, home/Blocks/index.tsx, components/Layout/Header.tsx 및 LICENSE.md를 검토했다. upstream의 시각 그래프 대신 프로젝트 요구에 맞는 숫자·테두리·짧은 목록을 유지한다. PolyForm Noncommercial 구현/리소스는 복사하지 않았다.

| 위치 | 메뉴 및 동작 |
|---|---|
| 비트코인코어 / 현황 | 노드, 최근6블록, 피어5개 요약, mempool, 수수료, 시스템·서비스 |
| 비트코인코어 / 버전 | 기존 검증된 다운로드/선택/변경 검토/복구 경로 |
| 비트코인코어 / Mempool·네트워크 설정 | 기존 버전별 정책 검증·검토·적용 경로 |
| 비트코인코어 / 피어 | 전체 연결 목록 |
| 지갑 연결 | 연결 관리 및 LAN/Tor Electrum QR |
| 기기 설정 | 저장장치·초기 설정, 백업·복구, 서비스 진단 |

최근 블록은 Core getblockchaininfo.bestblockhash에서 getblockheader(hash,true)의 previousblockhash를 따라 최대6개 수집한다. 전체 블록/거래를 내려받지 않으며 같은 tip일 때 재사용한다. 채굴 풀 attribution, block size는 헤더로 알 수 없으므로 임의 표기하지 않는다. 수집 실패는 이전 헤더를 STALE로 보존하며 수집기 전체가15초 이상 오래되면 Core 상태도 stale로 취급한다. 기존 Core 버전의 헤더 RPC 사용, 새 옵션이나 네트워크 추가 없음. 이번 실행 시험 버전은31.1이며 전 역사 버전 새 화면 재시험은 NOT RUN이다.

네이티브 단축키 V/M/P/C/Q/B/L 유지, S는 기기 설정, 그 안 S는 저장장치. 브라우저 메뉴는 F1~F10 터미널 이벤트로 직접 이동한다. 설정 편집 중 메뉴 이동은 적용을 수행하지 않는다. 실제 적용은 기존 검토 화면을 거친다.

검증: cargo test --locked, tests/dashboard_live.py, tests/web_lan_onboarding.py, tests/web_security.py 및 실제 Pi5 SSH 비권한 PTY. 실기 웹 HTTP 정적 파일/등록 보존 확인. 사용자 소유 웹 암호로 대신 로그인하지 않았으며 새 사용자 브라우저 로그인 후 화면 육안 확인은 아직 별도다. 신규 이미지 재빌드/부팅은 이번 UI 변경 이후 NOT RUN.

시험 중 고정 RPC 포트가 기존 프로세스와 충돌하여 인증 실패: 임시 할당 포트로 수정(기존 프로세스 변경 없음). invalidated 블록과 같은 coinbase 주소/시각을 재사용하면 동일 블록을 생성하므로 새 테스트 주소로 대체. pyte0.8.2의 CJK continuation display 예외는 실제 셀을 그대로 읽는 어댑터로 해결, PTY resize에는 SIGWINCH 전달. 실패 로그도 `.state/ui-reference/`에 보존했다.


## 사용자 피드백 후 브라우저 재검증

이전 PTY 검증에는 실제 브라우저 xterm style/CSP 충돌 검증이 빠져 있었다. 실제 브라우저에서 재현하고 styles 정책/resize를 수정했다. 새 메인은 web/static/dashboard.js의 실제수집기 기반 DOM, responsive CSS grid 박스이며 390px에서 scrollWidth=390, 각 박스 x16 width358 확인. native도 작은 화면4박스 및 CPU bar를 사용한다. 지갑 연결은 Electrum local/Tor 선택이 기본이고 RPC 관리는 하위 버튼으로 연다. QR PNG와 화면 캡처 모두 실제 주소 디코딩 통과. 폰 카메라/지갑 import는 NOT RUN.

2026-09-12 후속: Electrs / 버전 변경으로 명칭을 정리하고, Core 현황에 있는 피어 목록의 중복 메뉴를 제거했다. 설정/버전은 인증된 native HTML form으로 조작하며 기존 검증 서비스가 실제 적용한다. 1200px desktop와390px mobile에서 가로 overflow가 없고, 실제 browser 클릭·hover·정책 저장·31.1↔23.2 전환 및 reload 로그인 유지가 확인됐다. 기본값을 바꿔 테스트를 통과시키지 않았으며 상세 결과와 정확한 제한은 docs/evidence/browser-settings.json 및 ACCEPTANCE.md에 기록한다.
