#!/usr/bin/env python3
"""Two fresh regtest nodes through real Tor; peer-side address gossip and blocks."""
import argparse
import base64
import hashlib
import http.client
import importlib.util
import json
import pathlib
import subprocess
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('announcement', ROOT / 'scripts/core_service.py')
announcement = importlib.util.module_from_spec(spec); spec.loader.exec_module(announcement)


def wait(check, seconds, label):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            value = check()
            if value: return value
        except (OSError, ValueError, KeyError): pass
        time.sleep(1)
    raise TimeoutError(label)


class Node:
    def __init__(self, binary, data, port, host):
        self.binary, self.data, self.port, self.host = binary, data, port, host
        data.mkdir(mode=0o700)
        policy = '# JustVerify incoming=tor\nonlynet=onion\n'
        (data / 'bitcoin.conf').write_text('regtest=1\nserver=1\ndisablewallet=1\ndnsseed=0\nlistenonion=0\nonion=127.0.0.1:29580\n' + policy + f'[regtest]\nconnect=0\nrpcport={port}\nbind=127.0.0.1:{port+1}=onion\n')
        with (data / 'console.log').open('wb') as log:
            self.process = subprocess.Popen([str(binary), '-datadir=' + str(data), '-dbcache=32', *announcement.announcement_args(policy, 'regtest', host)], stdout=log, stderr=log)
        wait(lambda: self.rpc('getnetworkinfo'), 30, 'Core startup')

    def rpc(self, method, params=None):
        cookie = (self.data / 'regtest/.cookie').read_bytes().strip()
        c = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        try:
            c.request('POST', '/', json.dumps({'id': 1, 'method': method, 'params': params or []}), {'Authorization': 'Basic ' + base64.b64encode(cookie).decode()})
            result = json.loads(c.getresponse().read())
            if result.get('error'): raise ValueError(method + ' failed')
            return result['result']
        finally: c.close()

    def stop(self):
        if self.process.poll() is None:
            self.rpc('stop'); self.process.wait(timeout=30)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--core', type=pathlib.Path, required=True); parser.add_argument('--root', type=pathlib.Path, required=True); args = parser.parse_args()
    root = args.root.resolve(); root.mkdir(mode=0o700)
    binary = args.core.resolve()
    release = next(r for r in json.loads((ROOT / 'catalog/releases.json').read_text())['releases'] if r['version'] == '31.1')
    assert hashlib.sha256(binary.read_bytes()).hexdigest() == release['arm64_binary_sha256']
    tor_config = root / 'torrc'
    tor_config.write_text(f'DataDirectory {root}/tor\nSocksPort 127.0.0.1:29580\nLog notice stdout\n' + ''.join(f'HiddenServiceDir {root}/hs-{name}\nHiddenServiceVersion 3\nHiddenServicePort 8333 127.0.0.1:{port+1}\n' for name, port in [('a', 29581), ('b', 29591)]))
    with (root / 'tor.log').open('wb') as log:
        tor = subprocess.Popen(['/usr/bin/tor', '-f', str(tor_config)], stdout=log, stderr=log)
    nodes = []; report = {'status': 'RUNNING', 'scope': 'real Tor network and two fresh Core31.1 regtest nodes', 'checks': []}
    def note(text):
        report['checks'].append(text); (root / 'result.json').write_text(json.dumps(report, indent=2) + '\n'); print(text, flush=True)
    try:
        wait(lambda: 'Bootstrapped 100%' in (root / 'tor.log').read_text(), 240, 'Tor bootstrap')
        hosts = [announcement.onion_address((root / ('hs-' + name) / 'hostname').read_text()) for name in ('a', 'b')]
        a = Node(binary, root / 'a', 29581, hosts[0]); nodes.append(a)
        b = Node(binary, root / 'b', 29591, hosts[1]); nodes.append(b)
        a.rpc('generatetodescriptor', [101, 'raw(51)'])
        a.rpc('addnode', [hosts[1] + ':8333', 'add'])
        def connected():
            peers = a.rpc('getpeerinfo') + b.rpc('getpeerinfo')
            assert all(p['network'] == 'onion' for p in peers)
            return any(p['inbound'] and p['version'] for p in peers) and any(not p['inbound'] and p['version'] for p in peers)
        wait(connected, 300, 'onion Bitcoin version handshake')
        note('actual Tor outgoing/incoming Bitcoin handshake; onion classification; no clearnet fallback')
        wait(lambda: b.rpc('getbestblockhash') == a.rpc('getbestblockhash') and not b.rpc('getblockchaininfo')['initialblockdownload'], 120, 'Tor block propagation')
        note('101 regtest blocks transferred over Tor and IBD finished')
        wait(lambda: any(row['address'] == hosts[0] and row['port'] == 8333 for row in b.rpc('getnodeaddresses', [0, 'onion'])), 180, 'peer-side P2P onion address gossip')
        note('remote Core learned announced onion address and public port8333 without manual address insertion')
        a.rpc('generatetodescriptor', [1, 'raw(51)'])
        wait(lambda: b.rpc('getbestblockhash') == a.rpc('getbestblockhash'), 60, 'subsequent Tor block')
        report.update(status='PASS', height=102, tip=a.rpc('getbestblockhash'))
    except Exception as error:
        report.update(status='FAIL', error=type(error).__name__ + ': ' + str(error)); raise
    finally:
        for node in nodes: node.stop()
        tor.terminate(); tor.wait(timeout=30)
        (root / 'result.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__': main()
