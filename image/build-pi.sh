#!/bin/bash
# Development image builder: root on isolated ARM Linux, regular file output only.
set -euo pipefail
cd "$(dirname "$0")/.."
[[ $(uname -s) = Linux && $(uname -m) = aarch64 && $EUID = 0 ]] || { echo 'Run in the isolated ARM Linux builder as root'; exit 1; }
base=${1:?verified base .img.xz required}
core=${2:?verified extracted ARM Core directory required}
binary=${3:?ARM Linux JustVerify executable required}
electrs=${4:?verified ARM electrs executable required}
build_tag=${5:-0.1.0-beta1}
mempool=${6:?verified native mempool bundle directory required}
(cd "$mempool" && sha256sum -c SHA256SUMS > /dev/null)
[[ "$build_tag" =~ ^[A-Za-z0-9.-]+$ ]] || exit 1
out="$PWD/dist/justverify-${build_tag}.img"
mkdir -p dist
[[ ! -e "$out" && ! -e "$out.xz" ]] || { echo 'Output exists; choose a new build directory'; exit 1; }
python3 - "$base" <<'PY'
import hashlib,json,sys
m=json.load(open('catalog/pi-base.json'))
with open(sys.argv[1],'rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==m['sha256'],'base checksum mismatch'
PY
python3 - "$core" "$electrs" <<'CHECK_COMPONENTS'
import hashlib,json,pathlib,sys
release=next(v for v in json.load(open('catalog/releases.json'))['releases'] if v['version']=='31.1')
assert hashlib.sha256((pathlib.Path(sys.argv[1])/'bin/bitcoind').read_bytes()).hexdigest()==release['arm64_binary_sha256'],'Core differs from signature-verified artifact'
electrs=json.load(open('catalog/electrs.json'))
assert hashlib.sha256(pathlib.Path(sys.argv[2]).read_bytes()).hexdigest()==electrs['tested_arm64_binary_sha256'],'electrs differs from tested build; verify new build before packaging'
CHECK_COMPONENTS
xz -dc "$base" > "$out"
python3 - "$out" <<'PY'
import hashlib,json,sys
m=json.load(open('catalog/pi-base.json'))
with open(sys.argv[1],'rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==m['extracted_sha256'],'extracted checksum mismatch'
PY
truncate -s 8G "$out"
loop=$(losetup --find --show --partscan "$out")
mountdir=$(mktemp -d)
cleanup() { umount -R "$mountdir" 2>/dev/null || true; losetup -d "$loop"; rmdir "$mountdir"; }
trap cleanup EXIT
parted -s "$loop" resizepart 2 100%
partprobe "$loop"
e2fsck -fy "${loop}p2" || [[ $? = 1 ]]
resize2fs "${loop}p2"
mount "${loop}p2" "$mountdir"
mount "${loop}p1" "$mountdir/boot/firmware"
install -d "$mountdir/opt/justverify/bin" "$mountdir/opt/justverify/scripts" "$mountdir/etc/justverify" "$mountdir/srv/justverify/data"
install -m 0755 "$electrs" "$mountdir/opt/justverify/bin/electrs"
install -m 0755 "$binary" "$mountdir/opt/justverify/bin/justverify"
install -d -m 0755 "$mountdir/opt/justverify/versions/31.1"
cp -a "$core" "$mountdir/opt/justverify/versions/31.1/bitcoin-31.1"
# Headless appliance: keep official CLI/daemon/utilities and notices byte-identical.
# Qt and upstream test executables remain in the verified source artifact cache.
rm -f "$mountdir/opt/justverify/versions/31.1/bitcoin-31.1/bin/bitcoin-qt"
rm -rf "$mountdir/opt/justverify/versions/31.1/bitcoin-31.1/libexec"
ln -s versions/31.1/bitcoin-31.1 "$mountdir/opt/justverify/core"
cp -a catalog "$mountdir/opt/justverify/catalog"
cp -a licenses "$mountdir/opt/justverify/licenses"
install -m 0644 licenses/THIRD_PARTY_NOTICES.md "$mountdir/opt/justverify/THIRD_PARTY_NOTICES.md"
cp -a web "$mountdir/opt/justverify/web"
cp -a "$mempool" "$mountdir/opt/justverify/mempool"
find "$mountdir/opt/justverify/web" -type d -name __pycache__ -prune -exec rm -rf {} +
chown -R root:root "$mountdir/opt/justverify"
chmod -R go-w "$mountdir/opt/justverify"
install -m 0755 scripts/fetch_core.py scripts/web_identity.py scripts/owner_console.py scripts/disk_inventory.py scripts/storage_probe.py scripts/volume_setup.py scripts/storage_service.py scripts/device_service.py scripts/backup_bundle.py scripts/backup_service.py scripts/backup_guard.py scripts/wait_core_rpc.py scripts/node_ready.py scripts/publish_onions.py scripts/mempool_service.py scripts/mempool_data.py image/firstboot.sh "$mountdir/opt/justverify/scripts/"
install -d "$mountdir/usr/libexec" "$mountdir/etc/sudoers.d"
install -m 0755 image/restart-core.sh "$mountdir/usr/libexec/justverify-restart-core"
install -m 0755 scripts/profile_helper.py "$mountdir/usr/libexec/justverify-profile"
install -d "$mountdir/opt/justverify/templates"
install -m 0644 image/torrc "$mountdir/opt/justverify/templates/torrc"
install -m 0755 scripts/install_core.py "$mountdir/usr/libexec/justverify-install-core"
install -m 0440 image/justverify-profile.sudoers "$mountdir/etc/sudoers.d/justverify-profile"
install -m 0440 image/justverify-install-core.sudoers "$mountdir/etc/sudoers.d/justverify-install-core"
printf '{"version":"%s"}\n' "$build_tag" > "$mountdir/etc/justverify/os-release.json"
install -m 0644 image/versions.json "$mountdir/etc/justverify/versions.json"
install -m 0644 image/profile.json "$mountdir/etc/justverify/profile.json"
install -m 0440 image/justverify-core.sudoers "$mountdir/etc/sudoers.d/justverify-core"
install -m 0644 image/electrs.toml image/torrc "$mountdir/etc/justverify/"
install -m 0644 image/bitcoin.conf "$mountdir/etc/justverify/bitcoin.conf"
install -m 0755 image/ssh-firstboot.sh "$mountdir/opt/justverify/scripts/ssh-firstboot.sh"
install -d "$mountdir/etc/ssh/sshd_config.d" "$mountdir/etc/systemd/system/ssh.service.d"
install -m 0644 image/ssh/00-justverify.conf "$mountdir/etc/ssh/sshd_config.d/00-justverify.conf"
printf '[Unit]\nRequires=justverify-ssh-init.service\nAfter=justverify-ssh-init.service\n' > "$mountdir/etc/systemd/system/ssh.service.d/justverify.conf"
install -m 0644 image/systemd/*.service "$mountdir/etc/systemd/system/"
# Prevent service startup while assembling the offline image.
printf '#!/bin/sh\nexit 101\n' > "$mountdir/usr/sbin/policy-rc.d"
chmod 755 "$mountdir/usr/sbin/policy-rc.d"
mount --rbind /dev "$mountdir/dev"
mount --make-rslave "$mountdir/dev"
mount -t proc proc "$mountdir/proc"
mount -t sysfs sysfs "$mountdir/sys"
rm -f "$mountdir/etc/resolv.conf"
cp -L /etc/resolv.conf "$mountdir/etc/resolv.conf"
chroot "$mountdir" /bin/bash -ec '
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install --no-install-recommends -y python3-venv openssl avahi-daemon tor sudo gpg ca-certificates e2fsprogs util-linux nodejs=20.19.2+dfsg-1+deb13u2 mariadb-server=1:11.8.6-0+deb13u1
  id justverify >/dev/null 2>&1 || useradd --system --home-dir /var/lib/justverify --create-home --shell /usr/sbin/nologin justverify
  visudo -cf /etc/sudoers.d/justverify-core
  visudo -cf /etc/sudoers.d/justverify-profile
  visudo -cf /etc/sudoers.d/justverify-install-core
  python3 -m venv /opt/justverify/venv
  /opt/justverify/venv/bin/pip install --require-hashes --only-binary=:all: -r /opt/justverify/web/requirements.arm64.lock
  systemctl enable justverify-firstboot justverify-core justverify-manager justverify-web justverify-console justverify-storage justverify-device justverify-backup justverify-versions justverify-policy justverify-electrs justverify-tor avahi-daemon
  systemctl enable justverify-electrum-tls justverify-mempool justverify-mempool-web
  systemctl disable mariadb.service
  systemctl disable tor.service tor@default.service
  systemctl disable getty@tty1.service
  # Appliance ownership uses our fixed console; the OS dialog switches to tty8.
  systemctl disable userconfig.service
  systemctl mask userconfig.service
  systemctl enable ssh.service
  dpkg-query -W > /opt/justverify/os-packages.tsv
'
# The appliance owns its SQL store on NVMe; discard the unused apt-created store.
rm -rf "$mountdir/var/lib/mysql"
printf 'justverify\n' > "$mountdir/etc/hostname"
printf '127.0.0.1 localhost\n127.0.1.1 justverify\n' > "$mountdir/etc/hosts"
# Never distribute an assembled identity or shared credentials.
rm -f "$mountdir/etc/ssh/ssh_host_"* "$mountdir/usr/sbin/policy-rc.d"
truncate -s 0 "$mountdir/etc/machine-id"
rm -f "$mountdir/var/lib/dbus/machine-id"
ln -s /etc/machine-id "$mountdir/var/lib/dbus/machine-id"
cp "$mountdir/opt/justverify/os-packages.tsv" dist/os-packages.tsv
sync
cleanup
trap - EXIT
# Keep one OS and an automatically prepared data partition on the same device.
mkdir -p .state
pristine="$PWD/.state/justverify-${build_tag}-single-os-input.img"
[[ ! -e "$pristine" ]] || { echo 'Intermediate image exists; choose a new tag'; exit 1; }
mv "$out" "$pristine"
source_sha=$(sha256sum "$pristine" | cut -d ' ' -f 1)
python3 scripts/build_single_disk.py --source "$pristine" --source-sha256 "$source_sha" --output "$out"
python3 scripts/compact_factory_image.py "$out" --sha256 "$(sha256sum "$out" | cut -d ' ' -f 1)"
xz -T2 -6 "$out"
sha256sum "$out.xz" > dist/SHA256SUMS
printf 'Development image built; Pi boot, onboarding, data setup and release gates NOT RUN.\n'
