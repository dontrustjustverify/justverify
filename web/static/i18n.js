'use strict';
const I18n=(()=>{
const messages={
 "설정": {
  "en": "Settings",
  "ja": "設定"
 },
 "일반": {
  "en": "General",
  "ja": "一般"
 },
 "로그아웃": {
  "en": "Log out",
  "ja": "ログアウト"
 },
 "비트코인코어": {
  "en": "Bitcoin Core",
  "ja": "Bitcoin Core"
 },
 "현황": {
  "en": "Overview",
  "ja": "概要"
 },
 "버전 변경": {
  "en": "Change version",
  "ja": "バージョン変更"
 },
 "버전": {
  "en": "Version",
  "ja": "バージョン"
 },
 "Mempool · 네트워크 설정": {
  "en": "Mempool · Network",
  "ja": "Mempool・ネットワーク"
 },
 "Electrs 연결": {
  "en": "Electrs connection",
  "ja": "Electrs接続"
 },
 "RPC 연결 관리": {
  "en": "RPC connections",
  "ja": "RPC接続管理"
 },
 "저장장치 · 초기 설정": {
  "en": "Storage · Setup",
  "ja": "ストレージ・初期設定"
 },
 "백업 · 복구": {
  "en": "Backup · Restore",
  "ja": "バックアップ・復元"
 },
 "서비스 진단": {
  "en": "Diagnostics",
  "ja": "サービス診断"
 },
 "연결 중": {
  "en": "Connecting",
  "ja": "接続中"
 },
 "노드 요약": {
  "en": "Node summary",
  "ja": "ノード概要"
 },
 "네트워크 · Mempool": {
  "en": "Network · Mempool",
  "ja": "ネットワーク・Mempool"
 },
 "최근 블록": {
  "en": "Recent blocks",
  "ja": "最近のブロック"
 },
 "연결된 피어": {
  "en": "Connected peers",
  "ja": "接続中のピア"
 },
 "시스템 · 서비스": {
  "en": "System · Services",
  "ja": "システム・サービス"
 },
 "수수료": {
  "en": "Fees",
  "ja": "手数料"
 },
 "네트워크": {
  "en": "Network",
  "ja": "ネットワーク"
 },
 "블록 / 헤더": {
  "en": "Blocks / Headers",
  "ja": "ブロック / ヘッダー"
 },
 "검증 진행률": {
  "en": "Verification progress",
  "ja": "検証進捗"
 },
 "초기 동기화 (IBD)": {
  "en": "Initial sync (IBD)",
  "ja": "初期同期 (IBD)"
 },
 "대기": {
  "en": "Waiting",
  "ja": "待機中"
 },
 "진행 중": {
  "en": "In progress",
  "ja": "進行中"
 },
 "완료": {
  "en": "Complete",
  "ja": "完了"
 },
 "체인 용량": {
  "en": "Chain size",
  "ja": "チェーン容量"
 },
 "기기 가동 시간": {
  "en": "Device uptime",
  "ja": "稼働時間"
 },
 "들어옴 / 나감": {
  "en": "Inbound / Outbound",
  "ja": "受信 / 送信"
 },
 "수신 / 송신": {
  "en": "Received / Sent",
  "ja": "受信量 / 送信量"
 },
 "미확인 거래": {
  "en": "Unconfirmed transactions",
  "ja": "未承認取引"
 },
 "Mempool 크기": {
  "en": "Mempool size",
  "ja": "Mempoolサイズ"
 },
 "추정 불가": {
  "en": "Unavailable",
  "ja": "推定不可"
 },
 "6블록 이내 추정": {
  "en": "Estimate within 6 blocks",
  "ja": "6ブロック以内の推定"
 },
 "Mempool 최저": {
  "en": "Mempool minimum",
  "ja": "Mempool最低値"
 },
 "Relay 최저": {
  "en": "Relay minimum",
  "ja": "中継最低値"
 },
 "메모리": {
  "en": "Memory",
  "ja": "メモリ"
 },
 "데이터 여유 공간": {
  "en": "Data space available",
  "ja": "データ空き容量"
 },
 "인덱스 높이": {
  "en": "Index height",
  "ja": "インデックス高"
 },
 "연결 대기 · Core 초기 동기화 중": {
  "en": "Waiting · Core initial sync",
  "ja": "待機中・Core初期同期中"
 },
 "현재 연결이 끊겼습니다. 아래 값은 마지막 수집 데이터입니다.": {
  "en": "Disconnected. Values below are the last collected data.",
  "ja": "接続が切れました。以下は最後に取得したデータです。"
 },
 "Core에 연결하는 중입니다. 초기 시작 상태는 위 안내에서 확인하세요.": {
  "en": "Connecting to Core. Startup status is shown above.",
  "ja": "Coreに接続中です。起動状態は上の案内をご確認ください。"
 },
 "이전 블록 정보 · 현재 tip 확인 불가": {
  "en": "Previous block data · current tip unavailable",
  "ja": "以前のブロック情報・現在のtipは未確認"
 },
 "첫 블록 정보를 기다리고 있습니다.": {
  "en": "Waiting for the first block data.",
  "ja": "最初のブロック情報を待っています。"
 },
 "현재 연결된 피어가 없습니다.": {
  "en": "No peers connected.",
  "ja": "接続中のピアはありません。"
 },
 "Core 연결 후 피어가 표시됩니다.": {
  "en": "Peers will appear when Core connects.",
  "ja": "Core接続後にピアを表示します。"
 },
 "○ 연결 끊김": {
  "en": "○ Disconnected",
  "ja": "○ 切断"
 },
 "○ 연결 확인 필요": {
  "en": "○ Check connection",
  "ja": "○ 接続を確認"
 },
 "로컬 네트워크": {
  "en": "Local network",
  "ja": "ローカルネットワーク"
 },
 "지갑과 이 노드가 같은 네트워크에 있으면 로컬 네트워크를 선택하세요.": {
  "en": "Choose Local network when your wallet and node share a network.",
  "ja": "ウォレットとノードが同じネットワークの場合はローカルネットワークを選択してください。"
 },
 "연결 주소": {
  "en": "Connection address",
  "ja": "接続アドレス"
 },
 "주소 QR · 암호 포함 없음": {
  "en": "Address QR · no password",
  "ja": "アドレスQR・パスワードなし"
 },
 "QR 이미지 저장": {
  "en": "Save QR image",
  "ja": "QR画像を保存"
 },
 "접속 방식": {
  "en": "Connection type",
  "ja": "接続方式"
 },
 "프로토콜": {
  "en": "Protocol",
  "ja": "プロトコル"
 },
 "포트": {
  "en": "Port",
  "ja": "ポート"
 },
 "사용 · 지갑에서 SSL/TLS 선택": {
  "en": "Enabled · select SSL/TLS in wallet",
  "ja": "有効・ウォレットでSSL/TLSを選択"
 },
 "사용 안 함 · Tor 전송": {
  "en": "Disabled · transport through Tor",
  "ja": "無効・Tor経由の通信"
 },
 "같은 LAN의 지갑에서 SSL/TLS를 선택하고 기기 인증서를 확인하세요.": {
  "en": "Select SSL/TLS in your LAN wallet and verify the device certificate.",
  "ja": "同じLANのウォレットでSSL/TLSを選択し、証明書を確認してください。"
 },
 "지갑에서 Tor를 활성화하거나 Tor SOCKS 프록시를 설정하세요.": {
  "en": "Enable Tor or configure a Tor SOCKS proxy in your wallet.",
  "ja": "ウォレットでTorまたはTor SOCKSプロキシを設定してください。"
 },
 "연결 정보를 확인하는 중…": {
  "en": "Checking connection details…",
  "ja": "接続情報を確認中…"
 },
 "Core 초기 동기화 중 · electrs와 지갑 연결 준비는 동기화가 끝난 뒤 확인하세요.": {
  "en": "Core initial sync · check electrs and wallet readiness after sync finishes.",
  "ja": "Core初期同期中・同期完了後にelectrsとウォレットの接続状態を確認してください。"
 },
 "electrs 인덱싱·연결 대기 · 아래 주소는 설정된 주소이며, 아직 지갑 연결 준비가 확인되지 않았습니다.": {
  "en": "electrs indexing or connection pending · configured addresses below are not yet confirmed ready.",
  "ja": "electrsの索引作成・接続待機中。以下の設定アドレスは接続準備が未確認です。"
 },
 "연결 서비스 실행 중 · 주소 또는 QR 이미지를 사용하세요. 지갑에서 동기화 상태를 확인하세요.": {
  "en": "Connection service running · use the address or QR image and check sync in your wallet.",
  "ja": "接続サービス稼働中。アドレスまたはQR画像を使い、ウォレットで同期状態を確認してください。"
 },
 "연결 대기 · 아래는 기기에 설정된 주소입니다. 연결 서비스를 시작해야 사용할 수 있습니다.": {
  "en": "Connection pending · the configured address needs a running connection service.",
  "ja": "接続待機中。以下の設定アドレスを使用するには接続サービスの起動が必要です。"
 },
 "디바이스": {
  "en": "Device",
  "ja": "デバイス"
 },
 "로컬 IP": {
  "en": "Local IP",
  "ja": "ローカルIP"
 },
 "확인 불가": {
  "en": "Unavailable",
  "ja": "確認不可"
 },
 "버전 정보 없음": {
  "en": "Version unavailable",
  "ja": "バージョン情報なし"
 },
 "재시작": {
  "en": "Restart",
  "ja": "再起動"
 },
 "시스템 종료": {
  "en": "Shut down",
  "ja": "シャットダウン"
 },
 "계정명, 패스워드 변경": {
  "en": "Account name and password",
  "ja": "アカウント名・パスワード"
 },
 "계정명 변경": {
  "en": "Change name",
  "ja": "アカウント名を変更"
 },
 "패스워드 변경": {
  "en": "Change password",
  "ja": "パスワードを変更"
 },
 "멤풀": {"en":"Mempool","ja":"メンプール"},
 "글자색 선택": {
  "en": "Text color",
  "ja": "文字色"
 },
 "글자, 테두리와 버튼에 함께 적용됩니다.": {
  "en": "Applies to text, borders and buttons.",
  "ja": "文字、枠線、ボタンに適用します。"
 },
 "언어선택": {
  "en": "Language",
  "ja": "言語"
 },
 "저장되었습니다.": {
  "en": "Saved.",
  "ja": "保存しました。"
 },
 "켜짐": {
  "en": "On",
  "ja": "オン"
 },
 "꺼짐": {
  "en": "Off",
  "ja": "オフ"
 },
 "Tor Browser로 외부에서 관리 화면에 접속합니다.": {
  "en": "Access this dashboard remotely using Tor Browser.",
  "ja": "Tor Browserで外部から管理画面に接続します。"
 },
 "Tor Browser에서 이 주소를 열고 관리자 암호로 로그인하세요.": {
  "en": "Open this address in Tor Browser and sign in with your admin password.",
  "ja": "Tor Browserでこのアドレスを開き、管理者パスワードでログインしてください。"
 },
 "Tor 관리 화면 주소": {
  "en": "Tor dashboard address",
  "ja": "Tor管理画面アドレス"
 },
 "Tor 설정이 저장값과 다릅니다. 토글을 다시 적용하세요.": {
  "en": "Tor state differs from the saved setting. Apply the toggle again.",
  "ja": "Torの状態が保存値と異なります。設定を再適用してください。"
 },
 "기기 상태를 갱신하지 못했습니다.": {
  "en": "Could not refresh device status.",
  "ja": "デバイス状態を更新できませんでした。"
 },
 "취소": {
  "en": "Cancel",
  "ja": "キャンセル"
 },
 "저장": {
  "en": "Save",
  "ja": "保存"
 },
 "적용": {
  "en": "Apply",
  "ja": "適用"
 },
 "새 계정명": {
  "en": "New account name",
  "ja": "新しいアカウント名"
 },
 "현재 암호": {
  "en": "Current password",
  "ja": "現在のパスワード"
 },
 "새 암호 (12자 이상)": {
  "en": "New password (12+ characters)",
  "ja": "新しいパスワード（12文字以上）"
 },
 "새 암호 확인": {
  "en": "Confirm new password",
  "ja": "新しいパスワードの確認"
 },
 "웹 관리자 암호를 변경합니다. SSH 암호는 별개입니다. 변경 후 모든 브라우저에서 다시 로그인합니다.": {
  "en": "Changes the web admin password. SSH is separate. All browser sessions will need to sign in again.",
  "ja": "Web管理者パスワードを変更します。SSHは別です。変更後、全ブラウザで再ログインが必要です。"
 },
 "암호가 변경되었습니다. 새 암호로 로그인하세요.": {
  "en": "Password changed. Sign in with your new password.",
  "ja": "パスワードを変更しました。新しいパスワードでログインしてください。"
 },
 "기기를 재시작할까요?": {
  "en": "Restart this device?",
  "ja": "デバイスを再起動しますか？"
 },
 "기기를 종료할까요?": {
  "en": "Shut down this device?",
  "ja": "デバイスを終了しますか？"
 },
 "Core와 electrs를 안전하게 종료한 뒤 재부팅합니다. 잠시 후 다시 접속하세요.": {
  "en": "Core and electrs will stop cleanly before rebooting. Reconnect shortly.",
  "ja": "Coreとelectrsを安全に停止して再起動します。しばらくしてから再接続してください。"
 },
 "Core와 electrs를 안전하게 종료합니다. 다시 켜려면 기기의 전원을 조작해야 합니다.": {
  "en": "Core and electrs will stop cleanly. You will need to power the device on to use it again.",
  "ja": "Coreとelectrsを安全に停止します。再使用にはデバイスの電源操作が必要です。"
 },
 "Tor 원격 접속 켜기": {
  "en": "Enable remote Tor access",
  "ja": "Torリモート接続を有効化"
 },
 "Tor 원격 접속 끄기": {
  "en": "Disable remote Tor access",
  "ja": "Torリモート接続を無効化"
 },
 "관리자 암호를 아는 사용자가 Tor Browser로 접속할 수 있습니다.": {
  "en": "Users with the admin password can connect through Tor Browser.",
  "ja": "管理者パスワードを知るユーザーがTor Browserから接続できます。"
 },
 "Tor 브라우저 연결이 종료됩니다. 로컬 네트워크에서 계속 접속할 수 있습니다.": {
  "en": "Tor browser connections will close. Local network access remains available.",
  "ja": "Torブラウザ接続を終了します。ローカルネットワークからは接続できます。"
 },
 "재시작 중입니다. 잠시 후 새로고침하세요.": {
  "en": "Restarting. Refresh after the device comes back online.",
  "ja": "再起動中です。起動後に再読み込みしてください。"
 },
 "시스템 종료 중입니다. 기기가 완전히 꺼진 뒤 전원을 분리하세요.": {
  "en": "Shutting down. Wait until the device stops before unplugging power.",
  "ja": "終了中です。完全に停止してから電源を外してください。"
 },
 "현재 암호가 맞지 않습니다.": {
  "en": "Current password is incorrect.",
  "ja": "現在のパスワードが違います。"
 },
 "설정 값을 확인하고 다시 시도하세요.": {
  "en": "Check your settings and try again.",
  "ja": "設定値を確認して再試行してください。"
 },
 "기기 관리 서비스에 연결하지 못했습니다.": {
  "en": "Cannot reach the device management service.",
  "ja": "デバイス管理サービスに接続できません。"
 },
 "처음 시작하기": {
  "en": "Get started",
  "ja": "はじめに"
 },
 "다시 오셨군요": {
  "en": "Welcome back",
  "ja": "おかえりなさい"
 },
 "관리자 암호를 정해 주세요": {
  "en": "Create your admin password",
  "ja": "管理者パスワードを設定"
 },
 "노드에 로그인": {
  "en": "Sign in to your node",
  "ja": "ノードにログイン"
 },
 "앞으로 이 노드에 접속할 때 사용할 암호입니다.": {
  "en": "Use this password to sign in to your node.",
  "ja": "今後このノードに接続するためのパスワードです。"
 },
 "최초 설정 때 만든 관리자 암호를 입력하세요.": {
  "en": "Enter the admin password you created during setup.",
  "ja": "初期設定時の管理者パスワードを入力してください。"
 },
 "새 관리자 암호": {
  "en": "New admin password",
  "ja": "新しい管理者パスワード"
 },
 "관리자 암호": {
  "en": "Admin password",
  "ja": "管理者パスワード"
 },
 "시작하기": {
  "en": "Get started",
  "ja": "始める"
 },
 "로그인": {
  "en": "Sign in",
  "ja": "ログイン"
 },
 "12자 이상 입력하세요. SSH 로그인 암호와는 별개입니다.": {
  "en": "Use at least 12 characters. This is separate from the SSH password.",
  "ja": "12文字以上入力してください。SSHのパスワードとは別です。"
 },
 "위에서 정한 암호를 한 번 더 입력하세요.": {
  "en": "Enter your new password again.",
  "ja": "新しいパスワードをもう一度入力してください。"
 },
 "노드 시작 상태 확인 중…": {
  "en": "Checking node startup…",
  "ja": "ノードの起動状態を確認中…"
 },
 "노드 시작 다시 시도": {
  "en": "Retry node startup",
  "ja": "ノード起動を再試行"
 },
 "노드를 시작했습니다. 네트워크 연결과 블록 동기화가 진행됩니다.": {
  "en": "Node started. Network connections and block sync are starting.",
  "ja": "ノードを起動しました。ネットワーク接続とブロック同期を開始します。"
 },
 "로그인이 만료되었습니다. 다시 로그인하세요.": {
  "en": "Session expired. Please sign in again.",
  "ja": "セッションが切れました。再ログインしてください。"
 },
 "현재 설정을 불러오는 중…": {
  "en": "Loading current settings…",
  "ja": "現在の設定を読み込み中…"
 },
 "들어오는 연결": {
  "en": "Incoming connections",
  "ja": "受信接続"
 },
 "나가는 연결": {
  "en": "Outgoing connections",
  "ja": "送信接続"
 },
 "Clearnet 연결에 Tor 사용": {
  "en": "Route clearnet through Tor",
  "ja": "ClearnetをTor経由にする"
 },
 "블록만 수신": {
  "en": "Receive blocks only",
  "ja": "ブロックのみ受信"
 },
 "재시작 후 Mempool 유지": {
  "en": "Persist mempool on restart",
  "ja": "再起動後もMempoolを保持"
 },
 "Mempool 메모리 상한": {
  "en": "Mempool memory limit",
  "ja": "Mempoolメモリ上限"
 },
 "거래 보관 시간": {
  "en": "Transaction retention",
  "ja": "取引保持時間"
 },
 "최소 전파 수수료": {
  "en": "Minimum relay fee",
  "ja": "最小中継手数料"
 },
 "거래 교체 추가 수수료": {
  "en": "Incremental replacement fee",
  "ja": "取引置換追加手数料"
 },
 "Dust 기준 수수료": {
  "en": "Dust relay fee",
  "ja": "Dust基準手数料"
 },
 "데이터베이스 캐시": {
  "en": "Database cache",
  "ja": "データベースキャッシュ"
 },
 "최대 피어 수": {
  "en": "Maximum peers",
  "ja": "最大ピア数"
 },
 "하루 업로드 한도": {
  "en": "Daily upload limit",
  "ja": "1日の送信上限"
 },
 "데이터 출력 전파": {
  "en": "Relay data outputs",
  "ja": "データ出力の中継"
 },
 "데이터 출력 크기": {
  "en": "Data output size",
  "ja": "データ出力サイズ"
 },
 "전체 거래 인덱스": {
  "en": "Full transaction index",
  "ja": "全取引インデックス"
 },
 "블록 필터 인덱스": {
  "en": "Block filter index",
  "ja": "ブロックフィルターインデックス"
 },
 "피어에 블록 필터 제공": {
  "en": "Serve block filters",
  "ja": "ブロックフィルター提供"
 },
 "피어 Bloom 필터": {
  "en": "Peer Bloom filters",
  "ja": "ピアBloomフィルター"
 },
 "로컬 REST API": {
  "en": "Local REST API",
  "ja": "ローカルREST API"
 },
 "Bare multisig 전파": {
  "en": "Relay bare multisig",
  "ja": "Bare multisig中継"
 },
 "비공개 거래 브로드캐스트": {
  "en": "Private transaction broadcast",
  "ja": "プライベート取引送信"
 },
 "내장 ASMAP 사용": {
  "en": "Use embedded ASMAP",
  "ja": "内蔵ASMAPを使用"
 },
 "피어 차단 시간": {
  "en": "Peer ban duration",
  "ja": "ピアのブロック期間"
 },
 "연결 시간 제한": {
  "en": "Connection timeout",
  "ja": "接続タイムアウト"
 },
 "피어 응답 대기": {
  "en": "Peer response timeout",
  "ja": "ピア応答タイムアウト"
 },
 "수신 버퍼": {
  "en": "Receive buffer",
  "ja": "受信バッファ"
 },
 "송신 버퍼": {
  "en": "Send buffer",
  "ja": "送信バッファ"
 },
 "Mempool · 수수료": {
  "en": "Mempool · Fees",
  "ja": "Mempool・手数料"
 },
 "자원 · 인덱스": {
  "en": "Resources · Indexes",
  "ja": "リソース・インデックス"
 },
 "고급": {
  "en": "Advanced",
  "ja": "詳細"
 },
 "Core 옵션 설명": {
  "en": "Core option details",
  "ja": "Coreオプションの説明"
 },
 "기본값 사용": {
  "en": "Use default",
  "ja": "既定値を使用"
 },
 "기본값으로": {
  "en": "Reset to default",
  "ja": "既定値に戻す"
 },
 "이 버전·네트워크에서는 변경 불가": {
  "en": "Not editable on this version/network",
  "ja": "このバージョン・ネットワークでは変更不可"
 },
 "변경 내용 확인": {
  "en": "Review changes",
  "ja": "変更内容を確認"
 },
 "변경한 값은 아직 적용되지 않았습니다. 변경 내용 확인 후 저장하세요.": {
  "en": "Changes are not applied yet. Review and save them.",
  "ja": "変更は未適用です。内容を確認して保存してください。"
 },
 "이전 패치 버전까지 보기": {
  "en": "Show older patch releases",
  "ja": "以前のパッチバージョンも表示"
 },
 "공식 릴리스 안내": {
  "en": "Official release notes",
  "ja": "公式リリース情報"
 },
 "Bitcoin 네트워크": {
  "en": "Bitcoin network",
  "ja": "Bitcoinネットワーク"
 },
 "RPC 지갑 연동용 watch-only 모드": {
  "en": "Watch-only mode for RPC wallets",
  "ja": "RPCウォレット用watch-onlyモード"
 },
 "현재 사용 중인 버전과 모드입니다.": {
  "en": "This version and mode are currently active.",
  "ja": "現在使用中のバージョンとモードです。"
 },
 "검증된 바이너리 다운로드": {
  "en": "Download verified binary",
  "ja": "検証済みバイナリを取得"
 },
 "이 버전으로 변경 내용 확인": {
  "en": "Review this version change",
  "ja": "このバージョンへの変更を確認"
 },
 "공식 유지보수 지원 종료": {
  "en": "Official maintenance ended",
  "ja": "公式保守サポート終了"
 },
 "공식 안정 릴리스": {
  "en": "Official stable release",
  "ja": "公式安定版"
 },
 "다운로드됨": {
  "en": "Downloaded",
  "ja": "取得済み"
 },
 "다운로드 필요": {
  "en": "Download required",
  "ja": "ダウンロードが必要"
 },
 "적용 전 확인": {
  "en": "Review before applying",
  "ja": "適用前の確認"
 },
 "저장하고 적용": {
  "en": "Save and apply",
  "ja": "保存して適用"
 },
 "설정 저장·서비스 재시작·상태 확인을 마쳤습니다.": {
  "en": "Settings saved, services restarted and status checked.",
  "ja": "設定の保存・サービスの再起動・状態確認が完了しました。"
 },
 "적용하지 않았습니다.": {
  "en": "Not applied.",
  "ja": "適用していません。"
 },
 "변경 내용을 확인하세요. 아직 저장되지 않았습니다.": {
  "en": "Review the changes. They have not been saved yet.",
  "ja": "変更内容をご確認ください。まだ保存していません。"
 },
 "검증·서비스 응답을 기다리는 중…": {
  "en": "Waiting for validation and services…",
  "ja": "検証とサービスの応答を待っています…"
 },
 "주 메뉴": {
  "en": "Main navigation",
  "ja": "メインメニュー"
 },
 "노드 현황": {
  "en": "Node overview",
  "ja": "ノード概要"
 },
 "기기에 연결하지 못했습니다. 새로고침해 주세요.": {
  "en": "Cannot connect to the device. Please refresh.",
  "ja": "デバイスに接続できません。再読み込みしてください。"
 },
 "기기에 연결할 수 없습니다.": {
  "en": "Cannot connect to the device.",
  "ja": "デバイスに接続できません。"
 },
 "두 암호가 일치하지 않습니다. 다시 확인해 주세요.": {
  "en": "The passwords do not match. Please check them.",
  "ja": "パスワードが一致しません。確認してください。"
 },
 "이전 변경이 중단되었습니다. 복구 상태를 확인하세요.": {
  "en": "A previous change was interrupted. Check recovery status.",
  "ja": "前の変更が中断されました。復旧状態を確認してください。"
 },
 "중단된 변경 복구": {
  "en": "Recover interrupted change",
  "ja": "中断された変更を復旧"
 },
 "다른 노드가 이 노드로 연결할 수 있는 경로입니다. RPC 접근 설정과는 별개입니다.": {
  "en": "Routes other nodes can use to connect here. RPC access is configured separately.",
  "ja": "他のノードから接続できる経路です。RPC接続設定とは別です。"
 },
 "자동으로 연결할 목적지 네트워크를 선택합니다. 들어오는 연결과 수동으로 추가한 피어에는 적용되지 않습니다.": {
  "en": "Choose networks for automatic outbound connections. Does not apply to inbound or manually added peers.",
  "ja": "自動送信接続のネットワークを選択します。受信接続と手動追加ピアには適用されません。"
 },
 "켜면 일반 인터넷의 노드에도 Tor를 경유해 연결합니다. onion 연결은 이 토글과 관계없이 Tor를 사용합니다.": {
  "en": "When enabled, clearnet nodes are reached through Tor. Onion connections always use Tor.",
  "ja": "有効にすると通常のインターネットのノードにもTor経由で接続します。onion接続は常にTorを使用します。"
 },
 "나가는 연결은 하나 이상 선택하세요.": {
  "en": "Select at least one outgoing network.",
  "ja": "送信ネットワークを1つ以上選択してください。"
 },
 "버전별 데이터와 electrs 인덱스를 별도로 유지합니다. 새 버전·네트워크에서는 다시 동기화할 수 있습니다. 기존 데이터는 보존됩니다.": {
  "en": "Each version keeps separate data and electrs indexes. A new version or network may require syncing again. Existing data is preserved.",
  "ja": "バージョンごとにデータとelectrs索引を保持します。新しいバージョンやネットワークでは再同期する場合があります。既存データは保持します。"
 },
 "다운로드·서명 검증 진행 중…": {
  "en": "Downloading and verifying signatures…",
  "ja": "ダウンロード・署名検証中…"
 },
 "바이너리 다운로드·서명 검증 진행 중…": {
  "en": "Downloading binary and verifying signatures…",
  "ja": "バイナリのダウンロード・署名検証中…"
 },
 "다운로드·검증 완료. 변경 내용을 확인하세요.": {
  "en": "Download verified. Review the changes.",
  "ja": "取得と検証が完了しました。変更内容をご確認ください。"
 },
 "다운로드가 완료되지 않았습니다. 다시 다운로드를 선택하세요.": {
  "en": "Download did not finish. Choose download to retry.",
  "ja": "ダウンロードが完了していません。再度ダウンロードを選択してください。"
 },
 "Core와 관련 서비스를 재시작합니다. 동기화와 electrs 준비 상태는 현황에서 별도로 확인합니다.": {
  "en": "Core and related services will restart. Check sync and electrs readiness in Overview.",
  "ja": "Coreと関連サービスを再起動します。同期とelectrsの準備状態は概要で確認してください。"
 },
 "QR 데이터를 확인할 수 없습니다.": {
  "en": "Unable to validate QR data.",
  "ja": "QRデータを確認できません。"
 },
 "최초 노드 시작을 준비하고 있습니다.": {
  "en": "Preparing initial node startup.",
  "ja": "ノードの初回起動を準備中です。"
 },
 "백업 및 복원": {
  "en": "Backup and restore",
  "ja": "バックアップと復元"
 },
 "문제 해결": {
  "en": "Troubleshoot",
  "ja": "トラブルシューティング"
 },
 "열기 →": {
  "en": "Open →",
  "ja": "開く →"
 },
 "확인 →": {
  "en": "View →",
  "ja": "確認 →"
 },
 "← 설정": {
  "en": "← Settings",
  "ja": "← 設定"
 },
 "← 문제 해결": {
  "en": "← Troubleshoot",
  "ja": "← トラブルシューティング"
 },
 "Core RPC 상태": {
  "en": "Core RPC status",
  "ja": "Core RPCの状態"
 },
 "저장장치 관리": {
  "en": "Storage management",
  "ja": "ストレージ管理"
 },
 "저장장치 관리 열기": {
  "en": "Open storage management",
  "ja": "ストレージ管理を開く"
 },
 "고급 · 저장장치 관리": {
  "en": "Advanced · Storage management",
  "ja": "詳細設定・ストレージ管理"
 },
 "설정과 연결 정보를 암호화하여 보관합니다.": {
  "en": "Keep an encrypted copy of settings and connection information.",
  "ja": "設定と接続情報を暗号化して保管します。"
 },
 "노드 연결 상태와 고급 저장장치 관리를 확인합니다.": {
  "en": "Check node connections and advanced storage tools.",
  "ja": "ノードの接続状態とストレージの詳細管理を確認します。"
 },
 "NVMe는 첫 부팅 때 자동으로 준비됩니다. 설치 중단 복구나 별도 데이터 디스크를 관리할 때만 사용하세요.": {
  "en": "NVMe setup runs automatically on first boot. Use these tools only to recover an interrupted setup or manage a separate data disk.",
  "ja": "NVMeは初回起動時に自動で準備されます。中断したセットアップの復旧や別のデータディスクの管理に使用します。"
 },
 "내 Core의 RPC 응답과 마지막 수집 오류를 확인합니다.": {
  "en": "View local Core RPC responses and the latest collection errors.",
  "ja": "ローカルCoreのRPC応答と最新の収集エラーを確認します。"
 },
 "고급 관리 화면입니다. 정상 작동하는 NVMe는 다시 초기화할 필요가 없습니다.": {
  "en": "Advanced management. A working NVMe does not need to be initialized again.",
  "ja": "詳細管理画面です。正常に動作するNVMeの再初期化は不要です。"
 },
 "설정과 연결 정보를 암호화하여 백업하거나 복원합니다. 블록체인 전체와 지갑 개인키는 포함하지 않습니다.": {
  "en": "Back up or restore encrypted settings and connection information. The full blockchain and wallet private keys are not included.",
  "ja": "設定と接続情報を暗号化してバックアップ・復元します。ブロックチェーン全体とウォレット秘密鍵は含まれません。"
 },
 "알 수 없음": {
  "en": "Unknown",
  "ja": "不明"
 },
 "조회 불가": {
  "en": "Unavailable",
  "ja": "取得不可"
 },
 "식별 불확실": {
  "en": "Ambiguous",
  "ja": "識別不確実"
 },
 "보상 거래의 태그·주소로 추정한 채굴 풀입니다. 실제 채굴자 신원을 보증하지 않습니다.": {
  "en": "Pool inferred from coinbase tags or reward addresses. This does not prove the actual miner’s identity.",
  "ja": "コインベースのタグや報酬アドレスから推定したプールです。採掘者の身元を保証するものではありません。"
 },
 "블록의 보상 거래에서 채굴 풀을 식별하지 못했습니다.": {
  "en": "Could not identify the mining pool from this block’s coinbase transaction.",
  "ja": "このブロックのコインベースからマイニングプールを識別できませんでした。"
 }
};

let language='ko';const originals=new WeakMap();let observer;
function text(value){
 if(language==='ko')return value;
 const trimmed=value.trim(),entry=messages[trimmed];
 if(entry)return value.replace(trimmed,entry[language]);
 // Dynamic dashboard labels preserve numeric values and data; never translate hashes or addresses.
 const patterns=[[/^● 실시간 · (\d+)초 전$/,language==='en'?'● Live · $1s ago':'● リアルタイム・$1秒前'],[/^블록 ([\d,]+)$/,language==='en'?'Block $1':'ブロック $1']];
 for(const [pattern,replacement] of patterns)if(pattern.test(value))return value.replace(pattern,replacement);
 if(/\d(?:일|시간|분|초)/.test(value))value=value.replace(/(\d+)일/g,language==='en'?'$1d':'$1日').replace(/(\d+)시간/g,language==='en'?'$1h':'$1時間').replace(/(\d+)분/g,language==='en'?'$1m':'$1分').replace(/(\d+)초/g,language==='en'?'$1s':'$1秒').replace(/ 전$/,language==='en'?' ago':'前');
 for(const [source,translations] of Object.entries({"기본값: ": ["Default: ", "既定値: "], "지정값: ": ["Custom: ", "指定値: "], "저장된 요청값: ": ["Saved request: ", "保存された要求値: "], "입력 범위: ": ["Range: ", "入力範囲: "], "현재 실행: ": ["Running: ", "実行中: "], "선택한 버전: ": ["Selected version: ", "選択したバージョン: "], "현재 사용 · ": ["Active · ", "使用中・"], "저장하면 Core와 관련 서비스를 재시작합니다.": ["Saving restarts Core and related services.", "保存するとCoreと関連サービスを再起動します。"], " 선택됨 · 아래에서 변경 내용을 확인하세요.": [" selected · review the changes below.", " 選択済み・以下で変更内容を確認してください。"], "인증서 SHA256: ": ["Certificate SHA256: ", "証明書SHA256: "]}))value=value.split(source).join(translations[language==='en'?0:1]);
 if(value.includes('기본값 사용'))value=value.replaceAll('기본값 사용',messages['기본값 사용'][language]);
 return value;
}
function translate(){
 observer?.disconnect();
 const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
 let node;
 while(node=walker.nextNode()){
  if(node.parentElement.closest('script,style,#terminal,code,textarea'))continue;
  const cached=originals.get(node);const source=cached&&node.data===cached.rendered?cached.source:node.data;
  const rendered=text(source);if(node.data!==rendered)node.data=rendered;originals.set(node,{source,rendered});
 }
 for(const node of document.querySelectorAll('[aria-label],[title]')){
  if(node.closest('#terminal'))continue;
  for(const attr of ['aria-label','title'])if(node.hasAttribute(attr)){
   const key='i18n'+attr;node._jvTranslations??={};const c=node._jvTranslations[key],now=node.getAttribute(attr);const source=c&&now===c.rendered?c.source:now;const rendered=text(source);if(now!==rendered)node.setAttribute(attr,rendered);node._jvTranslations[key]={source,rendered};
  }
 }
 observer?.observe(document.body,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:['aria-label','title']});
}
function set(value){if(!['ko','en','ja'].includes(value))return;language=value;document.documentElement.lang=value;document.documentElement.style.setProperty('--stale-label',JSON.stringify(value==='en'?'Some values are from an earlier sample.':value==='ja'?'一部は以前の取得値です。':'일부 항목은 이전 수집값입니다.'));translate();}
observer=new MutationObserver(translate);translate();
return {set,text};
})();
