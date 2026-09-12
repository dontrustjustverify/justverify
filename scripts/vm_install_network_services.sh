#!/bin/bash
set -euo pipefail
[[ $EUID = 0 && $(hostname) = justverify-dev ]] || exit 1
cd /home/builder/justverify
install -m 0755 /home/builder/electrs/target/release/electrs /opt/justverify/bin/electrs
install -m 0755 scripts/publish_onions.py /opt/justverify/scripts/
install -m 0644 image/electrs.toml image/torrc /etc/justverify/
python3 - <<'PY'
from pathlib import Path
p=Path('/etc/justverify/electrs.toml');s=p.read_text().replace('"bitcoin"','"regtest"').replace('core/.cookie','core/regtest/.cookie').replace(':8332',':18443').replace(':8333',':18444');p.write_text(s)
p=Path('/etc/justverify/torrc');p.write_text(p.read_text().replace('127.0.0.1:8333','127.0.0.1:18444'))
PY
mountpoint -q /srv/justverify/data
install -d -m 0700 -o justverify -g justverify /srv/justverify/data/electrs
install -m 0644 image/systemd/justverify-electrs.service image/systemd/justverify-tor.service /etc/systemd/system/
systemctl stop tor.service tor@default.service
systemctl disable tor.service tor@default.service
systemctl daemon-reload
systemctl enable justverify-electrs justverify-tor
systemctl restart justverify-electrs justverify-tor
systemd-analyze verify /etc/systemd/system/justverify-electrs.service /etc/systemd/system/justverify-tor.service
