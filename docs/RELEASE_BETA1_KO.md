# JustVerify 0.1.0-beta1 설치 후보

이번 후보는 큰 BTC 원형 favicon, 전체 브랜드 문구, 4색 테마의 본문/보조/강조
색상 구분, ‘글자색 선택’, 내장 mempool과 3006 메뉴를 포함한다. 설정 언어에
따라 mempool의 한국어·영어·일본어 페이지를 연다. 기존 Pi5 dev16과 사용자
mainnet 데이터를 변경하지 않고 독립 regtest와 이미지 복사본을 검증했다.

## 고정 구성

- Bitcoin Core31.1: 기존 공식 SHA256·신뢰 서명자 검증 카탈로그 유지.
- electrs0.11.1: `catalog/electrs.json`의 공식 commit/ARM 실행 파일 SHA 유지.
- mempool3.3.1: `9332d9db97bcc7beed079acc8f79aa21c9b12a3b`.
- Umbrel apps 비교: `01de454ee9a368245a2513afc8e84969bafb946a`.
- Umbrel README 구조 참고: `bfa79ed24031b0065dd2f810411d58b82af1b95e`.
- Node20.19.2, npm11.8.0(빌더만), MariaDB11.8.6, GBT Rust1.84.1/NAPI2.18.0.
- native mempool bundle SHA256:
  `c6581327f1c006a58ecbf6591107158a1011535c02e9f84ade6d40ef2071775d`.

원본 mempool 소스, 전체 수정 patch, 잠금파일, 빌드 설명 및 라이선스는
설치된 앱의 `/source/`에서도 받을 수 있다. Umbrel 코드를 복사하지 않았다.
기능별 비교와 의도적인 차이는 [대응표](MEMPOOL_BETA1_KO.md)를 참조한다.

## 실제 거래·장애 검증

격리 regtest 최종 거래:
`164c84cf7410b54bdcbab86555797d07759b8a220048f9e1939d217479f18477`.
미확인 상태에서 블록에 포함된 뒤 확인2회, 최종 높이107.
Core/electrs/멤풀 tip은
`02eb296863dd360cdc3200b30b011ef5eb436f0b8a4539b2e41e1786ab2cee91`.

실제 지갑에서 생성·서명한 거래를 멤풀 HTTP로 전파하고 Core mempool 진입,
Electrum 주소 잔액, 블록 확인, WebSocket, SQL/backend 재시작, Core 중단과
cookie 교체, electrs 재시작 뒤 실제 header hash와 주소 조회를 검증했다.
네트워크 불일치는 SQL 생성 전에 거부하고, watch-only 프로필로 전환해도
기존 SQL 저장소를 보존하는 시험도 통과했다. 테스트 지갑은 로그/결과를
보관한 뒤 제거했다. mainnet이나 실제 자금을 거래에 사용하지 않았다.

실패를 숨기지 않았다. 초기 시험 폴더 권한/시험 포트 점유/WS 배열 순서
가정 오류를 수정했다. 추가 시험에서 electrs가 종료돼도 멤풀 cache 때문에
준비 완료로 보이는 오류와 프로필 전환 중 이전 상태가 남는 구간을 찾아
수정했다. 기존 실패 결과를 유지하고 실제 데이터로 재시험했다.

Core22.0에서도 같은 실제 시험을 추가 통과했다. 거래
`01197c2bd6be7e2eb848ba2e297242d0a07c8239d4c6f7c3c38d146875cacf08`,
높이107, 확인2회이며 별도 regtest다. 중간의 모든 Core 버전과 내장 멤풀
조합까지 검증한 것으로 확대하지 않는다.

이미지 설치 중에는 mempool 폴더의 생성 시점이 빈 볼륨 보호 검사와 충돌하고,
기존 서비스의 read-only namespace에 걸리는 문제를 확인했다. 엄격한 기존
검사를 유지하고, 등록된 NVMe의 지정 폴더만 준비하는 root oneshot으로
수정했다. 앞선 두 부팅 실패와 수정 후 재시험을 별도 기록했다.

