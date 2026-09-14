<p align="center"><img src="../../web/static/favicon.svg" alt="JustVerify BTC" width="96"></p>
<h1 align="center">JustVerify</h1>
<p align="center">YOUR BITCOIN NODE.<br>No Knots, no Blake2B—nothing but Bitcoin.<br>We are all Satoshi.</p>
<p align="center"><a href="../../README.md">English</a> · <a href="../ko/README.md">한국어</a> · 日本語</p>

自分で検証するBitcoin Coreノードです。NVMeにイメージを書き込み、Raspberry Pi 5を起動して **http://justverify.local** を開きます。端末風ダッシュボード、Tor、electrs、ローカルmempoolエクスプローラーを同梱しています。

**0.1.0-beta2はテスト版です。** インストール前に[検証済み・未検証の項目](../TESTING.md)をご確認ください。ビルドやregtestの成功は、mainnetの全インデックス、実機スマートフォンのウォレット接続、長期安定性の検証完了を意味しません。

## 主な機能

- 公式署名を検証したBitcoin Core。Core 22以降の対応カタログから選択し、互換性を検証していないバージョンには別のデータ領域を使用します。
- 非rootで動作する実際のTUIと、画面幅に合わせて配置が変わるWebダッシュボード。ブロック、ピア、手数料、システム情報を表示します。
- Torとelectrs。LAN/Tor別の接続先、ポート、TLS情報とQRコード。
- **mempool 3.3.1を同梱。** Electrsの隣の **メンプール** から **http://justverify.local:3006** を開けます。
- 韓国語、英語、日本語とTeal、Amber、Green、Iceの文字色テーマ。
- 変更内容を確認して設定を適用し、暗号化した設定のバックアップと復元ができます。

現在のソースのOP_RETURN・ネットワーク設定とログイン保持については[ノード設定ガイド](../SETTINGS.md)をご覧ください。公開済みbeta1インストーラーには、これらの最新ソース変更はまだ含まれていません。

## 画面と操作動画

実際のメニュー操作とスクロールを収録した **30秒の動画**です。10画面をそれぞれ3秒ずつ表示します。

https://github.com/user-attachments/assets/17d80624-cdec-40c1-af07-acc7816be195

[30秒の動画をダウンロード（MP4）](https://github.com/dontrustjustverify/justverify/releases/download/v0.1.0-beta1/justverify-0.1.0-beta1-tour.mp4)

**デスクトップの概要画面**

![JustVerify デスクトップ画面](../media/justverify-desktop.png)

**モバイルの概要画面とElectrs**

<p><img src="../media/justverify-mobile.png" alt="JustVerify モバイル画面" width="280"> <img src="../media/justverify-mobile-electrs.png" alt="JustVerify モバイルのElectrs接続とQR" width="280"></p>

実際のbeta1アプリとBitcoin Core・electrs・mempoolを、隔離したARM VMの **regtest** で実行して撮影しました。モバイル画像は幅390 pxのブラウザーで確認したレスポンシブ表示です。実機スマートフォンや公開ネットワークの検証完了を示すものではありません。表示された接続先とQRは使い捨てのテスト環境用です。接続時はご自身のノードに表示される情報を使用してください。

## 必要な機器

現在のイメージは **Raspberry Pi 5、64ビット、有線LAN、NVMe** 向けです。実機検証対象は **RAM 8 GB、NVMe 2 TB** と、対応するNVMe HAT・ブートローダーです。適切な電源と冷却装置を使用してください。Pi 4やx86 PCには対応するイメージではありません。

1台のNVMeをOSとデータ用パーティションに分け、初回起動時にデータ領域を拡張します。A/B OSは不要です。ブロックチェーン、txindex、electrs、エクスプローラーのデータを保存するため、圧縮ファイルのサイズと必要なストレージ容量は異なります。

## ダウンロードとインストール

1. このリポジトリの [**Releases**](https://github.com/dontrustjustverify/justverify/releases/tag/v0.1.0-beta2) に公開された [justverify-0.1.0-beta2.img.xz](https://github.com/dontrustjustverify/justverify/releases/download/v0.1.0-beta2/justverify-0.1.0-beta2.img.xz)、[justverify-0.1.0-beta2-SHA256SUMS](https://github.com/dontrustjustverify/justverify/releases/download/v0.1.0-beta2/justverify-0.1.0-beta2-SHA256SUMS)、署名、manifest、リリースノートを取得します。manifestに記載されたイメージを使用してください。
2. macOSでは `shasum -a 256 justverify-0.1.0-beta2.img.xz` を実行し、[justverify-0.1.0-beta2-SHA256SUMS](https://github.com/dontrustjustverify/justverify/releases/download/v0.1.0-beta2/justverify-0.1.0-beta2-SHA256SUMS)と比較します。実験用署名鍵と信頼上の制限は[インストールガイド](../INSTALL.md)を参照してください。
3. XZ対応の展開ツールで`.img.xz`を解凍し、**balenaEtcher**で展開した`.img`と対象NVMeを選択して書き込みます。macOS/Etcher 2.1.6の実測ではXZの直接書き込みは検証に失敗し、展開したIMGは成功しました。対象ドライブの内容は消去されます。検証を省略せず、成功表示を待ってください。
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

Web管理者パスワードとSSHパスワードは別です。指定された初期SSHアカウントは **`justverify` / `justverify`** です。初回SSH接続後に`passwd`で変更してください。beta2ではSSHパスワードを入力すると`sudo`でOSを管理できます。[SSH管理ガイド](../SSH.md)をご覧ください。公開イメージには開発者のroot SSH鍵や事前生成された機器秘密鍵を含めません。

管理HTTPとエクスプローラーは信頼できるLANで使用し、インターネットからポート転送しないでください。Core RPCはローカルに限定し、ウォレット用リモートRPCには別の認証・保護された経路を使用します。Remote Tor accessは明示的に有効化し、サービスごとに別のアドレスを使用します。[ウォレット接続ガイド](../MOBILE_CONNECTIONS.md)もご確認ください。

## バックアップと復旧

再インストール前に暗号化した設定バックアップとパスワードを **Piの外部に** 保存してください。設定と機器識別情報を含みますが、ブロックチェーン全体やウォレット秘密鍵は含みません。電源やNVMeを取り外す前に設定画面から終了します。イメージの再書き込みはディスクを置き換える新規インストールであり、既存環境への更新ではありません。[インストール](../INSTALL.md)と[復旧](../RECOVERY.md)の手順に従ってください。

## ビルド・検証・ライセンス

イメージの組み立てには隔離した **ARM64 Linux** 環境を使用します。[GitHub ソース・ライブラリ取得からイメージ作成まで](BUILD.md)、[検証結果と未完了項目](../TESTING.md)、[リリース情報](../RELEASE_NOTES.md)を公開しています。

JustVerifyと同梱コンポーネントにはそれぞれのライセンスが適用されます。[第三者の権利表示](../../licenses/THIRD_PARTY_NOTICES.md)をご覧ください。mempoolはupstreamのAGPL条件で別途同梱し、エクスプローラーの **ソース · AGPL** から原典、ビルド変更、ロックファイルを取得できます。Umbrelはガイド構成とアプリ統合の参考として調査し、コードやUI素材はコピーしていません。各upstreamプロジェクトによる公式製品や推奨を意味しません。
