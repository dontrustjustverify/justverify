<p align="center"><img src="../../web/static/favicon.svg" alt="JustVerify BTC" width="96"></p>
<h1 align="center">JustVerify</h1>
<p align="center">YOUR BITCOIN NODE.<br>No Knots, no Blake2B—nothing but Bitcoin.<br>We are all Satoshi.</p>

Bitcoin Core、electrs、Tor、ローカルMempoolをまとめたRaspberry Pi用ノードです。`justverify.local`またはテキスト画面から管理できます。

[English](../../README.md) · [한국어](../ko/README.md) · [ソースからビルド](BUILD.md)

## 正式版0.1.2

[PiイメージIMG.XZ](https://github.com/dontrustjustverify/justverify/releases/download/v0.1.2/justverify-0.1.2.img.xz) · [SHA256SUMS](https://github.com/dontrustjustverify/justverify/releases/download/v0.1.2/justverify-0.1.2-SHA256SUMS) · [署名](https://github.com/dontrustjustverify/justverify/releases/download/v0.1.2/justverify-0.1.2-SHA256SUMS.asc) · [公開鍵](https://github.com/dontrustjustverify/justverify/releases/download/v0.1.2/justverify-signing-key.asc) · [ソース](https://github.com/dontrustjustverify/justverify/releases/download/v0.1.2/justverify-0.1.2-source.tar.gz) · [リリース](https://github.com/dontrustjustverify/justverify/releases/tag/v0.1.2)

## インストール

基準構成はRaspberry Pi5、RAM8GB、2TB SSD/NVMe、有線LAN、適切な電源と冷却です。Pi4やx86用イメージではありません。

1. [インストール手順](../INSTALL.md)に従ってチェックサムと署名を検証します。
2. XZを展開し、balenaEtcherで`.img`と対象ドライブを選びます。**対象ドライブのデータは消去されます。**書き込み後の検証を有効にしてください。
3. ドライブをPiに接続して起動し、同じLANから`http://justverify.local/`を開き、ウェブ管理者パスワードを設定します。
4. CoreのIBD、Electrsのインデックス作成・DB整理・最新ブロック確認を待ちます。CoreベースのMempoolブロック画面はElectrs同期中も利用できます。

ウォレットは信頼できるLANで**`justverify.local:50001`、SSL/TLSオフ**を使用します。任意のTLSは50002、TorアドレスとQRはElectrs画面にあります。[接続案内](../MOBILE_CONNECTIONS.md)。

初期SSHユーザー名とパスワードは`justverify`です。初回接続後に`passwd`で変更してください。ウェブのパスワードとは別で、sudoにはSSHパスワードを使用します。[SSH管理](../SSH.md)。

## 機能

- 実際のブロック、ピア、手数料、サービス状態とElectrsの同期・DB整理進捗。
- 公式署名を検証したCore22.x–31.1とバージョン別設定。バージョン切替は事前検証と明示的な削除確認後に同じデータパスのチェーン・インデックスを初期化し、完全に再同期します。選択・ダウンロードだけでは変更しません。
- Clearnet、Tor、I2Pの接続選択と任意のTorウェブアクセス。
- 利用中に延長される7日間のログイン、接続ブラウザーの管理、個別ログアウト、暗号化設定バックアップ。
- 日本語・英語・韓国語、ブラウザー言語の自動選択、4色のテーマ。
- 設定のDigital Rain背景：初期状態はオフ。明るさ40%（最大100%）、速度1.60×（最大4.00×）、密度140%（最大300%）。プレビュー後に保存・取消ができ、既存設定は保持されます。非表示タブでは描画を停止し、動きを減らす設定では静止画になります。

Core31.1、electrs0.11.1、Mempool3.3.1、i2pd2.61.0を固定しています。標準ノードはウォレット秘密鍵を保持しません。イメージの再書き込みはデータを保持する更新ではありません。

[設定](../SETTINGS.md) · [復旧](../RECOVERY.md) · [検証範囲](../TESTING.md) · [変更点](../RELEASE_NOTES.md) · [第三者ライセンス](../../licenses/THIRD_PARTY_NOTICES.md)

検証報告書には実行済み試験と、未検証の実機ウォレット・機器の組み合わせを区別して記載しています。

## 画面と動画

Digital Rainを有効にした0.1.0の画面です。独立したregtestノードで撮影し、モバイル表示は幅390 pxのブラウザーを使用しています。

**デスクトップの概要**

![デスクトップの概要](../media/justverify-desktop.png)

**モバイルの概要とElectrs接続**

<p><img src="../media/justverify-mobile.png" alt="JustVerify mobile dashboard" width="300"> <img src="../media/justverify-mobile-electrs.png" alt="Electrs mobile connection" width="300"></p>

**Digital Rainの設定**

![Digital Rainの設定](../media/justverify-digital-rain.png)

**30秒ツアー · 10画面を各3秒**

https://github.com/user-attachments/assets/d26903d9-03a6-45cb-b740-3a5e81ee8407

[MP4をダウンロード](https://github.com/dontrustjustverify/justverify/releases/download/v0.1.0/justverify-0.1.0-tour.mp4)
