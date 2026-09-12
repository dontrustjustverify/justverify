# 설정 정리·favicon·채굴 풀 표시

2026-09-12. 새 이미지 결과는 RELEASE_DEV16.md와 해당 manifest에 기록한다. 이 문서 자체는 전체 배포 완료 판정이 아니다.

## 설정 구성

일반 설정 아래 **백업 및 복원**, **문제 해결**을 배치한다. 문제 해결에는 **Core RPC 상태**와 접힌 **고급 · 저장장치 관리**를 둔다. 정상 부팅한 단일 NVMe는 다시 초기화할 필요가 없다. 별도 디스크 관리, 설치 중단 복구, 암호화 백업/복원 API 및 TUI는 유지한다. Umbrel 공식 비교와 Pi 제약은 [설정 비교](UMBREL_SETTINGS_UX.md)에 기록했다.

## 채굴 풀 식별

- 데이터: [mempool/mining-pools](https://github.com/mempool/mining-pools/tree/f678a4a620537ad7997a475ad0f14bfab1de3c8b), MIT. 원문 pools-v2.json을 변경 없이 포함했다. 해시 catalog/mining-pools-source.json, 라이선스 licenses/mining-pools/LICENSE.
- 자신의 Core에 getblockheader, getblock(hash,1), getrawtransaction(first_txid,true,hash)를 호출한다. [공식 RPC 동작](https://bitcoincore.org/en/doc/31.0.0/rpc/rawtransactions/getrawtransaction/)상 명시한 블록이 있으면 txindex 없이 조회할 수 있다. 실제 Core22~31에서도 시험했다.
- coinbase 태그와 mainnet 보상 주소로 추정한다. 둘 이상 이름이 충돌하면 임의로 하나를 선택하지 않는다. 미식별, 충돌, 조회 실패를 구분하며 태그가 채굴자 신원을 증명하지 않음을 도움말에 표시한다.
- 태그는 대소문자를 구분한 원문 바이트 문자열로 보수적으로 매칭한다. upstream README의 정규식/대소문자 무시 방식과 달라 일부 패턴은 미식별될 수 있다. 임의 문자열을 정규식으로 실행하지 않는 의도적인 차이다.
- 외부 API와 실시간 GitHub 다운로드를 사용하지 않는다. 고정 데이터는 소프트웨어 업데이트 시 갱신한다. 최신 풀이나 변경된 태그는 미식별일 수 있다.
- 같은 블록 hash는 공유 snapshot에 캐시한다. 조회 실패는 30초 뒤 재시도한다. 이전 hash를 따라 최근6개를 읽으므로 reorg 때 분기를 섞지 않는다. 모든 거래를 상세 디코딩하지 않는다.
- 격리 regtest에서 실제 coinbase와 proof of work를 만들어 submitblock으로 수용시킨 뒤 수집 결과를 검사한다. 이 시험의 Luxor/Noderunners 태그는 시험 코드가 넣은 문자열이며 해당 회사가 실제 regtest 블록을 채굴했다는 뜻이 아니다.

## favicon과 크기

scripts/build_favicon.py는 폰트에 의존하지 않는 독립 SVG 경로와 ICO(16/32/48), Apple PNG(180)를 만든다. Amber #FFB000 돋보기 안에 BTC를 배치했다. 이미지 생성 서비스나 Umbrel 자산을 사용하지 않았다.

raw IMG에는 빈 파일시스템 공간도 포함된다. Umbrel의 약1.4GB zip과는 압축 파일 크기로 비교해야 한다. 기존 JustVerify 축소본은798,050,496bytes xz /6,444,548,096bytes raw였다. dev16 원본은577,803,744bytes(약551MiB) xz, raw6,444,548,096bytes다. root 실제 파일/디렉터리 할당량은1,793,581,056bytes이며 나머지는 업데이트·버전 설치용 여유 공간이다. Qt약40MiB와 upstream 시험 바이너리약94MiB, APT/pip 캐시 및 추가 APT 인덱스 캐시137,674,752bytes를 제거했다. 기본 OS의 gcc/개발 헤더/로케일 일부는 남아 있다. OS 패키지 의존성을 확인하지 않고 파일만 더 삭제하지 않았다. 사용자 제시 Umbrel1.4GB ZIP의 실제 파일을 분석한 것은 아니다.

새 headless 이미지에서는 Bitcoin Qt와 upstream libexec 시험 실행파일을 제외한다. 서명 검증 원본과 개발 테스트는 보존하며 daemon/CLI/보조 유틸리티 바이트는 변경하지 않는다. apt/pip 캐시 제거 뒤 unmounted disposable factory ext4의 빈 공간을 zerofree로 정리한다. OS 펌웨어·드라이버·저작권 고지는 임의 제거하지 않는다. OS는 한 벌이며 A/B 설치를 추가하지 않는다.

## 실행 증거와 제한

- .state/release-dev16/dashboard-live.log: 실제 Core31.1, 최근6블록 연결·reorg·PTY120/80/42·중단 stale PASS.
- miner-live-mac-retest.json, miner-live-linux.json, miner-core-matrix*.log: 실제 submitblock, 태그/미식별/충돌, txindex=0, 캐시, reorg 검사. 최초 fixture의 BIP34 높이 인코딩 실패는 miner-live-mac.err에 보존했다. 합의 검증을 완화하지 않고 시험 블록 인코딩을 수정했다.
- http-with-favicon.log: 실제 HTTP/TLS 서버의 favicon 경로/MIME/바이트, 최초 설정·로그인·새로고침 세션·rate limit PASS.
- pi-live-blocks.json: 실제 Pi5 mainnet IBD 중 관측. 새 소스 배포 후 F2Pool/BitFury 등의 추정 이름 확인. mainnet 상태 변경 RPC는 시험에 사용하지 않았다.
- pi-settings-full.png, pi-overview-mobile.png: 실제 Pi 코드와 Core를 연결한 별도 임시 웹 계정. 소유자 암호·설정은 변경하지 않았다.1200/390px 배치와 새로고침 로그인 유지 확인.
- 신규 이미지의 실제 Pi 부팅, 물리 휴대폰 카메라/지갑, 전체 체인 동기화, 최종 릴리스 기준은 별도 검증해야 한다.
