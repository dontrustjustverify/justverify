<p align="center"><img src="../../web/static/favicon.svg" alt="JustVerify BTC" width="96"></p>
<h1 align="center">JustVerify</h1>
<p align="center">YOUR BITCOIN NODE.<br>No Knots, no Blake2B—nothing but Bitcoin.<br>We are all Satoshi.</p>
<p align="center"><a href="../../README.md">English</a> · 한국어 · <a href="../ja/README.md">日本語</a></p>

내가 직접 검증하는 Bitcoin Core 노드입니다. NVMe에 이미지를 기록하고 Raspberry Pi 5를 켠 뒤 **http://justverify.local**을 여세요. 터미널 스타일의 대시보드, Tor, electrs와 로컬 mempool 탐색기가 함께 설치됩니다.

**0.1.0-beta1은 시험 배포 버전입니다.** 설치 전에 [통과·미검증 항목](../ACCEPTANCE.md)을 확인하세요. 빌드나 regtest 성공이 mainnet 전체 인덱싱, 실제 휴대폰 지갑 연결, 장시간 안정성 검증을 뜻하지 않습니다.

## 포함 기능

- 공식 서명을 검증한 Bitcoin Core. Core 22부터 지원 카탈로그의 버전을 선택하며, 호환성을 확인하지 않은 버전은 별도 데이터 경로를 사용합니다.
- 실제 비권한 TUI와 모바일에서도 영역이 재배치되는 브라우저 화면. 블록·피어·수수료·시스템 상태를 실제 노드에서 수집합니다.
- Tor와 electrs. LAN/Tor별 연결 주소·포트·TLS 정보와 QR을 제공합니다.
- **mempool 3.3.1 기본 포함:** 상단 Electrs 옆 **멤풀**을 누르면 **http://justverify.local:3006**이 열립니다.
- 한국어·영어·일본어와 Teal·Amber·Green·Ice 글자색 테마.
- 변경 내용 확인 후 설정 적용, 암호화 설정 백업 및 복원 도구.

## 준비할 장비

현재 이미지는 **Raspberry Pi 5, 64비트, 유선 LAN, NVMe**용입니다. 실기 검증 기준은 **RAM 8 GB와 NVMe 2 TB**, 호환되는 NVMe HAT·부트로더입니다. 적절한 전원 공급 장치와 냉각 장치를 사용하세요. Pi 4와 x86 PC용 이미지가 아닙니다.

NVMe 한 개에 OS와 데이터 파티션을 나눕니다. 데이터 영역은 첫 부팅에 자동 확장되며 A/B OS는 필요하지 않습니다. 전체 체인·txindex·electrs·탐색기 데이터가 저장되므로 압축 이미지 크기와 실제 필요한 저장공간은 다릅니다.

## 다운로드와 설치

1. 이 저장소의 **Releases**에 게시된 `justverify-0.1.0-beta1.img.xz`, `SHA256SUMS`, 서명, manifest와 릴리스 안내를 받으세요. 해당 manifest에 기재된 이미지를 사용합니다.
2. macOS에서는 `shasum -a 256 justverify-0.1.0-beta1.img.xz`로 파일 해시를 계산해 `SHA256SUMS`와 비교하세요. 실험용 서명키의 확인 방법과 한계는 [설치 안내](../INSTALL.md)에 있습니다.
3. **balenaEtcher**에서 이미지를 선택하고 지정한 NVMe에 기록하세요. 사용 중인 Etcher가 `.xz`를 받지 않으면 먼저 압축을 해제합니다. 선택한 드라이브 내용은 지워집니다. 검증을 건너뛰지 말고 성공 표시까지 기다리세요.
4. 안전하게 추출한 NVMe를 Pi 5에 장착하고 LAN과 전원을 연결합니다.
5. 같은 네트워크에서 **http://justverify.local**을 여세요. 이름으로 접속할 수 없으면 공유기에서 확인한 Pi IP 주소를 사용하세요.
6. 앞으로 사용할 웹 관리자 암호와 확인 암호를 입력합니다. 기기별 신원과 데이터 영역이 준비되고 기본 Core 프로필이 자동 시작됩니다.
7. 전원과 네트워크를 유지하며 Core 동기화를 기다리세요. electrs와 mempool의 준비 상태도 별도로 확인합니다. 서비스 실행 중 표시만으로 전체 완료를 판단하지 않습니다.

새 프로필에는 거래 조회용 `txindex=1`이 기본 저장됩니다. 기존 프로필의 설정은 보존합니다. Core·txindex·electrs가 준비될 때까지 mempool에 준비 상태를 표시하며, 결과를 외부 탐색기 데이터로 대체하지 않습니다.

## 평소 사용

| 접속·메뉴 | 용도 |
|---|---|
| `http://justverify.local` | 현황, Core 버전 변경·정책 설정, Electrs, 기기 설정 |
| `http://justverify.local:3006` | 내 노드의 mempool 탐색기 |
| Electrs → 로컬 네트워크 / Tor | 실제 주소·포트·프로토콜·TLS 지문·QR |
| 설정 | 계정, 글자색, 언어, Remote Tor access, 재시작·종료 |
| 설정 → 백업 및 복원 | 암호화된 설정 보관·복원 |
| 설정 → 문제 해결 | 서비스 상태와 고급 저장장치 관리 |

웹 관리자 암호와 SSH 암호는 별개입니다. 요청에 따라 최초 SSH 계정은 **`justverify` / `justverify`**입니다. 처음 SSH에 접속한 뒤 `passwd`로 변경하세요. 이 계정은 무제한 root 셸을 제공하지 않습니다. 공개 이미지에는 개발자의 root SSH 키나 미리 생성한 기기 개인키를 포함하지 않습니다.

관리 HTTP와 탐색기는 신뢰하는 LAN에서 사용하며 인터넷 포트 포워딩을 하지 마세요. Core RPC는 로컬에 제한하고, 지갑용 원격 RPC는 별도 인증·보호된 연결 경로를 사용합니다. Remote Tor access는 명시적으로 켜는 설정이며 서비스마다 주소가 다릅니다. QR 사용 전 [지갑 연결 안내](../MOBILE_CONNECTIONS.md)를 확인하세요.

## 백업과 복구

재설치 전에 암호화 설정 백업과 암호를 **Pi 외부에** 보관하세요. 백업은 설정과 기기 신원을 포함하며 전체 블록체인이나 지갑 개인키는 포함하지 않습니다. NVMe나 전원을 분리하기 전에 설정에서 종료하세요. 이미지 재기록은 디스크를 교체하는 새 설치이며 기존 설치에 적용하는 업데이트가 아닙니다. [설치](../INSTALL.md)와 [복구](../RECOVERY.md) 안내를 따르세요.

## 빌드·검증·라이선스

이미지 조립은 격리된 **ARM64 Linux** 환경에서 실행합니다. [빌드 방법](../BUILD.md), [인수 기준](../ACCEPTANCE.md), [시험 결과](../TEST_RESULTS.md), [현재 상태](../STATUS.md)를 함께 제공합니다.

JustVerify와 각 구성요소에는 각각의 라이선스가 적용됩니다. [제3자 고지](../../THIRD_PARTY_NOTICES.md)를 확인하세요. mempool은 upstream AGPL 조건으로 별도 포함하며, 탐색기의 **소스 · AGPL**에서 원본 소스·빌드 수정·잠금 파일을 받을 수 있습니다. Umbrel은 설치 안내와 앱 구성 비교에 참고했으며 코드를 복사하지 않았습니다. 각 upstream 프로젝트의 공식 제품이나 승인을 의미하지 않습니다.
