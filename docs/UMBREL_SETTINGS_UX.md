# 설정 보조 메뉴 필요성 비교 — 2026-09-12

사용자 요청은 메뉴 필요성 비교다. 이번에는 실행 코드와 Pi 메뉴를 변경하지 않았다. JustVerify 기준 소스 c745c4e, Umbrel 공식 소스 bfa79ed24031b0065dd2f810411d58b82af1b95e(2026-09-03), 현재 공식 지원 문서를 비교했다. 첨부된 umbrelOS1.2.1 화면을 현행 모든 버전의 기능 목록으로 간주하지 않는다.

| 항목 | Umbrel 근거 | 현재 JustVerify | 판단 |
|---|---|---|---|
| 저장장치 | 최신 Raspberry Pi 안내: 기록한 드라이브에 OS·앱·데이터 저장, Storage Manager/FailSafe 제공 안 함. 다른 하드웨어용 Storage Manager와 구별 | storage_ui.rs는 inventory뿐 아니라 새 디스크 포맷·마운트·중단 복구·profile 준비까지 포함 | 한 NVMe Pi5 기본 사용에는 상시 설치 탭 불필요. 사용량·여유 공간은 기기 정보에, 고급 디스크 작업은 문제 해결/고급 영역에 유지 |
| 초기 설정 | routes/onboarding과 settings가 분리되어 있고 설치/초기 복원 흐름 제공 | 최신 /node-start 자동 최초 등록과 기존 storage prepare 화면이 병존 | 소유자/노드 준비가 끝나면 상시 메뉴에서 제거하는 편이 타당. 필요한 최초 부팅·실패 상태에만 표시 |
| 백업·복구 | Settings > Backups에서 백업 설정, 복구는 Settings > Backups > Restore 또는 onboarding | 암호화된 계정·설정·인증서·Tor identity·RPC 연결정보 백업; 전체 chain은 제외 | 일반 노드 기동의 전제는 아니지만 운영/이전/장애 복구 기능으로 유지. 설정 페이지 안의 ‘백업 및 복원’ 한 항목으로 정리. 복구를 별도 상시 탭으로 분리할 이유 없음 |
| 서비스 진단 | Settings > Troubleshoot에서 OS/앱 로그 조회·다운로드 | src/tui.rs page l은 수집기 RPC 항목별 error/updated 문자열이 주 기능. 서비스 전체 로그 진단은 아님 | 필요할 때 쓰는 ‘문제 해결’로 이름/위치 조정. 일반 설정 아래 보조 링크/펼침으로 두고 정상 화면에 항상 큰 탭으로 표시할 필요 없음 |

권고 구조: 설정 본문(기기 정보·계정·색상·언어·Tor) 아래에 ‘백업 및 복원’, ‘문제 해결’ 진입점을 둔다. 기본 설정의 상단 서브탭은 생략하고, 초기 설정은 최초 부팅 조건부 화면으로, 고급 저장장치 복구는 문제 해결 안으로 이동한다. 기존 복구 기능·검증 기준은 보존한다. 이는 변경 권고이며 현재 배포 UI 변경 완료를 의미하지 않는다.

근거:
- https://github.com/getumbrel/umbrel/blob/bfa79ed24031b0065dd2f810411d58b82af1b95e/packages/ui/src/routes/settings/index.tsx
- 같은 commit의 settings/_components/settings-taxonomy.ts 및 routes/onboarding/index.tsx·create-account.tsx·restore.tsx 경로
- https://umbrel.com/support/install-umbrelos-on-your-own-hardware/installing-umbrelos-on-raspberry-pi (2026-09-02 갱신)
- https://umbrel.com/support/storage/managing-your-storage (2026-09-02 갱신)
- https://umbrel.com/support/backups-and-recovery/backing-up-your-data (2026-07-01 갱신)
- https://umbrel.com/support/backups-and-recovery/restoring-from-a-backup (2026-02-22 갱신)
- https://umbrel.com/support/troubleshooting/viewing-logs (2026-02-23 갱신)

읽기 전용 소스 조사이며 코드·자산 재사용 없음. 실행 테스트 대상 코드 변경 없음.
