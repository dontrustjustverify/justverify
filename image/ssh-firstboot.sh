#!/bin/sh
# User-requested LAN SSH default. Never reset an initialized user's password.
set -eu
umask 077
install -d -m 0700 -o root -g root /var/lib/justverify-ssh
# Fail before enabling SSH if an image omitted the owner's administration policy.
test -f /etc/sudoers.d/00-justverify-admin
/usr/sbin/visudo -c >/dev/null
if [ ! -f /var/lib/justverify-ssh/account-initialized ]; then
    usermod --shell /bin/bash justverify
    printf '%s\n' 'justverify:justverify' | chpasswd
    touch /var/lib/justverify-ssh/account-initialized
fi
ssh-keygen -A
/usr/sbin/sshd -t
