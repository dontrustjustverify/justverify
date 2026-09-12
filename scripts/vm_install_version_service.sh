#!/bin/bash
set -euo pipefail
[[ $EUID = 0 && $(hostname) = justverify-dev ]] || exit 1
cd /home/builder/justverify
install -d -m 0700 -o justverify -g justverify /var/lib/justverify/versions
install -m 0644 image/versions.json /etc/justverify/versions.json
# Explicit bootstrap allowance is confined to this disposable VM fixture.
python3 - <<'PY_CONFIG'
import json,pathlib
p=pathlib.Path('/etc/justverify/versions.json');value=json.loads(p.read_text());value['allow_initial_selection']=True;p.write_text(json.dumps(value)+'\n')
PY_CONFIG
install -m 0644 image/systemd/justverify-versions.service /etc/systemd/system/
systemctl stop justverify-policy justverify-manager justverify-web justverify-versions 2>/dev/null || true
install -m 0755 target/release/justverify /opt/justverify/bin/justverify
systemctl daemon-reload
systemctl start justverify-policy justverify-manager justverify-web
# The test starts the new service; do not enable it over an unregistered legacy development profile.
