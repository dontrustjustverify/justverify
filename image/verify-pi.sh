#!/bin/bash
set -euo pipefail
[[ $(uname -s) = Linux && $EUID = 0 ]] || exit 1
artifact=${1:?compressed image required}
source_root=$(cd "$(dirname "$0")/.." && pwd)
# Full image extraction must not depend on a RAM-backed /tmp fitting the rootfs.
work=$(mktemp -d /var/tmp/jv-image-verify.XXXXXX)
loop=''
cleanup() { umount "$work/root/boot/firmware" 2>/dev/null || true; umount "$work/root/tmp" 2>/dev/null || true; umount "$work/root" 2>/dev/null || true; [[ -z "$loop" ]] || losetup -d "$loop"; rm -f "$work/image.img" "$work/core-help.txt"; rm -rf "$work/runtime"; rmdir "$work/root" "$work"; }
trap cleanup EXIT
mkdir "$work/root"
xz -dc "$artifact" | dd of="$work/image.img" bs=4M conv=sparse status=none
loop=$(losetup --find --show --partscan --read-only "$work/image.img")
e2fsck -fn "${loop}p2"
mount -o ro,noload "${loop}p2" "$work/root"
mount -o ro "${loop}p1" "$work/root/boot/firmware"
test ! -s "$work/root/etc/machine-id"
test -z "$(find "$work/root/etc/ssh" -name 'ssh_host_*_key' -print -quit)"
test ! -e "$work/root/var/lib/justverify/web/private-key.pem"
test ! -e "$work/root/var/lib/justverify/web/setup-token"
test ! -e "$work/root/etc/justverify/node-ready.json"
test ! -e "$work/root/var/lib/justverify/versions/active.json"
test ! -e "$work/root/var/lib/justverify-tor/p2p/hs_ed25519_secret_key"
test ! -e "$work/root/var/lib/justverify-tor/electrum/hs_ed25519_secret_key"
test ! -e "$work/root/var/lib/justverify-tor/rpc/hs_ed25519_secret_key"
test ! -e "$work/root/var/lib/justverify-tor/web/hs_ed25519_secret_key"
test ! -e "$work/root/var/lib/justverify/web/admin.json"
test ! -e "$work/root/var/lib/justverify/web/sessions.json"
test ! -e "$work/root/var/lib/mysql"
chroot "$work/root" /opt/justverify/bin/electrs --version
chroot "$work/root" /usr/bin/tor --version
chroot "$work/root" /opt/justverify/i2pd/i2pd --version
(cd "$work/root/opt/justverify/i2pd" && sha256sum -c SHA256SUMS > /dev/null)
chroot "$work/root" /usr/bin/node --version
chroot "$work/root" /usr/sbin/mariadbd --version
(cd "$work/root/opt/justverify/mempool" && sha256sum -c SHA256SUMS > /dev/null)
chroot "$work/root" /usr/sbin/visudo -cf /etc/sudoers.d/justverify-core
chroot "$work/root" /usr/sbin/visudo -cf /etc/sudoers.d/justverify-profile
chroot "$work/root" /usr/sbin/visudo -cf /etc/sudoers.d/justverify-install-core
chroot "$work/root" /usr/sbin/visudo -c
chroot "$work/root" /usr/bin/gpg --version | head -n 2
chroot "$work/root" /bin/sh -n /opt/justverify/scripts/firstboot.sh
python3 - "$work/root" "$source_root" <<'VERIFY_HASH'
import hashlib,json,pathlib,sys
root=pathlib.Path(sys.argv[1]);catalog=root/'opt/justverify/catalog'
source=pathlib.Path(sys.argv[2])
assert (root/'opt/justverify/scripts/i2p_service.py').read_bytes()==(source/'scripts/i2p_service.py').read_bytes()
assert (root/'etc/justverify/i2pd.conf').read_bytes()==(source/'image/i2pd.conf').read_bytes()
assert (root/'etc/systemd/system/justverify-i2p.service').read_bytes()==(source/'image/systemd/justverify-i2p.service').read_bytes()
assert (root/'etc/systemd/system/multi-user.target.wants/justverify-i2p.service').is_symlink()
assert not (root/'var/lib/justverify-i2p/router.keys').exists()
assert not list((root/'srv/justverify/data').rglob('i2p_private_key'))
router=json.loads((root/'opt/justverify/i2pd/manifest.json').read_text())
assert all(router.get(k)==v for k,v in json.loads((source/'catalog/i2pd.json').read_text()).items())
admin=root/'etc/sudoers.d/00-justverify-admin'
assert admin.read_bytes()==(source/'image/justverify-admin.sudoers').read_bytes()
assert admin.stat().st_uid==0 and admin.stat().st_mode&0o777==0o440
assert (root/'opt/justverify/scripts/ssh-firstboot.sh').read_bytes()==(source/'image/ssh-firstboot.sh').read_bytes()
assert (root/'etc/ssh/sshd_config.d/00-justverify.conf').read_bytes()==(source/'image/ssh/00-justverify.conf').read_bytes()
for item in (source/'catalog').glob('*.json'):
    assert (catalog/item.name).read_bytes()==item.read_bytes(),f'stale packaged catalog: {item.name}'
