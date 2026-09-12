#!/usr/bin/env python3
"""Publish only generated public hostnames; Tor keys remain in private state."""
import os, pathlib, re, time
for service in ('p2p', 'electrum', 'rpc', 'web'):
    if service == 'web' and 'HiddenServiceDir /var/lib/justverify-tor/web' not in pathlib.Path('/etc/justverify/torrc').read_text(): continue
    source = pathlib.Path('/var/lib/justverify-tor') / service / 'hostname'
    deadline = time.monotonic() + 20
    while not source.exists():
        if time.monotonic() >= deadline: raise SystemExit('Tor hostname generation timed out')
        time.sleep(.1)
    hostname = source.read_text().strip()
    if not re.fullmatch(r'[a-z2-7]{56}\.onion', hostname): raise SystemExit('Invalid v3 hostname')
    target = pathlib.Path('/run/justverify-tor') / (service + '.hostname')
    pending = target.with_suffix('.pending')
    pending.write_text(hostname + '\n')
    pending.chmod(0o644)
    os.replace(pending, target)
