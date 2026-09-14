# GitHub のソースから JustVerify イメージを作る

[English](../BUILD.md) · [한국어](../ko/BUILD.md) · [完成イメージのインストール](../INSTALL.md)

JustVerify・electrs・mempool と固定したライブラリを取得してコンパイルし、Raspberry Pi 5 ARM64 用イメージを作ります。Bitcoin Core は**公式署名とチェックサムを検証したバイナリ**、Pi OS と Debian パッケージも upstream の配布物を使用します。OS 全体や Bitcoin Core までソースからコンパイルする手順ではありません。

リリースのソースには `v0.1.0-beta2` タグを使用してください。最新の変更をビルドする場合は `main` の commit を記録してください。自作イメージには独自のチェックサムがあり、プロジェクトの署名は引き継ぎません。OS 全体のバイト単位の再現性は未確認です。

## 1. 隔離した Linux 環境を準備する

**Debian 13 ARM64**、Python 3.13、systemd、sudo を使える一般ユーザー、loop デバイス・mount・chroot が必要です。CPU 4 コア・RAM 8 GB・Linux ファイルシステムの空き 80 GB を目安にしてください。実測した最低要件ではなく余裕を持った割り当てです。作業ディレクトリと `/var/tmp` の両方に空き容量が必要です。稼働中のノードや既存のデータディスクを使用しないでください。

