# GitHub 소스로 JustVerify 이미지 만들기

[English](../BUILD.md) · [日本語](../ja/BUILD.md) · [완성 이미지 설치](../INSTALL.md)

GitHub에서 JustVerify·electrs·mempool 소스와 잠금된 라이브러리를 받아 컴파일하고 Raspberry Pi 5 ARM64 설치 이미지를 만드는 안내입니다. Bitcoin Core는 **공식 서명과 체크섬을 검증한 바이너리**를 사용하며 Pi OS·Debian 패키지도 upstream 배포물을 사용합니다. OS의 모든 패키지와 Bitcoin Core까지 소스에서 컴파일하는 과정은 아닙니다.

이 안내는 현재 `main` 기준입니다. 받은 commit을 기록하세요. 고정된 `v0.1.0-beta1` 태그는 이 안내보다 이전 상태입니다. 직접 만든 이미지는 별도 산출물이므로 기존 beta1 서명이나 검증 결과를 이어받지 않습니다. OS 이미지 전체의 **바이트 단위 재현성은 아직 입증되지 않았습니다**.

## 1. 격리된 Linux 빌드 환경 준비

**Debian 13 ARM64**, Python 3.13, systemd, sudo를 사용할 수 있는 일반 계정, loop 장치·mount·chroot가 필요합니다. CPU 4코어·RAM 8 GB·Linux 파일시스템 여유 공간 80 GB를 준비하는 것을 권합니다. 실측 최소 사양이 아니라 여유를 둔 빌드 자원 안내입니다. 작업 폴더와 `/var/tmp` 모두 공간이 필요합니다. 운영 중인 노드나 기존 데이터 디스크를 빌드에 사용하지 마세요.

