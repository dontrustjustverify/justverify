#!/bin/sh
# User-requested LAN SSH default. Never reset an initialized user's password.
set -eu
umask 077
install -d -m 0700 -o root -g root /var/lib/justverify-ssh
if [ ! -f /var/lib/justverify-ssh/account-initialized ]; then
    usermod --shell /bin/bash justverify
    printf '%s\n' 'justverify:justverify' | chpasswd
    touch /var/lib/justverify-ssh/account-initialized
fi
ssh-keygen -A
/usr/sbin/sshd -t
