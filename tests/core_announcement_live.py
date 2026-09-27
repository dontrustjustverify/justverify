#!/usr/bin/env python3
"""Verified Core release matrix: actual fresh-regtest RPC and announcement state."""
import argparse
import hashlib
import importlib.util
import json
import pathlib
import subprocess
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('announcement', ROOT / 'scripts/core_service.py')
announcement = importlib.util.module_from_spec(spec); spec.loader.exec_module(announcement)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--matrix', type=pathlib.Path, required=True)
    parser.add_argument('--hostname', type=pathlib.Path, required=True)
    parser.add_argument('--result', type=pathlib.Path, required=True)
    args = parser.parse_args()
    hostname = announcement.onion_address(args.hostname.read_text())
    releases = json.loads((ROOT / 'catalog/releases.json').read_text())['releases']
    report = {'status': 'RUNNING', 'scope': 'isolated regtest, real verified binaries; address registration, not external reachability', 'versions': []}
    args.result.write_text(json.dumps(report, indent=2) + '\n')
    for release in releases:
        if release['verification'] != 'PASS': continue
        version = release['version']
        binary = args.matrix / version / ('bitcoin-' + version) / 'bin/bitcoind'
        assert hashlib.sha256(binary.read_bytes()).hexdigest() == release['arm64_binary_sha256']
        for incoming, outgoing, proxy in [('clearnet,tor', 'ipv4,ipv6,onion', '0'), ('tor', 'onion', '0'), ('clearnet,tor', 'ipv4,ipv6,onion', '127.0.0.1:9050'), ('none', 'ipv4,ipv6,onion', '0'), ('tor', 'ipv4,ipv6', '0')]:
            policy = '# JustVerify incoming=' + incoming + '\n' + ''.join('onlynet=' + n + '\n' for n in outgoing.split(',')) + 'proxy=' + proxy + '\n'
            generated = announcement.announcement_args(policy, 'main', hostname)
            with tempfile.TemporaryDirectory(prefix='jv-announcement-live-') as temporary:
                data = pathlib.Path(temporary)
                (data / 'bitcoin.conf').write_text('regtest=1\nserver=1\ndisablewallet=1\ndnsseed=0\nlistenonion=0\nonion=127.0.0.1:9050\n' + policy + ('noonion=1\n' if 'onion' not in outgoing.split(',') else '') + '[regtest]\nconnect=0\nrpcport=29573\nbind=127.0.0.1:29574\n')
                with (data / 'console.log').open('wb') as log:
                    process = subprocess.Popen([str(binary), '-datadir=' + temporary, '-dbcache=32', *generated], stdout=log, stderr=log)
                cli = [str(binary.with_name('bitcoin-cli')), '-datadir=' + temporary]
                try:
                    deadline = time.monotonic() + 20
                    while True:
                        r = subprocess.run([*cli, 'getnetworkinfo'], capture_output=True)
                        if r.returncode == 0: break
                        if time.monotonic() >= deadline or process.poll() is not None:
                            raise AssertionError('Core startup failed for ' + version)
                        time.sleep(.1)
                    info = json.loads(r.stdout)
                    advertised = [a for a in info['localaddresses'] if a['address'].endswith('.onion')]
                    expected = 'tor' in incoming.split(',') and 'onion' in outgoing.split(',')
                    assert bool(advertised) == expected
                    if expected: assert advertised[0]['address'] == hostname and advertised[0]['port'] == 8333
                    networks = {n['name']: n for n in info['networks']}
                    assert networks['ipv4']['proxy'] == ('' if proxy == '0' else proxy)
                    assert networks['ipv6']['proxy'] == ('' if proxy == '0' else proxy)
                    assert networks['onion']['reachable'] == ('onion' in outgoing.split(','))
                    assert generated[0] == '-discover=' + str(int('clearnet' in incoming.split(',') and proxy == '0'))
                finally:
                    if process.poll() is None:
                        subprocess.run([*cli, 'stop'], capture_output=True, timeout=10)
                        process.wait(timeout=30)
        report['versions'].append({'version': version, 'cases': 5, 'status': 'PASS'})
        args.result.write_text(json.dumps(report, indent=2) + '\n')
        print(version + ': 5 actual startup/RPC cases PASS', flush=True)
    assert len(report['versions']) == 32
    report['status'] = 'PASS'
    args.result.write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__': main()
