#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
scripts/vm_ssh.sh 'mkdir -p ~/justverify'
COPYFILE_DISABLE=1 tar --no-xattrs --exclude='*/__pycache__' --exclude='*.pyc' -czf - Cargo.toml Cargo.lock rust-toolchain.toml src scripts web catalog image tests licenses THIRD_PARTY_NOTICES.md | scripts/vm_ssh.sh 'tar -xzf - -C ~/justverify'
