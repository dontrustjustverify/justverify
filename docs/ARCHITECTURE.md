# 아키텍처 및 신뢰 경계

브라우저 → HTTPS 인증/Origin/세션 → 고정 TUI → 권한 제한 Unix socket → 관리 데몬 → loopback Core cookie RPC.
로컬 콘솔도 동일 TUI를 사용한다. Core, electrs, Tor, UI는 별도 비권한 서비스다. privileged helper는 허용 서비스의 제한된 작업만 실행한다.

LAN Electrum은 기기별 인증서를 사용하는 별도 비권한 TLS 서비스(50002) → 고정 localhost electrs(50001) 경로다. IPv4 사설/링크 로컬/loopback 출발만 허용하며 HTTP와 Core RPC를 전달하지 않는다. 등록 마운트/프로필 검사와 electrs 생명주기에 연결한다. Tor Electrum은 기존 별도 onion → localhost electrs 경로를 유지한다. 실제 앱 인증서 신뢰와 IPv6 지원은 별도 과제다.

데몬은 공유 수집 캐시를 보유한다. RPC 실패 시 마지막 값과 갱신 시각을 보존하되 STALE로 표시한다. 미지원 필드는 N/A다. 외부 문자열의 terminal escape 및 제어문자는 화면에 전달하지 않는다. 자격증명은 API와 진단자료에서 제외한다.

데이터 mount가 없으면 Core/electrs를 시작하지 않는다. OS 복구와 Core 데이터 형식 복구는 별개다. 설정 변경은 검증→diff→원자적 저장→필요 서비스 재시작→건강 확인 순서로 진행한다. 데이터 마이그레이션 뒤 자동 binary rollback은 금지한다.

이 문서는 목표 구조다. 실제 구현 및 검증 여부는 ACCEPTANCE.md를 따른다.
