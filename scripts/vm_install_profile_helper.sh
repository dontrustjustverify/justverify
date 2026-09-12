#!/bin/bash
set -euo pipefail
[[ $EUID = 0 && $(hostname) = justverify-dev ]] || exit 1
cd /home/builder/justverify
install -m 0755 scripts/profile_helper.py /usr/libexec/justverify-profile
printf 'justverify ALL=(root) NOPASSWD: /usr/libexec/justverify-profile ""\n' > /etc/sudoers.d/justverify-profile
chmod 0440 /etc/sudoers.d/justverify-profile
visudo -cf /etc/sudoers.d/justverify-profile
install -m 0644 catalog/runtime-options.json /opt/justverify/catalog/
install -d -m 0700 -o justverify -g justverify /srv/justverify/data/instances
for version in 31.1 22.0; do
  install -d /opt/justverify/versions/$version/bitcoin-$version/bin
  install -m 0755 /home/builder/core-matrix/$version/bitcoin-$version/bin/bitcoind /opt/justverify/versions/$version/bitcoin-$version/bin/bitcoind
  runuser -u justverify -- /opt/justverify/bin/justverify prepare-instance --root /srv/justverify/data/instances --version "$version" --network regtest > /dev/null
  if [[ ! -e /srv/justverify/data/instances/regtest/$version/managed.conf ]]; then
    install -m 0600 -o justverify -g justverify /dev/null /srv/justverify/data/instances/regtest/$version/managed.conf
  fi
done