Apple Silicon Mac では Debian 13 ARM64 VM を用意し、以下のコマンドを **Linux 内で**実行します。[Debian ARM64 インストールガイド](https://www.debian.org/releases/trixie/arm64/)を参照してください。macOS 単体での組み立て、Intel/x86 クロスビルド、非特権コンテナ、macOS 共有フォルダは検証済みの経路ではありません。

同じ Bash シェルで順番に実行し、失敗したら原因を解決してから進めます。対象は新しく作成する**通常のイメージファイル**です。`/dev/diskN`、`/dev/sdX`、NVMe など実ディスクのパスを渡さないでください。

```bash
bash
set -euo pipefail
umask 022
test "$(uname -sm)" = "Linux aarch64"
test "$(. /etc/os-release; echo "$VERSION_ID")" = "13"
sudo -v
df -h . /var/tmp
sudo apt-get update
sudo apt-get install --no-install-recommends -y \
  git curl ca-certificates gnupg build-essential clang libclang-dev \
  cmake pkg-config libssl-dev python3 python3-venv xz-utils tar gzip patch \
  file jq parted fdisk e2fsprogs dosfstools zerofree util-linux udev kmod systemd \
  openssl npm nodejs=20.19.2+dfsg-1+deb13u2 \
  mariadb-server=1:11.8.6-0+deb13u1
python3 -c 'import sys; assert sys.version_info[:2] == (3, 13)'
sudo modprobe loop
sudo losetup --find
```

固定した Node/MariaDB が apt に見つからない場合は停止します。同じバージョンを提供するリポジトリ snapshot を使うか、別バージョンの依存関係更新として検証してください。バージョン指定を消して最新パッケージへ置き換えないでください。イメージ内部も同じ固定版を使用します。

## 2. ソースとコンパイラを取得する

```bash
export JV_WORK="$(mktemp -d /var/tmp/justverify-source.XXXXXX)"
chmod 755 "$JV_WORK"
git clone --branch main --single-branch \
  https://github.com/dontrustjustverify/justverify.git "$JV_WORK/repo"
cd "$JV_WORK/repo"
export JV_REPO="$PWD"
export JV_TAG=0.1.0-beta2-local1
mkdir -p .state/build-guide docs/evidence
git rev-parse HEAD > .state/build-guide/source-commit.txt
git switch --detach "$(git rev-parse HEAD)"
curl --proto '=https' --tlsv1.2 -fsSLo "$JV_WORK/rustup-init.sh" https://sh.rustup.rs
sh "$JV_WORK/rustup-init.sh" -y --profile minimal --default-toolchain none
source "$HOME/.cargo/env"
rustup toolchain install 1.98.0 --profile minimal --component rustfmt --component clippy
rustup toolchain install 1.84.1 --profile minimal
rustc +1.98.0 --version
rustc +1.84.1 --version
```

[Rustup](https://rust-lang.github.io/rustup/installation/index.html) は一般ユーザーにコンパイラを導入します。JustVerify・electrs は Rust 1.98.0、mempool の `rust-gbt` は **1.84.1** を明示して使用します。依存関係を HTTPS で取得するため、インターネット接続が必要です。

| 構成要素 | 固定するバージョン・出典 |
|---|---|
| JustVerify・Rust | 記録した Git commit、`rust-toolchain.toml`、`Cargo.lock`、`cargo --locked` |
| Pi OS Lite ARM64 | `catalog/pi-base.json`: 2026-06-18、圧縮・展開後 SHA256 |
| Bitcoin Core | イメージ用 31.1、互換性試験用 22.0、`catalog/trusted-builders.json`、GPG 署名・SHA256 |
| electrs | `catalog/electrs.json`: 0.11.1、commit `35216c6d30148be8e6763d913d437330f431fc03`、ソース・Cargo.lock ハッシュ |
| mempool | `catalog/mempool.json`: 3.3.1、commit `9332d9db97bcc7beed079acc8f79aa21c9b12a3b`、npm 11.8.0、NAPI CLI 2.18.0、依存ロック |
| Python・ブラウザ | `web/requirements.arm64.lock` の wheel・ハッシュ、同梱 `web/static` |
| OS ライブラリ | apt、実際のイメージ一覧は `dist/os-packages.tsv`、apt 依存全体の snapshot 固定は未実装 |

## 3. 検証した入力を取得してコンパイルする

```bash
cd "$JV_REPO"
export JV_BASE="$JV_WORK/raspios-lite-arm64.img.xz"
python3 - "$JV_BASE" <<'FETCH_BASE'
import hashlib, json, pathlib, shutil, sys, urllib.request
m = json.loads(pathlib.Path('catalog/pi-base.json').read_text())
p = pathlib.Path(sys.argv[1])
assert not p.exists(), 'use a fresh output path'
with urllib.request.urlopen(m['url'], timeout=120) as src, p.open('xb') as dst:
    shutil.copyfileobj(src, dst)
with p.open('rb') as f:
    assert hashlib.file_digest(f, 'sha256').hexdigest() == m['sha256']
print('PASS Pi OS compressed SHA256')
FETCH_BASE
python3 scripts/fetch_core.py 31.1 aarch64-linux-gnu
python3 scripts/fetch_core.py 22.0 aarch64-linux-gnu
export JV_CORE="$JV_REPO/.cache/core/31.1/aarch64-linux-gnu/bitcoin-31.1"
export CARGO_BUILD_JOBS=2
cargo +1.98.0 build --release --locked 2>&1 | tee .state/build-guide/cargo-build.log
cargo +1.98.0 test --locked 2>&1 | tee .state/build-guide/cargo-test.log
RUSTUP_TOOLCHAIN=1.98.0 python3 scripts/build_electrs.py "$JV_WORK/electrs" \
  2>&1 | tee .state/build-guide/electrs-build.log
JV_ELECTRS_COMMIT=$(jq -r .commit catalog/electrs.json)
export JV_ELECTRS="$JV_WORK/electrs/electrs-$JV_ELECTRS_COMMIT/target/release/electrs"
RUSTUP_TOOLCHAIN=1.84.1 bash scripts/build_mempool.sh "$JV_WORK/mempool" \
  2>&1 | tee .state/build-guide/mempool-build.log
export JV_MEMPOOL="$JV_WORK/mempool/bundle"
(cd "$JV_MEMPOOL" && sha256sum -c SHA256SUMS > /dev/null)
```

Core のスクリプトは署名・チェックサムが不正なら停止し、`docs/evidence/` に署名者の検証記録を残します。electrs はソースと Cargo ロックを確認します。mempool は固定 commit と追跡されたパッチを使い、韓国語・英語・日本語の画面、対応ソース・ロック・ライセンスをまとめます。Docker は不要です。

electrs・mempool の出力先は**まだ存在しないディレクトリ**である必要があります。失敗した出力を保存し、新しいパスで再試行してください。コンパイルは一般ユーザーで実行します。署名・ソース・依存ハッシュ検証の失敗を回避してはいけません。

## 4. 実際の統合テストを実行する

テストは `/opt/justverify/venv` と非特権 `justverify` アカウントを使用します。専用 MariaDB のローカルソケット認証にもこのアカウントが必要です。**隔離したビルダーのみ**に作成してください。既存環境を上書きしないよう、アカウント・runtime が存在すれば停止します。テストユーザーにパスワードや sudo 権限は付与しません。

```bash
cd "$JV_REPO"
if getent passwd justverify >/dev/null || test -e /opt/justverify/venv; then
  echo 'Use a clean isolated builder: test account/runtime already exists.'
  exit 1
fi
sudo useradd --system --user-group --create-home \
  --home-dir /var/lib/justverify --shell /usr/sbin/nologin justverify
sudo install -d /opt/justverify
sudo python3 -m venv /opt/justverify/venv
sudo /opt/justverify/venv/bin/pip install --require-hashes --only-binary=:all: \
  -r "$JV_REPO/web/requirements.arm64.lock"
sha256sum "$JV_ELECTRS" > .state/build-guide/electrs-before-tests.sha256
for version in 31.1 22.0; do
  core="$JV_REPO/.cache/core/$version/aarch64-linux-gnu/bitcoin-$version"
  sudo install -d -o justverify -g justverify "$JV_WORK/tests-$version"
  state="$JV_WORK/tests-$version/jv-mempool-test-$version"
  sudo -u justverify /opt/justverify/venv/bin/python "$JV_REPO/tests/mempool_live.py" \
    --state "$state" --core "$core/bin" --electrs "$JV_ELECTRS" \
    --bundle "$JV_MEMPOOL" --version "$version"
  sudo cat "$state/result.json" > ".state/build-guide/regtest-$version.json"
done
sha256sum -c .state/build-guide/electrs-before-tests.sha256
```

両方とも終了コード 0 と `PASS` が必要です。実トランザクションの作成・署名・配信、mempool への登録、採掘、承認数 2、Core・electrs・mempool の高さ **107** と tip の一致、アドレス照会、WebSocket 更新、サービス・Core の中断と復旧を検証します。探索を無効にした隔離 regtest 資金のみを使います。ポート 19643/19644/19601/19624/13006/18999 は固定なので同時実行しないでください。テストフォルダのウォレット・認証情報は公開やイメージへの同梱をしないでください。

### 新しくビルドした electrs の検証記録

組み立て時に `catalog/electrs.json` の検証済みバイナリハッシュと比較します。コンパイラやパスの違いでハッシュが変わることがあります。**検査を削除したり、通過させるためだけにハッシュを変更しないでください。** 同一バイナリで上記 2 テストが成功してから、以下でローカルの証拠を保存し、必要ならローカルの検証済みハッシュを更新します。upstream commit・ソース・ロックのハッシュは変更しません。これは 2 つの regtest 組み合わせの検証で、全リリース要件の合格ではありません。

```bash
python3 - "$JV_ELECTRS" <<'LOCAL_EVIDENCE'
import hashlib, json, pathlib, sys
p = pathlib.Path('catalog/electrs.json')
m = json.loads(p.read_text())
with open(sys.argv[1], 'rb') as f:
    digest = hashlib.file_digest(f, 'sha256').hexdigest()
before = pathlib.Path('.state/build-guide/electrs-before-tests.sha256').read_text().split()[0]
build = json.loads(pathlib.Path(sys.argv[1]).parents[3].joinpath('build-result.json').read_text())
assert digest == before == build['binary_sha256']
assert build['source_sha256'] == m['source_sha256']
reports = {}
for version in ('31.1', '22.0'):
    r = json.loads(pathlib.Path(f'.state/build-guide/regtest-{version}.json').read_text())
    assert r['status'] == 'PASS' and r['confirmations'] == 2
    assert r['core_electrs_mempool_height'] == 107
    assert r['versions']['core'].startswith('/Satoshi:' + version + '.')
    reports[version] = r
evidence = {'previous_binary_sha256': m['tested_arm64_binary_sha256'],
            'local_binary_sha256': digest, 'build': build, 'regtest': reports,
            'hardware_boot': 'NOT RUN', 'whole_image_reproducibility': 'NOT RUN'}
pathlib.Path('.state/build-guide/local-electrs-validation.json').write_text(json.dumps(evidence, indent=2)+'\n')
if m['tested_arm64_binary_sha256'] != digest:
    m['tested_arm64_binary_sha256'] = digest
    p.write_text(json.dumps(m, indent=2)+'\n')
LOCAL_EVIDENCE
git diff -- catalog/electrs.json > .state/build-guide/local-catalog.patch
```

## 5. 未起動イメージを組み立てて検証する

```bash
cd "$JV_REPO"
sudo bash image/build-pi.sh \
  "$JV_BASE" "$JV_CORE" "$JV_REPO/target/release/justverify" \
  "$JV_ELECTRS" "$JV_TAG" "$JV_MEMPOOL" \
  2>&1 | tee .state/build-guide/image-build.log
sudo bash image/verify-pi.sh "dist/justverify-$JV_TAG.img.xz" \
  2>&1 | tee .state/build-guide/image-verify.log
```

入力を検証し、OS 内へ runtime・systemd サービスを導入して機器固有の識別情報を除去します。**OS 1 つと分離したデータパーティション**を作り、キャッシュ・未使用領域を整理して圧縮します。A/B の OS 2 組構成ではありません。起動済み VM・Pi ディスクを原本に使用しないでください。

現在のソースは、初回起動で拡張した後も ext4 データボリュームの 0.5% を root 用に予約します。公開済み beta1 イメージでは 5% です。ソースの更新だけでは、インストール済みドライブの予約率は変わりません。

検証器はファイルシステム、ソース・バイナリのハッシュ、所有権、有効なサービス、ARM 実行ファイル、Python import、生成済み識別情報がないことを確認します。Pi 起動・同期・Tor 到達・実機ウォレット接続の代わりにはなりません。失敗は修正してから進めてください。

## 6. チェックサム・展開・インストール

```bash
cd "$JV_REPO"
sudo chown "$(id -u):$(id -g)" dist/justverify-"$JV_TAG".* dist/os-packages.tsv dist/SHA256SUMS
cd dist
xz -t "justverify-$JV_TAG.img.xz"
xz -dk "justverify-$JV_TAG.img.xz"
sha256sum "justverify-$JV_TAG.img.xz" "justverify-$JV_TAG.img" \
  > "justverify-$JV_TAG-SHA256SUMS"
sha256sum -c "justverify-$JV_TAG-SHA256SUMS"
cd "$JV_REPO"
dpkg-query -W > .state/build-guide/builder-packages.tsv
git diff --binary > .state/build-guide/local-source.patch
```

| 成果物 | 用途 |
|---|---|
| `dist/justverify-0.1.0-beta2-local1.img` | balenaEtcher で選択する展開済みイメージ |
| `dist/justverify-0.1.0-beta2-local1.img.xz` | 保管・ダウンロード用 |
| `dist/justverify-0.1.0-beta2-local1-SHA256SUMS` | 両ファイルのハッシュ、`dist/` から検証 |
| `dist/justverify-0.1.0-beta2-local1.layout.json` / `.size-audit.json` | パーティション・容量の記録 |
| `dist/os-packages.tsv` | イメージに実際に導入された OS パッケージ |
| `.state/build-guide/` | ソース commit・差分・ログ・ローカル検証の証拠 |

`JV_TAG` を変えるとファイル名も変わります。SHA256 は完全性確認であり発行者の署名ではありません。この例で生成するのは署名のないローカルイメージです。再配布には正確なソース・変更、各構成要素の対応ソース・ライセンス、対応範囲・テスト報告、自分の署名手順が必要です。[第三者の権利表示](../../licenses/THIRD_PARTY_NOTICES.md)と[リリースの対応ソース](https://github.com/dontrustjustverify/justverify/releases/tag/v0.1.0-beta2)を参照してください。変更したファイルに公式署名を流用できません。

[インストール案内](../INSTALL.md)に従い、Etcher の検証を有効にしてください。実際の macOS/Etcher 2.1.6 では XZ 直接入力がチェックサム検証に失敗し、**展開済み IMG** の記録は合格しました。その後、実機 Pi 5 で初期設定、Core・electrs・Tor、ポート 3006 の mempool、LAN・onion ウォレット、再起動・復旧を確認します。未実行は `NOT RUN`/`BLOCKED` と記録してください。残るリリース条件は [TESTING.md](../TESTING.md) にあります。

## エラー対応と再開

| 症状 | 確認・対応 |
|---|---|
| root・CPU・loop/mount エラー | ARM64 Linux、sudo、loop デバイスを使用。実ディスクで代用しない |
| libclang・RocksDB エラー | clang、libclang-dev、build-essential と失敗ログを確認 |
| mempool Rust エラー | `RUSTUP_TOOLCHAIN=1.84.1` を確認。ロック再生成で隠さない |
| テストの権限エラー | `justverify` がソース・バイナリと上位パスにアクセスできるか確認。ウォレット・runtime は非公開に保つ |
| ポート使用中・試験パス重複 | 自分のテストだけを停止し、旧記録を保って新しいパスで再試行 |
| `electrs differs from tested build` | 当該バイナリで手順 4 を完了し、ローカル証拠を記録 |
| イメージ・中間ファイルが存在 | 旧出力を保ち、新しい `JV_TAG` または checkout を使用。リリースを上書きしない |
| 強制終了・空き容量不足 | RAM と `/var/tmp` の空きも確認。同時処理を減らすか VM を拡張 |

新しいシェルで再開する場合、以前の `JV_WORK`、`JV_REPO`、`JV_TAG`、`JV_BASE`、`JV_CORE`、`JV_ELECTRS`、`JV_MEMPOOL` を復元し、`set -euo pipefail` と `cd "$JV_REPO"` を実行します。検証済み取得物・完成出力は再利用できますが、新規ディレクトリが必要な処理を既存出力へ重ねて実行しないでください。再試験は新しい `tests-...` と `jv-mempool-test-...` パスで行い、両方の報告を残します。再組み立ては新しいタグを使います。
