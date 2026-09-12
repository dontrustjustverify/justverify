#!/bin/sh
set -eu
[ "$#" -eq 0 ] || exit 64
# Stop dependants deliberately: electrs0.11 exits when its P2P connection drops.
# Repeated owner-reviewed changes must not consume its crash restart budget.
/usr/bin/systemctl stop justverify-electrum-tls.service justverify-electrs.service
/usr/bin/systemctl reset-failed justverify-core.service justverify-electrs.service justverify-electrum-tls.service
/usr/bin/systemctl restart justverify-core.service
# Type=simple restart returning does not prove Core completed startup. Fail
# within the administration deadline before starting an indexer that would
# otherwise wait 120 seconds against a rejected Core configuration.
/usr/bin/python3 -c 'import sys; sys.path.insert(0,"/opt/justverify/scripts"); from wait_core_rpc import wait_ready; wait_ready("/etc/justverify/profile.json",20)'
/usr/bin/systemctl start justverify-electrs.service
exec /usr/bin/systemctl start justverify-electrum-tls.service
