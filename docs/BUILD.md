# Build a JustVerify image from GitHub

[한국어](ko/BUILD.md) · [日本語](ja/BUILD.md) · [Install a prebuilt image](INSTALL.md)

This guide compiles JustVerify, electrs and mempool, downloads their locked libraries, and assembles a Raspberry Pi 5 ARM64 image. Bitcoin Core comes from its official **signature-verified binary archive**; Pi OS and Debian packages are prebuilt upstream inputs. This is not a source build of every OS package or Bitcoin Core.

Use the `v0.1.0-beta7` tag for the release source, or record the commit of `main` when building newer changes. Local builds have their own checksums and do not inherit the project signature. Whole-image byte-for-byte reproducibility is not established.

## 1. Prepare an isolated builder

Use **Debian 13 ARM64**, Python 3.13, systemd, a normal user with sudo, and working loop devices/mount/chroot. Plan for 4 CPU cores, 8 GB RAM and 80 GB free on a Linux filesystem. These are conservative allocations, not measured minimum requirements. Both the checkout and `/var/tmp` need space. Do not use a running node or connect its data drive to the builder.

On Apple Silicon, install Debian 13 ARM64 in a VM and execute these commands **inside Linux**; see the [Debian ARM64 installation guide](https://www.debian.org/releases/trixie/arm64/). macOS cannot run the assembler directly. Intel/x86 cross-compilation, unprivileged containers and macOS shared folders are not validated build paths.

Run each block in order in the same Bash shell; stop on failure. The assembler operates on newly created **regular image files**. Never supply a physical disk such as `/dev/diskN`, `/dev/sdX` or an NVMe device.

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
  cmake pkg-config libssl-dev libboost-program-options-dev libboost-filesystem-dev zlib1g-dev python3 python3-venv xz-utils tar gzip patch \
  file jq parted fdisk e2fsprogs dosfstools zerofree util-linux udev kmod systemd \
  openssl npm nodejs=20.19.2+dfsg-1+deb13u2 \
  mariadb-server=1:11.8.6-0+deb13u1
python3 -c 'import sys; assert sys.version_info[:2] == (3, 13)'
sudo modprobe loop
sudo losetup --find
```

If apt cannot find the pinned Node/MariaDB versions, stop. Use a repository snapshot supplying those exact packages, or qualify a separately versioned dependency update. Do not remove version pins silently. Assembly installs the same pinned packages inside the Pi OS image.

## 2. Clone source and install toolchains

```bash
export JV_WORK="$(mktemp -d /var/tmp/justverify-source.XXXXXX)"
chmod 755 "$JV_WORK"
git clone --branch main --single-branch \
  https://github.com/dontrustjustverify/justverify.git "$JV_WORK/repo"
cd "$JV_WORK/repo"
export JV_REPO="$PWD"
export JV_TAG=0.1.0-beta7-local1
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

[Rustup](https://rust-lang.github.io/rustup/installation/index.html) installs compilers for the normal build user. JustVerify and electrs use Rust 1.98.0. Mempool's native `rust-gbt` uses **1.84.1**, explicitly selected below. Dependencies download over HTTPS; this is an online build.

| Input | Version/source control |
|---|---|
| JustVerify/Rust libraries | Recorded Git commit, `rust-toolchain.toml`, `Cargo.lock`, `cargo --locked` |
| Pi OS Lite ARM64 | `catalog/pi-base.json`: 2026-06-18; compressed and extracted SHA256 |
| Bitcoin Core | 31.1 in image; 22.0 for compatibility tests; `catalog/trusted-builders.json`, GPG signature and SHA256 |
| electrs | `catalog/electrs.json`: 0.11.1, commit `35216c6d30148be8e6763d913d437330f431fc03`, source/Cargo.lock hashes |
| mempool | `catalog/mempool.json`: 3.3.1, commit `9332d9db97bcc7beed079acc8f79aa21c9b12a3b`, npm 11.8.0, NAPI CLI 2.18.0 and dependency locks |
| i2pd | 2.61.0; `catalog/i2pd.json`, SHA256-verified source, BSD-3-Clause; native CMake build, local SAM 3.1 |
| Python/browser | Hashed Python wheels in `web/requirements.arm64.lock`; vendored browser assets in `web/static` |
| OS libraries | apt packages; actual image inventory in `dist/os-packages.tsv`; the entire apt graph is not snapshot-locked |

## 3. Download verified inputs and compile

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
bash scripts/build_i2pd.sh "$JV_WORK/i2pd" \
  2>&1 | tee .state/build-guide/i2pd-build.log
export JV_I2PD="$JV_WORK/i2pd/bundle"
(cd "$JV_I2PD" && sha256sum -c SHA256SUMS > /dev/null)
```

i2pd is built from the pinned source in `catalog/i2pd.json`. Its bundle includes the source archive, BSD license and public reseed certificates. Assembly requires this seventh argument and installs the pinned Boost program-options runtime. No router identity is included.

Core's script rejects checksum/signature failures and writes signer evidence under `docs/evidence/`. Electrs checks its source and Cargo lock before compilation. Mempool verifies its commit, applies tracked patches, builds the Korean/English/Japanese frontends and packages corresponding source, locks and licenses. No Docker daemon is needed.

Electrs/mempool build scripts require **new output directories**. Keep failures for diagnosis and use a fresh path for retries. Do not compile as root. Never bypass a source, signature or dependency hash failure.

## 4. Run real integration tests

The existing harness uses `/opt/justverify/venv` and the unprivileged `justverify` account for its private MariaDB socket. Set these up only in the isolated builder. The block refuses an existing account/runtime to prevent overwriting a real installation. The test account gets no password or sudo rights.

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

Both tests must exit zero and report `PASS`: actual transaction creation/signing/broadcast, mempool entry, mining, two confirmations, Core/electrs/mempool height **107** and tip agreement, address lookup, WebSocket updates and service/Core interruption/recovery. They use private regtest funds with discovery disabled. Ports 19643/19644/19601/19624/13006/18999 are fixed: run one test at a time. Private test folders contain disposable wallets and credentials; do not publish or package them.

### I2P peer transport

In a separate builder with SAM ports 7656/8656 free, run the bundled-router test as the normal user. It owns two independent i2pd routers on the public I2P network and uses only fresh regtest wallets/funds. Allow several minutes for tunnels. Output folders contain private test identities and must not be published.

```bash
python3 tests/run_i2p_live.py --bundle "$JV_I2PD" \
  --core "$JV_CORE/bin/bitcoind" --root "$JV_WORK/i2p-live"
```

The test requires actual I2P Bitcoin handshakes, signed transaction propagation, two confirmations, matching tips, restart identity preservation and outgoing-only block propagation. `tests/image_i2p_probe.py` separately tests installed services and reboot in a disposable factory-image VM; it must never run on an existing physical node.

### Qualify the newly compiled electrs

The assembler checks `catalog/electrs.json`'s tested binary hash. Different compiler/path environments can produce a different binary. **Do not delete this check or change the hash merely to bypass it.** Only after both actual tests above pass for the unchanged binary, record local evidence and update your local tested hash if needed. Source/commit/lock hashes remain fixed. This validates these two regtest combinations, not every release gate.

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

## 5. Assemble and verify a pristine image

```bash
cd "$JV_REPO"
sudo bash image/build-pi.sh \
  "$JV_BASE" "$JV_CORE" "$JV_REPO/target/release/justverify" \
  "$JV_ELECTRS" "$JV_TAG" "$JV_MEMPOOL" "$JV_I2PD" \
  2>&1 | tee .state/build-guide/image-build.log
sudo bash image/verify-pi.sh "dist/justverify-$JV_TAG.img.xz" \
  2>&1 | tee .state/build-guide/image-verify.log
```

Assembly verifies inputs, installs runtime/systemd units offline, removes machine identities, creates **one OS plus a separate data partition**, removes caches, zeroes unused filesystem blocks and compresses the image. It does not create two OS slots. Never use a booted VM/Pi disk as the base.

Current source reserves 0.5% of the ext4 data volume for root, including after first-boot expansion. The published beta1 image used 5%; updating source alone does not change an installed drive.

The verifier checks the filesystem, packaged source/binary hashes, ownership, enabled units, ARM executables, Python imports and absence of generated identities. It does **not** boot a Pi or prove synchronization, Tor reachability or physical wallet connectivity. Diagnose any failure before proceeding.

## 6. Checksum, extract and install

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

| Output | Purpose |
|---|---|
| `dist/justverify-0.1.0-beta7-local1.img` | Extracted image to select in balenaEtcher |
| `dist/justverify-0.1.0-beta7-local1.img.xz` | Compressed image for download/storage |
| `dist/justverify-0.1.0-beta7-local1-SHA256SUMS` | Both file hashes; check from `dist/` |
| `dist/justverify-0.1.0-beta7-local1.layout.json` / `.size-audit.json` | Partition layout and size audit |
| `dist/os-packages.tsv` | Actual image package inventory |
| `.state/build-guide/` | Source commit/patch, logs, local component/test evidence |

A different `JV_TAG` changes the filenames. SHA256 is an integrity check, not a publisher signature. This example creates an unsigned local build. Redistribution also requires your exact source/patches, corresponding component sources/licenses, support/test report and your own signing process. See [third-party notices](../licenses/THIRD_PARTY_NOTICES.md) and the [release source assets](https://github.com/dontrustjustverify/justverify/releases/tag/v0.1.0-beta7). Do not reuse the official signature for a changed file.

Follow [installation](INSTALL.md) with Etcher validation enabled. Direct XZ input failed checksum validation on the tested macOS/Etcher 2.1.6 setup; the **extracted IMG** passed. Then test initial setup, Core/electrs/Tor, mempool port 3006, LAN/onion wallets, reboot and recovery on a physical Pi 5. Mark unexecuted tests `NOT RUN`/`BLOCKED`. [TESTING.md](TESTING.md) lists the remaining release gates.

## Troubleshooting and resuming

| Symptom | Action |
|---|---|
| Root/architecture or loop/mount error | Use ARM64 Linux with sudo and loop devices for assembly; never supply a physical disk instead |
| `libclang` / RocksDB error | Check clang, libclang-dev and build-essential; preserve the compile log |
| Mempool Rust error | Check `RUSTUP_TOOLCHAIN=1.84.1`; do not regenerate dependency locks to hide a failure |
| Test permission denied | Check parent-directory traversal and public binary/source permissions for `justverify`; keep wallet/runtime directories private |
| Port occupied / failed test state exists | Stop only your own test process, keep old evidence and retry in a new test path |
| `electrs differs from tested build` | Run section 4 on that exact new binary and record local evidence |
| Image output/intermediate exists | Keep failed logs/files; use a new `JV_TAG` or fresh checkout; never overwrite a release image |
| Build killed / disk full | Check RAM and free disk including `/var/tmp`; reduce concurrency or enlarge the builder |

To resume in a new shell, restore `JV_WORK`, `JV_REPO`, `JV_TAG`, `JV_BASE`, `JV_CORE`, `JV_ELECTRS` and `JV_MEMPOOL` to the paths used for that build, enable `set -euo pipefail`, and `cd "$JV_REPO"`. Reuse verified downloads/completed outputs; do not rerun commands requiring a new directory over existing output. For another test attempt use new `tests-...` and `jv-mempool-test-...` paths, then preserve both attempts' reports. For another assembly choose a new tag.
