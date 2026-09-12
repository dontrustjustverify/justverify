#!/bin/bash
set -euo pipefail
[[ $EUID = 0 && $(hostname) = justverify-dev ]] || exit 1
cd /home/builder/justverify
install -d /usr/libexec /opt/justverify/catalog
install -m 0755 image/restart-core.sh /usr/libexec/justverify-restart-core
printf 'justverify ALL=(root) NOPASSWD: /usr/libexec/justverify-restart-core ""\n' > /etc/sudoers.d/justverify-core
chmod 0440 /etc/sudoers.d/justverify-core
visudo -cf /etc/sudoers.d/justverify-core
cp catalog/*.json /opt/justverify/catalog/
install -d -m 0700 -o justverify -g justverify /var/lib/justverify/config /var/lib/justverify/preflight
if [[ ! -e /var/lib/justverify/config/managed.conf ]]; then install -m 0600 -o justverify -g justverify /dev/null /var/lib/justverify/config/managed.conf; fi
python3 - <<'PY'
import json,pathlib
p=json.load(open('image/profile.json'));p['network']='regtest';p['cookie']='/srv/justverify/data/core/regtest/.cookie';p['rpc_port']=18443
pathlib.Path('/etc/justverify/profile.json').write_text(json.dumps(p,indent=2)+'\n')
conf=pathlib.Path('/etc/justverify/bitcoin.conf');s=conf.read_text();line='includeconf=/var/lib/justverify/config/managed.conf\n'
if line not in s:conf.write_text(line+s)
PY
install -m 0644 image/systemd/justverify-policy.service /etc/systemd/system/
systemctl stop justverify-policy 2>/dev/null || true
systemctl stop justverify-manager justverify-web
install -m 0755 target/release/justverify /opt/justverify/bin/justverify
systemctl daemon-reload
systemctl enable justverify-policy
systemctl restart justverify-core
systemctl start justverify-manager justverify-web justverify-policy
