#!/usr/bin/env python3
"""Read-only evidence from an installed Pi; no wallet or configuration mutation.

Run as root through the authorized SSH connection. Credentials stay in memory;
the output contains hashes of identity/configuration files, never their contents.
This observes IBD/indexing and does not equate an active service with readiness.
"""
import base64
import hashlib
import json
import pathlib
import re
import subprocess
import time
import urllib.request


def command(*args):
    return subprocess.check_output(args, text=True).strip()


def main():
    path = pathlib.Path
    profile = json.loads(path('/etc/justverify/profile.json').read_text())
    cookie = path(profile['cookie']).read_bytes().strip()

    def rpc(method, params=None):
        request = urllib.request.Request(
            'http://127.0.0.1:' + str(profile['rpc_port']),
            json.dumps({'id': 1, 'method': method, 'params': params or []}).encode(),
            {'Content-Type': 'application/json',
             'Authorization': 'Basic ' + base64.b64encode(cookie).decode()},
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            result = json.load(response)
        assert result.get('error') is None, method
        return result['result']

    chain = rpc('getblockchaininfo')
    network = rpc('getnetworkinfo')
    tip = rpc('getblockheader', [chain['bestblockhash']])
    peers = rpc('getpeerinfo')
    identities = [
        '/etc/machine-id', '/etc/ssh/ssh_host_ed25519_key.pub',
        '/var/lib/justverify/web/certificate.pem',
        '/var/lib/justverify/web/admin.json', '/etc/justverify/profile.json',
        '/var/lib/justverify/web/preferences.json',
        '/var/lib/justverify/web/remote-web.json',
        '/var/lib/justverify/web/remote-rpc.json',
        profile['managed_config'],
    ]
    identities += [str(p) for p in path('/run/justverify-tor').glob('*.hostname')]
    identities += [str(p) for p in path('/etc/justverify').glob('*.json')]
    hashes = {p: hashlib.sha256(path(p).read_bytes()).hexdigest()
              for p in sorted(set(identities)) if path(p).is_file()}
    services = {}
    for name in ('firstboot', 'console', 'core', 'electrs', 'electrum-tls',
                 'manager', 'web', 'policy', 'versions', 'storage', 'backup',
                 'device', 'tor', 'ssh-init'):
        raw = command('systemctl', 'show', 'justverify-' + name,
                      '-p', 'ActiveState', '-p', 'SubState', '-p', 'NRestarts',
                      '-p', 'User', '-p', 'Result')
        services[name] = dict(line.split('=', 1) for line in raw.splitlines())
    snapshot = json.loads(command(
        'runuser', '-u', 'justverify', '--', '/opt/justverify/bin/justverify',
        'snapshot', '--socket', '/run/justverify/manager.sock'))
    journal = command('journalctl', '-b', '-u', 'justverify-tor',
                      '-o', 'cat', '--no-pager')
    progress = re.findall(r'Bootstrapped (\d+)%', journal)
    result = {
        'observed_unix': int(time.time()),
        'scope': 'Read-only actual installed Pi; no transaction/configuration changes',
        'model': path('/proc/device-tree/model').read_text().rstrip('\0'),
        'kernel': command('uname', '-r'),
        'boot_id': path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        'uptime_seconds': float(path('/proc/uptime').read_text().split()[0]),
        'block_devices': json.loads(command('lsblk', '-b', '-J', '-o',
                                           'NAME,SIZE,MODEL,SERIAL,FSTYPE,UUID,MOUNTPOINTS')),
        'mount': json.loads(command('findmnt', '-J', '-o', 'SOURCE,TARGET,UUID,FSTYPE',
                                   '--target', '/srv/justverify/data')),
        'identity_config_sha256': hashes,
        'binary_sha256': hashlib.sha256(path('/opt/justverify/bin/justverify').read_bytes()).hexdigest(),
        'services': services,
        'core': chain,
        'tip_header': tip,
        'network': {key: network.get(key) for key in
                    ('version', 'subversion', 'connections', 'connections_in',
                     'connections_out', 'networkactive', 'networks', 'warnings')},
        'peers_by_network': {n: sum(p.get('network') == n for p in peers)
                             for n in sorted({p.get('network', 'unknown') for p in peers})},
        'indexes': rpc('getindexinfo'),
        'mempool': rpc('getmempoolinfo'),
        'collector': {
            'chain': snapshot['rpc']['getblockchaininfo'],
            'electrs': snapshot.get('host', {}).get('electrs'),
            'tor': snapshot.get('host', {}).get('tor'),
        },
        'tor_bootstrap_percent': int(progress[-1]) if progress else 0,
        'tor_warning_count': len(re.findall(r'\[(?:warn|err)\]', journal)),
        'ntp': command('timedatectl', 'show', '-p', 'NTPSynchronized', '--value'),
        'static_sha256': {str(p.relative_to('/opt/justverify/web/static')):
                          hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in path('/opt/justverify/web/static').rglob('*') if p.is_file()},
    }
    assert result['model'].startswith('Raspberry Pi 5'), result['model']
    assert tip['height'] == chain['blocks'] and tip['hash'] == chain['bestblockhash']
    assert result['mount']['filesystems'][0]['target'] == '/srv/justverify/data'
    assert all(v['ActiveState'] == 'active' for v in services.values()), services
    assert services['web']['User'] == services['manager']['User'] == 'justverify'
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