assert (root/'usr/libexec/justverify-restart-core').read_bytes()==(source/'image/restart-core.sh').read_bytes(),'stale restart helper'
for name in ('server.py','node_admin.py','device_settings.py','remote_web.py','rpc_gateway.py','manage_clients.py','electrum_qr.py','electrum_tls.py','requirements.lock','requirements.arm64.lock','wallet_gateway.py','watch_only.py','remote_rpc.py','rpc_qr.py','mempool_proxy.py','mempool_frontend.json'):
    packaged=root/'opt/justverify/web'/name
    assert packaged.read_bytes()==(source/'web'/name).read_bytes(),f'stale packaged web component: {name}'
    assert packaged.stat().st_uid==0 and packaged.stat().st_mode&0o022==0
for name in ('volume_setup.py','storage_service.py','device_service.py','storage_probe.py','disk_inventory.py','backup_bundle.py','backup_service.py','backup_guard.py','node_ready.py','publish_onions.py','mempool_service.py','mempool_data.py'):
    packaged=root/'opt/justverify/scripts'/name
    assert packaged.read_bytes()==(source/'scripts'/name).read_bytes(),f'stale packaged storage/profile component: {name}'
    assert packaged.stat().st_uid==0 and packaged.stat().st_mode&0o022==0
if (root/'etc/justverify-factory.json').exists():
    helper=root/'opt/justverify/scripts/factory_volume.py'
    assert helper.read_bytes()==(source/'scripts/factory_volume.py').read_bytes()
    assert helper.stat().st_uid==0 and helper.stat().st_mode&0o022==0
    assert not (root/'var/lib/justverify-factory/provision.json').exists()
    layout=json.loads((root/'etc/justverify-factory.json').read_text())
    assert 'resize' not in (root/'boot/firmware/cmdline.txt').read_text().split(), 'unsafe Pi OS root resize hook enabled on single-OS data layout'
    assert layout['kind']=='single-os' and [p['role'] for p in layout['partitions']]==['boot','root','data']
    assert (root/'opt/justverify/scripts/firstboot.sh').read_bytes()==(source/'image/firstboot.sh').read_bytes()
assert (root/'usr/libexec/justverify-profile').read_bytes()==(source/'scripts/profile_helper.py').read_bytes(),'stale packaged profile helper'
assert (root/'opt/justverify/bin/justverify').read_bytes()==(source/'target/release/justverify').read_bytes(),'stale packaged TUI'
core=next(v for v in json.loads((catalog/'releases.json').read_text())['releases'] if v['version']=='31.1')
electrs=json.loads((catalog/'electrs.json').read_text())
assert hashlib.sha256((root/'opt/justverify/core/bin/bitcoind').read_bytes()).hexdigest()==core['arm64_binary_sha256']
assert hashlib.sha256((root/'opt/justverify/bin/electrs').read_bytes()).hexdigest()==electrs['tested_arm64_binary_sha256']
for item in (source/'web/static').iterdir():
    if item.is_file():
        packaged=root/'opt/justverify/web/static'/item.name
        assert packaged.read_bytes()==item.read_bytes(),f'stale static file: {item.name}'
        assert packaged.stat().st_uid==0 and packaged.stat().st_mode&0o022==0
