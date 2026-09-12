#!/bin/bash
set -euo pipefail
[[ $EUID = 0 && $(hostname) = justverify-dev ]] || exit 1
cd /home/builder/justverify
command -v gpg >/dev/null
install -m 0755 scripts/install_core.py /usr/libexec/justverify-install-core
install -m 0755 scripts/fetch_core.py /opt/justverify/scripts/fetch_core.py
install -m 0644 catalog/trusted-builders.json /opt/justverify/catalog/
install -d -m 0700 -o justverify -g justverify /var/lib/justverify/downloads
printf 'justverify ALL=(root) NOPASSWD: /usr/libexec/justverify-install-core ""\n' > /etc/sudoers.d/justverify-install-core
chmod 0440 /etc/sudoers.d/justverify-install-core
visudo -cf /etc/sudoers.d/justverify-install-core
bash scripts/vm_install_version_service.sh
