<p align="center"><img src="../../web/static/favicon.svg" alt="JustVerify BTC" width="96"></p>
<h1 align="center">JustVerify</h1>
<p align="center">YOUR BITCOIN NODE.<br>No Knots, no Blake2B—nothing but Bitcoin.<br>We are all Satoshi.</p>
<p align="center"><a href="../../README.md">English</a> · <a href="../ko/README.md">한국어</a> · 日本語</p>

自分で検証するBitcoin Coreノードです。NVMeにイメージを書き込み、Raspberry Pi 5を起動して **http://justverify.local** を開きます。端末風ダッシュボード、Tor、electrs、ローカルmempoolエクスプローラーを同梱しています。

**0.1.0-beta1はテスト版です。** インストール前に[検証済み・未検証の項目](../ACCEPTANCE.md)をご確認ください。ビルドやregtestの成功は、mainnetの全インデックス、実機スマートフォンのウォレット接続、長期安定性の検証完了を意味しません。

## 主な機能

- 公式署名を検証したBitcoin Core。Core 22以降の対応カタログから選択し、互換性を検証していないバージョンには別のデータ領域を使用します。
- 非rootで動作する実際のTUIと、画面幅に合わせて配置が変わるWebダッシュボード。ブロック、ピア、手数料、システム情報を表示します。
- Torとelectrs。LAN/Tor別の接続先、ポート、TLS情報とQRコード。
- **mempool 3.3.1を同梱。** Electrsの隣の **メンプール** から **http://justverify.local:3006** を開けます。
- 韓国語、英語、日本語とTeal、Amber、Green、Iceの文字色テーマ。
- 変更内容を確認して設定を適用し、暗号化した設定のバックアップと復元ができます。

## 必要な機器

現在のイメージは **Raspberry Pi 5、64ビット、有線LAN、NVMe** 向けです。実機検証対象は **RAM 8 GB、NVMe 2 TB** と、対応するNVMe HAT・ブートローダーです。適切な電源と冷却装置を使用してください。Pi 4やx86 PCには対応するイメージではありません。

1台のNVMeをOSとデータ用パーティションに分け、初回起動時にデータ領域を拡張します。A/B OSは不要です。ブロックチェーン、txindex、electrs、エクスプローラーのデータを保存するため、圧縮ファイルのサイズと必要なストレージ容量は異なります。

## ダウンロードとインストール

1. このリポジトリの **Releases** に公開された `justverify-0.1.0-beta1.img.xz`、`justverify-0.1.0-beta1-SHA256SUMS`、署名、manifest、リリースノートを取得します。manifestに記載されたイメージを使用してください。
2. macOSでは `shasum -a 256 justverify-0.1.0-beta1.img.xz` を実行し、`justverify-0.1.0-beta1-SHA256SUMS`と比較します。実験用署名鍵と信頼上の制限は[インストールガイド](../INSTALL.md)を参照してください。
3. **balenaEtcher**でイメージと対象NVMeを選択して書き込みます。利用中のEtcherが`.xz`を受け付けない場合は先に展開してください。対象ドライブの内容は消去されます。検証を省略せず、成功表示を待ってください。
4. NVMeを安全に取り出してPi 5に装着し、LANと電源を接続します。
5. 同じネットワークから **http://justverify.local** を開きます。名前で接続できない場合は、ルーターで確認したPiのIPアドレスを使用します。
6. Web管理者パスワードと確認用パスワードを入力します。機器固有の識別情報とデータ領域を準備し、既定のCoreプロファイルを自動で起動します。
7. 電源とネットワークを維持して同期を待ちます。Coreの後にelectrsとmempoolの準備状態も確認してください。サービスの起動表示だけでは同期完了とは判断できません。

新しいプロファイルでは取引照会用に`txindex=1`を設定します。既存の設定は保持します。Core・txindex・electrsが準備できるまでmempoolに準備状況を表示し、外部エクスプローラーのデータで代用しません。

## 日常の操作

| 接続先・メニュー | 用途 |
|---|---|
| `http://justverify.local` | 概要、Coreバージョン・ポリシー設定、Electrs、機器設定 |
| `http://justverify.local:3006` | 自分のノードのmempoolエクスプローラー |
| Electrs → ローカルネットワーク / Tor | 実際のアドレス、ポート、プロトコル、TLS指紋、QR |
| 設定 | アカウント、文字色、言語、Remote Tor access、再起動・終了 |
| 設定 → バックアップと復元 | 暗号化した設定の保管・復元 |
| 設定 → トラブルシューティング | サービス状態とストレージの詳細管理 |

Web管理者パスワードとSSHパスワードは別です。指定された初期SSHアカウントは **`justverify` / `justverify`** です。初回SSH接続後に`passwd`で変更してください。無制限のrootシェルを提供するアカウントではありません。公開イメージには開発者のroot SSH鍵や事前生成された機器秘密鍵を含めません。

管理HTTPとエクスプローラーは信頼できるLANで使用し、インターネットからポート転送しないでください。Core RPCはローカルに限定し、ウォレット用リモートRPCには別の認証・保護された経路を使用します。Remote Tor accessは明示的に有効化し、サービスごとに別のアドレスを使用します。[ウォレット接続ガイド](../MOBILE_CONNECTIONS.md)もご確認ください。

## バックアップと復旧

再インストール前に暗号化した設定バックアップとパスワードを **Piの外部に** 保存してください。設定と機器識別情報を含みますが、ブロックチェーン全体やウォレット秘密鍵は含みません。電源やNVMeを取り外す前に設定画面から終了します。イメージの再書き込みはディスクを置き換える新規インストールであり、既存環境への更新ではありません。[インストール](../INSTALL.md)と[復旧](../RECOVERY.md)の手順に従ってください。

## ビルド・検証・ライセンス

イメージの組み立てには隔離した **ARM64 Linux** 環境を使用します。[ビルド手順](../BUILD.md)、[受け入れ基準](../ACCEPTANCE.md)、[テスト結果](../TEST_RESULTS.md)、[作業状況](../STATUS.md)を公開しています。

JustVerifyと同梱コンポーネントにはそれぞれのライセンスが適用されます。[第三者の権利表示](../../THIRD_PARTY_NOTICES.md)をご覧ください。mempoolはupstreamのAGPL条件で別途同梱し、エクスプローラーの **ソース · AGPL** から原典、ビルド変更、ロックファイルを取得できます。Umbrelはガイド構成とアプリ統合の参考として調査し、コードやUI素材はコピーしていません。各upstreamプロジェクトによる公式製品や推奨を意味しません。
