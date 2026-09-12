# 백업 검토 및 보강 상태

2026-09-12 보강: 선택 policy_file, root canonical 생성, 고정 UUID/instance/binary 검증, 소유자 재인증, 서비스 정지/재시작, TLS Electrum 헤더와 Core RPC health, bounded ciphertext 및 durable rollback을 구현했다. 실제 systemd/Unix API 생성·복원, 잘못된 입력 차단, health 실패 rollback, 실제 SIGKILL 복구, 비권한 TUI 재인증 PASS. 증거는 evidence/backup-hardening.json.

남은 범위: 물리 전원 차단/부팅 자동 복구, OS를 새로 기록한 뒤 기존 데이터 볼륨 재등록/identity 복원, 브라우저에서 암호화 파일 반출입, Pi/모바일 재접속. 현재 복원은 동일하게 등록된 데이터 볼륨·선택 버전으로 제한하며, 다른 볼륨/버전이나 임의 root 설정을 복원하지 않는다. 전체 백업·재해 복구 완료 아님.

## 보강 전 발견 사항 (이력)

기존 사용자 변경을 보존했고 dev11/dev12 이미지에는 포함하지 않았다. 아래는 코드 검토 결과이며 실제 공격/운영 복구 PASS를 주장하지 않는다.

- `production_specs()`가 고정 `/var/lib/justverify/config/managed.conf`를 백업한다. 실제 선택 프로필은 `/srv/justverify/data/instances/<network>/<version[-watch-only]>/managed.conf`를 사용하므로 선택된 정책을 놓칠 수 있다. root가 검증한 프로필 식별자로부터 경로를 유도해야 한다.
- 복호화 및 파일 해시 일치는 백업 내용의 신뢰성을 증명하지 않는다. `_validate_snapshot()`은 config3개와 등록 해시의 자기 일관성을 검사하지만 systemd profile drop-in의 내용을 정규 생성 결과와 대조하지 않는다. node UID가 선택한 암호로 만든 임의 백업의 root 소유 drop-in 내용을 그대로 복원하는 API를 활성화하면 권한 경계를 깨뜨릴 수 있다. 명령·User·외부 경로를 백업에서 신뢰하지 말고 고정된 profile_helper 생성 모델과 서명 검증 바이너리로 재생성/정확 대조해야 한다.
- 복원하려는 데이터 UUID와 현재 mount/instance marker/현재 바이너리·data compatibility를 쓰기 전에 검증해야 한다. 기존 Core 데이터를 다운그레이드 바이너리로 열도록 이전 active/profile을 복원해서는 안 된다.
- create는 서비스 간 동시 변경을 일괄 정지/동기화하지 않는다. 파일 하나의 변경 탐지는 있으나 여러 파일의 동일 시점 snapshot 보장은 별도 문제다. restore는 web을 계속 실행한 채 인증/원격 설정을 바꾸고 뒤늦게 restart하므로 취소된 권한/세션 및 동시 파일 갱신을 검증해야 한다.
- restore의 `committed`는 파일 일관성 기준이고 Core/electrs/Tor 및 실제 인증된 지갑 연결 health를 완료 기준으로 삼지 않는다. resume callback이 일부 시작 실패를 무시하므로 성공 보고 전에 실제 서비스를 확인해야 한다.
- Unix socket의 node UID 허용은 로그인한 소유자의 재인증을 대신하지 않는다. 기존 remote-RPC 검토·관리자 재인증과 같은 경계를 적용해야 한다.

재개 순서: root 신뢰 경계와 canonical 생성 모델→선택 프로필/UUID·동시성 보호→실제 GPG 변조·잘못된 암호·임의 drop-in 거부→격리 등록 볼륨에서 동일 identity 복원→서비스 health 및 실제 재부팅/중단 복구. mainnet 또는 기존 운영 데이터는 사용하지 않는다.
