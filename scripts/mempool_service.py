#!/usr/bin/env python3
"""Run the installed explorer beside Core, with per-profile SQL and caches.

No owner keys are generated; MariaDB uses a private Unix socket and OS identity.
Never modifies Core settings or starts an index on a different profile's data.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import time
import urllib.request

STOP = False

def stop(*_):
    global STOP
    STOP = True


def rpc(profile, method):
    cookie = Path(profile['cookie']).read_bytes().strip()
    request = urllib.request.Request('http://127.0.0.1:' + str(profile['rpc_port']),
        json.dumps({'id': 1, 'method': method, 'params': []}).encode(),
        {'Authorization': 'Basic ' + base64.b64encode(cookie).decode(), 'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=8) as response:
        result = json.load(response)
    if result.get('error'):
        raise ValueError('Core RPC not ready')
    return result['result']


def electrs_header(port):
    with socket.create_connection(('127.0.0.1', port), 3) as sock:
        sock.settimeout(5)
        sock.sendall(b'{"id":1,"method":"blockchain.headers.subscribe","params":[]}\n')
        header = json.loads(sock.makefile('rb').readline())['result']
    tip = hashlib.sha256(hashlib.sha256(bytes.fromhex(header['hex'])).digest()).digest()[::-1].hex()
    return header['height'], tip


def atomic(path, data):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, indent=2) + '\n')
    tmp.chmod(0o600)
    tmp.replace(path)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--profile', type=Path, default=Path('/etc/justverify/profile.json'))
    p.add_argument('--data', type=Path, default=Path('/srv/justverify/data/mempool'))
    p.add_argument('--runtime', type=Path, default=Path('/run/justverify-mempool'))
    p.add_argument('--bundle', type=Path, default=Path('/opt/justverify/mempool'))
    p.add_argument('--api-port', type=int, default=8999)
    p.add_argument('--web-port', type=int, default=3006)
    p.add_argument('--electrum-port', type=int, default=50001)
    a = p.parse_args()
    assert os.geteuid() != 0, 'Explorer must run without root privileges'
    assert a.data.is_dir() and a.runtime.is_dir(), 'Prepared data volume and runtime required'
    for s in (signal.SIGINT, signal.SIGTERM): signal.signal(s, stop)
    status = a.runtime / 'status.json'
    atomic(status, {'state':'waiting'})
    while not STOP:
        processes = []
        logs = []
        try:
            raw = a.profile.read_bytes()
            profile = json.loads(raw)
            version, network = profile['version'], profile['network']
            assert re.fullmatch(r'\d+\.\d+(?:\.\d+)?', version)
            assert network in ('main', 'test', 'testnet4', 'signet', 'regtest')
            chain = rpc(profile, 'getblockchaininfo')
            assert chain['chain'] == network, 'Selected network must match the actual Core chain'
            indexes = rpc(profile, 'getindexinfo')
            reason = 'core_sync' if chain['initialblockdownload'] else 'txindex'
            if chain['initialblockdownload'] or not indexes.get('txindex', {}).get('synced'):
                atomic(status, {'state': reason, 'network': network, 'blocks': chain['blocks'], 'headers': chain['headers'], 'ibd': chain['initialblockdownload']})
                time.sleep(5)
                continue
            electrs_height, tip = electrs_header(a.electrum_port)
            if tip != chain['bestblockhash'] or electrs_height != chain['blocks']:
                atomic(status, {'state': 'electrs_sync', 'network': network, 'blocks': chain['blocks'], 'electrs_height': electrs_height})
                time.sleep(5)
                continue
            atomic(status, {'state':'starting', 'network':network})
            folder = a.data / (network + '-' + version + ('-watch-only' if profile.get('watch_only') else ''))
            folder.mkdir(mode=0o700, exist_ok=True)
            assert not folder.is_symlink()
            db = folder / 'mysql'
            db.mkdir(mode=0o700, exist_ok=True)
            cache = folder / 'cache'
            cache.mkdir(mode=0o700, exist_ok=True)
            # Oversized disposable cache is retained for diagnosis, not erased.
            for name in ('rbfcache.json', 'tmp-rbfcache.json'):
                path = cache / name
                if path.is_file() and path.stat().st_size > 64 * 1024 * 1024:
                    path.rename(cache / (name + '.oversized-' + str(time.time_ns())))
            sql_socket = a.runtime / 'mysql.sock'
            if not (db / 'mysql').is_dir():
                subprocess.run(['mariadb-install-db', '--no-defaults', '--datadir=' + str(db), '--auth-root-authentication-method=socket', '--auth-root-socket-user=justverify', '--skip-test-db'], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            def start(command, name):
                log = (folder / name).open('ab'); logs.append(log)
                process = subprocess.Popen(command, stdout=log, stderr=log); processes.append(process)
                return process
            database = start(['mariadbd', '--no-defaults', '--datadir=' + str(db), '--socket=' + str(sql_socket), '--pid-file=' + str(a.runtime / 'mysql.pid'), '--skip-networking', '--innodb-buffer-pool-size=128M', '--max-connections=20', '--innodb-log-file-size=32M'], 'database.log')
            sql = ['mariadb', '--no-defaults', '--socket=' + str(sql_socket), '--user=justverify']
            deadline = time.monotonic() + 60
            while not STOP:
                if database.poll() is not None: raise RuntimeError('Database stopped')
                if subprocess.run(sql + ['-e', 'SELECT 1'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0: break
                if time.monotonic() > deadline: raise TimeoutError('Database startup')
                time.sleep(.5)
            if STOP: break
            subprocess.run(sql + ['-e', 'CREATE DATABASE IF NOT EXISTS mempool CHARACTER SET utf8mb4;'], check=True, stdout=subprocess.DEVNULL)
            conf = {
                'MEMPOOL': {'NETWORK': {'main':'mainnet','test':'testnet'}.get(network, network), 'BACKEND':'electrum', 'HTTP_PORT': a.api_port, 'CACHE_DIR': str(cache), 'INDEXING_BLOCKS_AMOUNT':52560, 'BLOCKS_SUMMARIES_INDEXING':False, 'GOGGLES_INDEXING':False, 'POOLS_JSON_URL':f'http://127.0.0.1:{a.web_port}/resources/pools-v2.json', 'POOLS_JSON_TREE_URL':f'http://127.0.0.1:{a.web_port}/resources/pools-tree.json', 'EXTERNAL_ASSETS':[], 'AUTOMATIC_POOLS_UPDATE':False, 'RUST_GBT':True, 'STDOUT_LOG_MIN_PRIORITY':'info'},
                'CORE_RPC': {'HOST':'127.0.0.1', 'PORT':profile['rpc_port'], 'COOKIE':True, 'COOKIE_PATH':profile['cookie']},
                'ELECTRUM': {'HOST':'127.0.0.1', 'PORT':a.electrum_port, 'TLS_ENABLED':False},
                'DATABASE': {'ENABLED':True, 'SOCKET':str(sql_socket), 'DATABASE':'mempool', 'USERNAME':'justverify', 'PASSWORD':'', 'PID_DIR':str(a.runtime), 'POOL_SIZE':10},
                'STATISTICS': {'ENABLED':True}, 'FIAT_PRICE': {'ENABLED':False}, 'LIGHTNING': {'ENABLED':False}, 'SYSLOG': {'ENABLED':False}, 'MAXMIND': {'ENABLED':False}, 'REPLICATION': {'ENABLED':False}, 'MEMPOOL_SERVICES': {'ACCELERATIONS':False}}
            atomic(a.runtime / 'config.json', conf)
            env = dict(os.environ, MEMPOOL_CONFIG_FILE=str(a.runtime / 'config.json'))
            backend_log = (folder / 'backend.log').open('ab'); logs.append(backend_log)
            backend = subprocess.Popen(['/usr/bin/node', '--max-old-space-size=1024', str(a.bundle / 'backend/index.js')], env=env, cwd=a.bundle / 'backend', stdout=backend_log, stderr=backend_log); processes.append(backend)
            atomic(status, {'state':'starting', 'network':network})
            while not STOP and a.profile.read_bytes() == raw:
                if backend.poll() is not None or database.poll() is not None: raise RuntimeError('Explorer process stopped')
                try:
                    with urllib.request.urlopen(f'http://127.0.0.1:{a.api_port}/api/v1/backend-info', timeout=3) as response:
                        info = json.load(response)
                    chain = rpc(profile, 'getblockchaininfo')
                    if chain['chain'] != network: raise ValueError('Core chain changed')
                    indexes = rpc(profile, 'getindexinfo')
                    with urllib.request.urlopen(f'http://127.0.0.1:{a.api_port}/api/v1/blocks/tip/hash', timeout=3) as response:
                        indexed_tip = response.read().decode().strip()
                    electrs_height, electrs_tip = electrs_header(a.electrum_port)
                    indexes_match = indexed_tip == electrs_tip == chain['bestblockhash'] and electrs_height == chain['blocks']
                    state = 'core_sync' if chain['initialblockdownload'] else ('txindex' if not indexes.get('txindex', {}).get('synced') else ('running' if indexes_match else 'electrs_sync'))
                    atomic(status, {'state':state, 'network':network, 'version':info.get('version'), 'core_version':version, 'blocks':chain['blocks'], 'headers':chain['headers'], 'ibd':chain['initialblockdownload']})
                except (OSError, ValueError, KeyError):
                    atomic(status, {'state':'waiting', 'network':network})
                time.sleep(3)
            atomic(status, {'state':'waiting'})
        except Exception as error:
            # Credentials, URLs, Core response bodies and user addresses are never logged.
            atomic(status, {'state':'waiting', 'reason':type(error).__name__})
        finally:
            for process in reversed(processes):
                if process.poll() is None:
                    process.terminate()
                    try: process.wait(timeout=90)
                    except subprocess.TimeoutExpired: process.kill(); process.wait()
            for log in logs: log.close()
        if not STOP: time.sleep(5)

if __name__ == '__main__': main()