브라우저에서 Amber/Green/Ice 실제 변경, 새로고침 뒤 로그인·테마 유지,
390px 폭에서 전체 문구/메뉴와 가로 넘침 없음, 세 언어의 멤풀 경로를
확인했다. 이 결과는 실제 휴대폰 카메라나 지갑 앱 시험을 대신하지 않는다.

## 이미지와 설치

파일명은 `justverify-0.1.0-beta1.img.xz`이다. OS는 한 벌이며, 부팅/root/data
영역만 있다. root의 여유 공간은 raw IMG의 논리적 크기에 포함되지만
압축 파일에서는 대부분 제거된다. 체인·인덱스·개인키·테스트 지갑·멤풀 빌드 작업 폴더
및 사용하지 않는 기본 SQL 저장소143MiB는 배포 이미지에 포함하지 않는다.
기반 OS의 일부 컴파일러·커널 헤더는 남아 있으며, 전체 SDK를 제거했다고
주장하지 않는다. 최종 root 파일 할당량은2,139,951,104bytes다.
영어·한국어·일본어 외의 mempool frontend도 빌드하지 않는다.

최종 압축은654,231,760bytes(624MiB), raw는6,444,548,096bytes다.
SHA256은 `31ed2db7a8f16de4a0947eb5468cb61054a3eeff4ea6001c5ebb86498bed462d`.
파일 검사와 초기 등록·Core/electrs·HTTP/TUI/QR·멤풀 DB/tip은 통과했다.
첫 Tor onion RPC timeout은 FAIL로 유지하며, 같은 신원·데이터의 별도
복구와 실제 재부팅은 멤풀 및 인증된 Tor RPC까지 모두 PASS2회다.

이미지의 실제 크기·SHA·설치 및 재부팅 결과는 함께 제공하는 manifest와
검증 결과 JSON을 기준으로 한다. 검사한 원본과 부팅한 시험 복사본은
분리한다. 부팅한 시험 복사본을 NVMe에 기록하거나 공개 배포하지 않는다.

[한국어 설치 README](ko/README.md), [English](../README.md),
[日本語](ja/README.md), [복구 안내](RECOVERY.md)를 제공한다.
기존 설정은 암호화 백업과 암호를 기기 밖에 보관한 뒤 재설치한다.
balenaEtcher에서 의도한 NVMe와 이미지 hash를 확인하고 검증을 생략하지 않는다.

## 판정 경계

아직 새 beta1 Pi5 실기 부팅·물리 모바일 지갑/카메라·장시간 검증을
통과한 것으로 표시하지 않는다. 기존 Pi dev16은 읽기 확인 시
main440886/966685, IBD=true였다. 이전 공개 testnet/RPC 기록은 유지하지만
이번 mempool regtest를 공개망 전체 검증으로 확대하지 않는다.
전체 정책 의미 검증, 백업의 새 볼륨 복원, 시스템 업데이트 실패 복구,
전체 OS byte 재현성과 공개 바이너리 배포의 전체 소스/고지 검토 등
기존 S4 미완료 기준은 [ACCEPTANCE](ACCEPTANCE.md)를 따른다.
따라서 전체 ‘정상작동 확인 완료’ 또는 최종 안정판이라고 주장하지 않는다.

## 소스와 기존 검증 기록

공개 소스: https://github.com/dontrustjustverify/justverify .
영어 README와 한국어·일본어 README, 고정 카탈로그·실행 시험·라이선스 고지를
함께 게시했다. 로컬 설치 이미지는 같은 beta1 manifest/체크섬/서명과 전달한다.
전체 OS 바이너리의 공개 GitHub 배포는 아직 하지 않았다.

이전 Core RPC 목록·실행 결과·미검증 사유는 [RPC_AUDIT](RPC_AUDIT.md),
공개 testnet4 거래/동기화 기록은 [원본 증거](evidence/public-testnet4-audit.json),
포크 관측은 [별도 기록](evidence/testnet4-fork-observation.json)에 보존한다.
이번 새 멤풀 조합의 거래2개는 모두 격리 regtest이며 새 공개 testnet 거래로
표시하지 않는다. 최신 새 이미지의 실제 Pi 설치·물리 지갑 검증은 남아 있다.