Apple Silicon Mac에서는 Debian 13 ARM64 VM을 먼저 설치한 뒤 아래 명령을 **Linux 안에서** 실행합니다. [Debian ARM64 설치 안내](https://www.debian.org/releases/trixie/arm64/)를 참고하세요. macOS에서 이미지 조립을 직접 실행할 수 없습니다. Intel/x86 교차 빌드·비권한 컨테이너·macOS 공유 폴더는 검증된 빌드 경로가 아닙니다.

같은 Bash 셸에서 각 블록을 순서대로 실행하고 실패하면 원인을 해결한 뒤 진행하세요. 이미지 조립 대상은 새로 만드는 **일반 파일**입니다. `/dev/diskN`, `/dev/sdX`, NVMe 장치 등 실제 디스크 경로를 입력하지 마세요.

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

apt에서 고정한 Node/MariaDB 버전을 찾지 못하면 중단합니다. 정확한 버전이 있는 저장소 snapshot을 사용하거나 별도 버전으로 의존성 변경을 검증해야 합니다. 버전 지정을 지워 임의로 최신 패키지를 설치하지 마세요. 이미지 내부에도 같은 고정 버전을 설치합니다.

## 2. 소스와 컴파일러 받기

```bash
export JV_WORK="$(mktemp -d /var/tmp/justverify-source.XXXXXX)"
chmod 755 "$JV_WORK"
git clone --branch main --single-branch \
  https://github.com/dontrustjustverify/justverify.git "$JV_WORK/repo"
cd "$JV_WORK/repo"
export JV_REPO="$PWD"
export JV_TAG=0.1.0-beta1-local1
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

[Rustup](https://rust-lang.github.io/rustup/installation/index.html)은 일반 빌드 계정에 컴파일러를 설치합니다. JustVerify·electrs는 Rust 1.98.0, mempool의 `rust-gbt`는 **1.84.1**을 사용합니다. 아래 명령은 이를 각각 명시합니다. 의존성을 HTTPS로 받으므로 인터넷 연결이 필요합니다.

| 구성요소 | 버전·출처 고정 방법 |
|---|---|
| JustVerify·Rust 라이브러리 | 기록한 Git commit, `rust-toolchain.toml`, `Cargo.lock`, `cargo --locked` |
| Pi OS Lite ARM64 | `catalog/pi-base.json`: 2026-06-18, 압축·원본 SHA256 |
| Bitcoin Core | 이미지용 31.1, 호환성 시험용 22.0; `catalog/trusted-builders.json`, GPG 서명·SHA256 |
| electrs | `catalog/electrs.json`: 0.11.1, commit `35216c6d30148be8e6763d913d437330f431fc03`, 소스·Cargo.lock 해시 |
| mempool | `catalog/mempool.json`: 3.3.1, commit `9332d9db97bcc7beed079acc8f79aa21c9b12a3b`, npm 11.8.0, NAPI CLI 2.18.0, 의존성 잠금 파일 |
| Python·브라우저 | `web/requirements.arm64.lock`의 wheel·해시, 저장소에 포함된 `web/static` |
| OS 라이브러리 | apt 설치, 실제 이미지 목록은 `dist/os-packages.tsv`; 전체 apt 의존성은 snapshot으로 고정되지 않음 |

## 3. 검증된 입력 파일 받기와 컴파일

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

Core 스크립트는 서명·체크섬 실패 시 중단하고 `docs/evidence/`에 서명자 검증 결과를 기록합니다. electrs는 소스·Cargo 잠금 파일을 확인하고 컴파일합니다. mempool은 고정 commit과 저장소의 패치를 사용해 한글·영어·일본어 화면을 만들고 원본 소스·잠금 파일·라이선스를 묶습니다. Docker는 필요하지 않습니다.

electrs·mempool 빌드는 **아직 없는 출력 폴더**가 필요합니다. 실패한 폴더는 진단용으로 보존하고 새 경로에서 재시도하세요. 컴파일은 일반 계정으로 실행합니다. 서명·소스·의존성 해시 검증 실패를 우회하면 안 됩니다.

## 4. 실제 통합시험 실행

기존 시험 스크립트는 `/opt/justverify/venv`와 비권한 `justverify` 계정을 사용합니다. 이 계정은 시험용 MariaDB의 로컬 소켓 인증에도 필요합니다. **격리된 빌드 환경에서만** 준비하세요. 아래 명령은 기존 설치를 덮어쓰지 않도록 계정·환경이 이미 있으면 중단합니다. 시험 계정에는 암호나 sudo 권한을 부여하지 않습니다.

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

두 시험 모두 종료 코드 0과 `PASS`가 필요합니다. 실제 거래 생성·서명·브로드캐스트, mempool 진입, 블록 생성, 확인 수 2, Core·electrs·mempool 높이 **107** 및 tip 일치, 주소 조회, WebSocket 갱신, 서비스·Core 중단 후 복구를 확인합니다. 피어 검색을 끈 격리 regtest의 시험 자금만 사용합니다. 포트 19643/19644/19601/19624/13006/18999가 고정되어 있으므로 동시에 실행하지 마세요. 시험 폴더의 지갑·자격증명을 공개하거나 이미지에 넣지 마세요.

### 직접 빌드한 electrs 검증 기록

이미지 조립기는 `catalog/electrs.json`의 검증된 바이너리 해시와 비교합니다. 컴파일러·빌드 경로에 따라 새 바이너리의 해시가 다를 수 있습니다. **검사를 지우거나 통과시키기 위해 해시만 바꾸면 안 됩니다.** 위 두 실제 시험을 동일 바이너리로 통과한 뒤에만 아래 명령으로 근거를 저장하고 필요한 경우 로컬 카탈로그의 검증 해시를 갱신합니다. upstream commit·소스·잠금 파일 해시는 유지됩니다. 이는 두 regtest 조합의 검증이며 전체 배포 기준 통과를 의미하지 않습니다.

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

## 5. 미부팅 설치 이미지 조립·검증

```bash
cd "$JV_REPO"
sudo bash image/build-pi.sh \
  "$JV_BASE" "$JV_CORE" "$JV_REPO/target/release/justverify" \
  "$JV_ELECTRS" "$JV_TAG" "$JV_MEMPOOL" \
  2>&1 | tee .state/build-guide/image-build.log
sudo bash image/verify-pi.sh "dist/justverify-$JV_TAG.img.xz" \
  2>&1 | tee .state/build-guide/image-verify.log
```

입력 검증 후 OS 안에 실행 파일과 systemd 서비스를 설치하고 기기별 식별정보를 제거합니다. **OS 한 벌과 별도 데이터 파티션**으로 구성하고 캐시·미사용 파일시스템 영역을 정리해 압축합니다. A/B OS 두 벌을 만들지 않습니다. 이미 부팅한 VM·Pi 디스크를 원본 이미지로 사용하지 마세요.

검증기는 파일시스템, 포함된 소스·바이너리 해시, 소유권, 활성 서비스, ARM 실행 파일, Python import, 기기별 식별정보 부재를 확인합니다. Pi 부팅·동기화·Tor 도달·실제 모바일 지갑 연결을 대신하지 않습니다. 실패하면 원인을 해결한 뒤 다음 단계로 진행합니다.

## 6. 체크섬 생성·압축 해제·설치

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

| 산출물 | 용도 |
|---|---|
| `dist/justverify-0.1.0-beta1-local1.img` | balenaEtcher에서 선택할 압축 해제 이미지 |
| `dist/justverify-0.1.0-beta1-local1.img.xz` | 보관·다운로드용 압축 이미지 |
| `dist/justverify-0.1.0-beta1-local1-SHA256SUMS` | 두 파일의 체크섬; `dist/`에서 검증 |
| `dist/justverify-0.1.0-beta1-local1.layout.json` / `.size-audit.json` | 파티션 구성·용량 분석 |
| `dist/os-packages.tsv` | 이미지 안에 실제 설치한 OS 패키지 |
| `.state/build-guide/` | 소스 commit·수정 내역·로그·로컬 구성요소 검증 근거 |

`JV_TAG`를 바꾸면 파일명도 바뀝니다. SHA256은 파일 무결성 검사이며 배포자 서명이 아닙니다. 이 예제는 서명되지 않은 로컬 이미지를 만듭니다. 다른 사람에게 재배포하려면 정확한 소스·수정 내역, 각 구성요소의 대응 소스·라이선스, 지원 범위·시험 보고서와 자체 서명 절차를 갖춰야 합니다. [제3자 고지](../../licenses/THIRD_PARTY_NOTICES.md)와 [릴리스의 대응 소스 자료](https://github.com/dontrustjustverify/justverify/releases/tag/v0.1.0-beta1)를 참고하세요. 수정한 파일에 공식 릴리스 서명을 재사용할 수 없습니다.

[설치 안내](../INSTALL.md)에 따라 Etcher의 검증을 켜고 기록하세요. 실제 macOS/Etcher 2.1.6 시험에서는 XZ 직접 입력이 체크섬 검증에 실패했고 **압축을 푼 IMG** 기록은 통과했습니다. 이후 실제 Pi 5에서 최초 설정, Core·electrs·Tor, 3006 포트 mempool, LAN·onion 지갑, 재부팅·복구를 확인합니다. 실행하지 않은 검증은 `NOT RUN`/`BLOCKED`로 기록하세요. 남은 배포 기준은 [TESTING.md](../TESTING.md)에 있습니다.

## 오류 해결과 재개

| 증상 | 확인할 내용 |
|---|---|
| root·CPU 또는 loop/mount 오류 | ARM64 Linux에서 sudo·loop 장치를 사용; 실제 디스크 경로로 대체하지 않음 |
| libclang·RocksDB 오류 | clang, libclang-dev, build-essential 설치 확인; 실패 로그 보존 |
| mempool Rust 오류 | `RUSTUP_TOOLCHAIN=1.84.1` 확인; 잠금 파일 재생성으로 숨기지 않음 |
| 통합시험 권한 오류 | `justverify`가 소스·바이너리와 상위 경로를 읽고 통과할 수 있는지 확인; 지갑·runtime은 비공개 유지 |
| 포트 사용 중·시험 폴더 중복 | 자신의 시험 프로세스만 정지; 이전 근거를 남기고 새 경로로 재시험 |
| `electrs differs from tested build` | 해당 바이너리로 4단계 시험과 로컬 검증 기록 완료 |
| 이미지·중간 파일 중복 | 실패 파일·로그 보존, 새 `JV_TAG` 또는 새 checkout 사용; 릴리스 덮어쓰기 금지 |
| 빌드 강제 종료·디스크 부족 | RAM과 `/var/tmp`를 포함한 여유 공간 확인; 동시 작업 수 감소 또는 빌드 VM 확장 |

새 셸에서 재개할 때는 기존 빌드의 `JV_WORK`, `JV_REPO`, `JV_TAG`, `JV_BASE`, `JV_CORE`, `JV_ELECTRS`, `JV_MEMPOOL` 값을 복원하고 `set -euo pipefail`, `cd "$JV_REPO"`를 실행합니다. 검증한 다운로드·완성된 출력은 재사용하되 새 폴더가 필요한 명령을 기존 출력 위에 다시 실행하지 마세요. 재시험은 새 `tests-...` 및 `jv-mempool-test-...` 경로를 쓰고 두 시도의 보고서를 보존합니다. 재조립은 새 태그를 사용합니다.

이 안내는 저장소의 실제 스크립트를 기준으로 작성했습니다. 문서·명령 검증과 새 빌드 환경의 전체 실행은 구분합니다. 안내 추가만으로 새로운 이미지 전체 빌드나 실기 검증을 통과했다고 주장하지 않습니다.
