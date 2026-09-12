# dev16 설치 후보와 검증 결과

이 빌드는 요청한 설정 구성, Amber BTC 돋보기 favicon, 최근 블록의 채굴 풀 추정 표시를 포함한다. 전체 S0–S4 정상작동 확인 완료 또는 공개 배포 후보는 아니다. 설치 절차는 [dev16 안내](INSTALL_DEV16.md), 상세 기능·라이선스는 [구현 기록](MINER_AND_IMAGE_DEV16.md)을 따른다.

| 항목 | 결과 |
|---|---|
| 설정 | 일반 설정 아래 백업 및 복원 / 문제 해결, 고급 저장장치 관리 접힘. 기존 복구 API/TUI 유지 |
| favicon | 독립 제작 SVG, ICO16/32/48, Apple PNG180. #FFB000 돋보기 안 BTC |
| 최근 블록 | 블록 번호 오른쪽 풀 이름. 로컬 coinbase 태그/보상 주소 기반 추정이며 미식별·충돌·조회 실패 구분 |
| 배포 원본 크기 |577,803,744bytes xz(약578MB /551MiB). raw6,444,548,096bytes |
| 실제 root 파일 할당량 |1,793,581,056bytes. OS 한 벌, boot/root/data. 블록체인·시험 계정 없음 |
| 줄인 내용 | Qt, upstream 시험 실행파일, APT/pip 다운로드·인덱스 캐시, 삭제 파일이 남긴 빈 블록 정리 |

사용자가 제시한 Umbrel 약1.4GB ZIP과 비교할 값은578MB xz다. raw 크기는 여유 공간을 포함하므로 같은 기준이 아니다. xz와 zip의 압축 방식도 다르며 해당 Umbrel 파일 내부를 직접 분석했다고 주장하지 않는다. 기본 OS의 일부 개발 패키지·헤더·로케일은 남아 있다.

## 출처와 버전

- 이미지 조립: b3c5f5b46d1a42042cfd675cc2130aa0bde4e449. Rust 런타임: abfce56, SHA2568cfa9b71ac44586ad7c10c846adfab2acd3631200efa11f0ff11d6b203c7fd1c. 후속 검증기19a6335는 가상 시험 디스크 크기만 추가 지정한다.
- Raspberry Pi OS Lite64 2026-06-18, 고정 base SHA256acff736ca7945e3b305f07cda4abdb870910e12634991da69783611756e381b3. OS 패키지 목록을 번들에 포함한다.
- Bitcoin Core31.1 공식 서명·체크섬 검증 ARM64 바이너리, electrs0.11.1 commit35216c6d30148be8e6763d913d437330f431fc03, Tor0.4.9.11, aiohttp3.13.3, qrcode8.2, xterm6.0.0.
- Umbrel 설정 참고: bfa79ed24031b0065dd2f810411d58b82af1b95e. 소스·아이콘 재사용 없음. [항목별 비교](UMBREL_SETTINGS_UX.md).
- 채굴 풀 자료: mempool/mining-pools f678a4a620537ad7997a475ad0f14bfab1de3c8b, MIT. 원본 자료와 라이선스·출처 고지를 포함한다.

## 실행한 검증

- 실제 Core22.0/22.1/23.2/24.2/25.2/26.2/27.2/28.2/28.4/29.3/29.4/30.2/30.3/31.1 regtest에서 유효한 coinbase/PoW를 submitblock으로 수용시켜 태그·미식별·충돌·캐시·reorg·txindex 미사용 확인 PASS. 최종 ARM 바이너리의31.1 재시험 PASS. [기록](evidence/miner-attribution-live.json).
- 실제 Core31.1 대시보드·6개 연결 블록·reorg·프로세스 중단 STALE·PTY120/80/42 PASS. cargo test --locked PASS; 별도 환경이 필요한 ignored 항목은 이 실행의 통과 수에 포함하지 않는다.
- 실제 HTTP/TLS 서버의 최초 등록·로그인·refresh 세션·CSRF·시도 제한·favicon MIME/바이트 PASS. 실제 Pi Core와 연결한 임시 계정에서 설정/백업/진단/보호된 저장장치 이동,1200/390px 배치 PASS. [Pi UI 기록](evidence/dev16-ui-pi.json). 실제 휴대폰 시험은 아니다.
- 이미지 전체 offline 검사 PASS: 파일 hash, 서비스·권한, 기기 신원 부재, Core/electrs 실제 실행, Python imports, filesystem/GPT. Mac xz 무결성·hash PASS.
- 개인 설치 복사본의 실제 root 공개키 SSH와 justverify/justverify 암호 SSH PASS. 개인키·기존 관리자 암호·Tor 키는 넣지 않았다.
- 재설치 전 Pi의28개 설정 파일을 암호화 백업하고 Mac에서 독립 복호화·각 파일 hash 대조 PASS. 실제 새 볼륨 복원은 하지 않았다.
- VM 첫 시도는 확장할 여유 공간이 없는 가상 디스크의 data 용량 assertion에서 FAIL.12GiB 가상 디스크 재시험은 실제 제품의 데이터 확장과 Core/electrs/TLS·TUI·QR에 통과했지만 Tor onion timeout으로 전체 FAIL. 다음 새 복사본도 bootstrap62% timeout으로 FAIL. 세 기록을 보존한다.
- 동일 실패 이미지의 신원·데이터를 유지한 별도 복구/실제 재부팅 검사: UUID·tip·인덱스·정책·SSH/TLS/admin 신원·watch-only·PSBT·HTTP 로그인/세션/favicon·기본 언어·TUI PASS. Tor는100% 준비 후에도 onion 요청 timeout이며 독립 builder Tor client에서도 동일. 기기 내부 실제 RPC gateway는200/regtest다. 근본 원인은 미확정이며 전체 결과 PARTIAL. [복구 증거](evidence/image-dev16-recovery.json). 초기 Tor 부팅 시험을 통과로 바꾼 결과가 아니다.

공개 testnet의 이전 동기화/거래/RPC 검증은 기존 [인수 기록](ACCEPTANCE.md) 및 네트워크별 증거를 따른다. 이번 UI·이미지 변경 시험에서 공개 testnet 거래를 새로 생성하지 않았으며 regtest 태그 시험에 실제 자금을 사용하지 않았다. Pi mainnet은 기존 IBD 중 데이터를 읽기만 했고, 이 빌드가 전체 동기화를 마쳤다고 표시하지 않는다.

## 남은 검증

VM Tor bootstrap/onion 시간 초과 해결·재검증, 새 이미지의 Etcher 기록·검증, Pi5 펌웨어/NVMe 실제 첫 부팅·재부팅, 전체 Core IBD 종료와 electrs tip 일치, 실제 모바일 지갑/카메라,24시간 운영이 남아 있다. 전체 정책 의미·단일 OS 업데이트 실패 복구·새 UUID 재설치 복원·OS 바이트 재현성 및 전체 릴리스 고지/소스 제공 검토도 완료되지 않았다. 실험용 로컬 서명은 파일 무결성을 검증하며 이 인수 기준을 대신하지 않는다.
