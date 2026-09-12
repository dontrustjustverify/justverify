#!/bin/bash
# This installer is exclusively for our disposable VM, not user hardware.
set -euo pipefail
[[ $EUID = 0 && $(hostname) = justverify-dev ]] || { echo 'Disposable justverify-dev VM required'; exit 1; }
cd /home/builder/justverify
id justverify >/dev/null 2>&1 || useradd --system --create-home --home-dir /var/lib/justverify --shell /usr/sbin/nologin justverify
install -d /opt/justverify/bin /opt/justverify/scripts /etc/justverify /srv/justverify/data
install -m 0755 target/release/justverify /opt/justverify/bin/justverify
if [[ ! -d /opt/justverify/core ]]; then cp -a /home/builder/artifacts/bitcoin-31.1 /opt/justverify/core; fi
cp -a web /opt/justverify/
install -m 0755 scripts/web_identity.py image/firstboot.sh /opt/justverify/scripts/
python3 -m venv /opt/justverify/venv
/opt/justverify/venv/bin/pip install -r web/requirements.lock
if [[ ! -e /var/lib/justverify-dev-data.img ]]; then
    truncate -s 4G /var/lib/justverify-dev-data.img
    mkfs.ext4 -q /var/lib/justverify-dev-data.img
    printf '/var/lib/justverify-dev-data.img /srv/justverify/data ext4 loop,nofail 0 0\n' >> /etc/fstab
fi
mountpoint -q /srv/justverify/data || mount /srv/justverify/data
install -d -m 0700 -o justverify -g justverify /srv/justverify/data/core
cat > /etc/justverify/bitcoin.conf <<'CONF'
regtest=1
server=1
disablewallet=1
natpmp=0
listen=1
dnsseed=0
[regtest]
connect=0
rpcbind=127.0.0.1
rpcallowip=127.0.0.1
bind=127.0.0.1
CONF
install -m 0644 image/systemd/*.service /etc/systemd/system/
mkdir -p /etc/systemd/system/justverify-manager.service.d
cat > /etc/systemd/system/justverify-manager.service.d/regtest.conf <<'UNIT'
[Service]
ExecStart=
ExecStart=/opt/justverify/bin/justverify daemon --cookie /srv/justverify/data/core/regtest/.cookie --rpc-port 18443 --socket /run/justverify/manager.sock
UNIT
systemctl daemon-reload
systemctl enable justverify-firstboot justverify-core justverify-manager justverify-web
systemctl start justverify-firstboot justverify-core justverify-manager justverify-web
systemctl is-active justverify-firstboot justverify-core justverify-manager justverify-web
