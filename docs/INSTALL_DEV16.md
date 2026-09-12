# dev16 재설치 안내

이 버전에는 HTTP 최초 설정/로그인, 새 설정 구성, Amber BTC 돋보기 favicon, 최근 블록의 로컬 채굴 풀 추정 표시가 포함된다. 설치 이미지의 실제 검증 상태와 SHA256은 같은 버전 manifest를 기준으로 한다. 이전 dev15 원본에는 resize 문제가 있으므로 다시 기록하지 않는다.

ARM Linux 빌더에서는 기존 도구 외에 `zerofree`가 필요하다 (`sudo apt-get install zerofree`). 저장된 실행 순서는 image/build-pi.sh와 scripts/compact_factory_image.py이며, 실제 dev16 조립/후속 캐시 정리 명령은 .state/release-dev16/build.sh 및 finalize-build.sh에 보존했다. 기본 OS 패키지 버전 목록도 번들에 포함한다. apt 저장소를 시점별로 고정한 OS의 바이트 단위 재현성은 이번 빌드에서 주장하지 않는다.

현재 결과: 압축 무결성·체크섬·파일시스템 PASS. VM 데이터 확장/Core/electrs/HTTP/TUI와 별도 동일 신원 재부팅 복구는 확인했지만 Tor bootstrap/onion timeout으로 전체 시험 미통과. 실기 재검증용 개발 설치 후보이며 최종 정상작동 확인 완료 이미지가 아니다.

1. 위 결과를 확인한 뒤 실제 Pi 검증을 위해 현재 Pi를 설정의 셧다운으로 정상 종료한다.
2. Pi 전원을 분리한 뒤 지정된 NVMe를 Mac에 연결한다. 새 장치 번호와 용량·모델을 다시 확인한다. 과거의 disk 번호를 그대로 쓰지 않는다.
3. balenaEtcher에서 `.state/pi5-install/justverify-dev16-pi5-private.img`를 선택하고 해당 NVMe에 기록한다. raw SHA256은2e65e50b536c9fac6e48e8e63fcdff8b3d0d1dcfe891642bd54c87d9cbdecefe다. 기록 후 Etcher 검증을 끝까지 수행한다. 이전 기록에서 압축 입력 검증 실패가 있어 이번에는 압축 bytes와 독립 대조한 raw를 준비했다. Etcher가 전체 장치에 쓰므로 별도 포맷은 필요하지 않다.
4. 안전하게 추출한 NVMe를 Pi5에 연결하고 LAN과 전원을 연결한다. 첫 부팅에서 데이터 영역을 준비하고 고유 키를 생성한다.
5. http://justverify.local 또는 공유기가 배정한 IP로 접속한다. 새 관리자 암호와 확인 입력을 정하고 시작한다. SSH 기본 계정 justverify / justverify와 웹 관리자 암호는 별개다.
6. Core 동기화, electrs 인덱싱, 새로고침 로그인 유지, 설정 저장, 재부팅, 실제 지갑 연결을 확인한다. 이 새 이미지의 Pi5 실기 부팅을 아직 하지 않았다면 전체 정상작동 완료로 표시하지 않는다.

## 기존 데이터와 백업

이번 절차는 NVMe를 새 이미지로 다시 기록하는 설치다. 현재 NVMe의 설정과 동기화 중인 블록 데이터가 지워지며 체인은 다시 내려받는다. 이 대상의 초기화는 사용자가 지정하고 허용했다. 다른 디스크는 대상이 아니다.

재설치 전 설정 보존 위치는 Mac의 `.state/release-dev16/preflash-backup/`이다. configuration.jvb는 암호화 백업, passphrase.txt는 별도0600 복호화 암호 파일이다. 둘 다 개인 자료이며 Git·이미지·공개 배포물에 포함하지 않는다. Pi에서 생성/복호화하고 Mac에서 독립 GPG 복호화와28개 파일 해시를 대조했다. 블록체인과 지갑 개인키는 포함하지 않았다.

현재 제품의 자동 복원은 등록된 동일 볼륨/프로필의 검증된 설정 복구에 한정된다. 이번처럼 새 UUID로 생성한 볼륨에 이전 백업을 자동 적용하지 않는다. 새 볼륨으로의 설정 이전은 별도 검토가 필요하며 지원이 끝났다고 표시하지 않는다.

## 크기를 비교하는 기준

압축된 xz/zip은 다운로드 크기이고, 압축 해제된 raw IMG는 파일시스템의 여유 공간도 포함한다. dev16 raw 크기는6,444,548,096bytes이며 그 안의 root5GiB에는 업데이트와 Core 버전 파일을 위한 여유 공간이 있다. 단일 OS이고 나머지 NVMe 공간은 첫 부팅에서 노드 데이터에 배정한다. A/B OS 복사본은 없다.

배포 원본과 Pi 시험용 SSH 공개키를 넣은 개인 복사본을 구분한다. 개인 복사본에도 SSH 개인키·공통 SSH host key·웹 계정·Tor 개인키·기존 체인은 넣지 않는다. 원격 시험 공개키가 포함된 개인 복사본은 다른 사람에게 배포하지 않는다.
