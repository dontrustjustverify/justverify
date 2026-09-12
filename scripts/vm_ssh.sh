#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
exec ssh -i .state/vm/id_ed25519 -p 22222 -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=.state/vm/known_hosts builder@127.0.0.1 "$@"