assert (root/'opt/justverify/licenses/mining-pools/LICENSE').read_bytes()==(source/'licenses/mining-pools/LICENSE').read_bytes()
assert not (root/'opt/justverify/core/bin/bitcoin-qt').exists()
assert not (root/'opt/justverify/core/libexec').exists()
import tomllib
assert json.loads((root/'etc/justverify/os-release.json').read_text())['version']==tomllib.loads((source/'Cargo.toml').read_text())['package']['version']
for name in ('policy','electrs','tor','versions','storage','device','backup','console','mempool','mempool-web'):
    assert (root/f'etc/systemd/system/multi-user.target.wants/justverify-{name}.service').is_symlink()
assert (root/'etc/systemd/system/justverify-electrs.service.wants/justverify-electrum-tls.service').is_symlink()
assert (root/'etc/systemd/system/justverify-electrum-tls.service').read_bytes()==(source/'image/systemd/justverify-electrum-tls.service').read_bytes()
assert (root/'etc/systemd/system/justverify-tor.service').read_bytes()==(source/'image/systemd/justverify-tor.service').read_bytes()
assert (root/'etc/systemd/system/justverify-backup.service').read_bytes()==(source/'image/systemd/justverify-backup.service').read_bytes()
assert (root/'etc/justverify/torrc').read_bytes()==(source/'image/torrc').read_bytes()
template=root/'opt/justverify/templates/torrc'
assert template.read_bytes()==(source/'image/torrc').read_bytes()
assert template.stat().st_uid==0 and template.stat().st_mode&0o022==0
versioned=root/'opt/justverify/versions/31.1/bitcoin-31.1/bin/bitcoind'
assert hashlib.sha256(versioned.read_bytes()).hexdigest()==core['arm64_binary_sha256']
assert not json.loads((root/'etc/justverify/versions.json').read_text()).get('allow_initial_selection',False)
assert (root/'etc/systemd/system/userconfig.service').is_symlink()
assert (root/'etc/systemd/system/userconfig.service').readlink()==pathlib.Path('/dev/null')
for path in [versioned,root/'usr/libexec/justverify-profile',root/'usr/libexec/justverify-install-core',root/'opt/justverify/scripts/fetch_core.py',root/'opt/justverify/scripts/node_ready.py']:
    assert path.stat().st_uid==0 and path.stat().st_mode&0o022==0
for name in ('core','electrs','policy'):
    unit=(root/f'etc/systemd/system/justverify-{name}.service').read_text()
    assert 'ConditionPathExists=/etc/justverify/node-ready.json' in unit and 'scripts/node_ready.py' in unit
for name in ('gpg','findmnt','lsblk','mount'):
    assert (root/f'usr/bin/{name}').exists()
for name in ('mkfs.ext4','e2fsck','wipefs','blkid'):
    assert (root/f'usr/sbin/{name}').exists()
assert (root/'opt/justverify/mempool/backend/index.js').is_file()
assert (root/'opt/justverify/mempool/web/ko/index.html').is_file()
assert (root/'opt/justverify/mempool/web/ja/index.html').is_file()
assert (root/'opt/justverify/mempool/web/en-US/index.html').is_file()
assert not (root/'srv/justverify/data/mempool').exists()
print('PASS verified hashes, version/setup tooling, root ownership, production guard and enabled services')
VERIFY_HASH
chroot "$work/root" /opt/justverify/bin/justverify --version
mkdir "$work/runtime"
mount --bind "$work/runtime" "$work/root/tmp"
chroot "$work/root" /opt/justverify/core/bin/bitcoind -datadir=/tmp -disablewallet -help > "$work/core-help.txt"
head -n 2 "$work/core-help.txt"
chroot "$work/root" /opt/justverify/venv/bin/python -B -c 'import sys, importlib.metadata; sys.path.insert(0,"/opt/justverify/web"); import aiohttp, server, device_settings, remote_web, rpc_gateway, manage_clients, electrum_qr, rpc_qr, wallet_gateway, watch_only; assert importlib.metadata.version("qrcode")=="8.2"; print("PASS web/device/remote/gateway/client/QR imports; aiohttp",aiohttp.__version__,"qrcode 8.2")'
systemd-analyze --root="$work/root" verify "$work/root/etc/systemd/system/justverify-"*.service
printf 'PASS filesystem, identity absence, ARM executables, Python runtime and systemd unit verification. Pi hardware boot NOT RUN.\n'
