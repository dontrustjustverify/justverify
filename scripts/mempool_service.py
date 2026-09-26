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
import threading
import time
import urllib.request

STOP = False
LOG_BYTES = 2 * 1024 * 1024


class BoundedLog:
    """Drain child output continuously; retain at most three 2 MiB segments."""
    def __init__(self, path, stream):
        self.path, self.stream = path, stream
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def run(self):
        try:
            # A previous release may have left a large log. Keep only its tail.
            if self.path.exists() and self.path.stat().st_size > LOG_BYTES:
                with self.path.open('rb') as source:
                    source.seek(-LOG_BYTES, os.SEEK_END)
                    tail = source.read()
                self.path.write_bytes(tail)
            with self.path.open('ab') as output:
                while chunk := self.stream.read1(16384):
                    if output.tell() + len(chunk) > LOG_BYTES:
                        output.close()
                        oldest = self.path.with_name(self.path.name + '.2')
                        oldest.unlink(missing_ok=True)
                        previous = self.path.with_name(self.path.name + '.1')
                        if previous.exists(): previous.replace(oldest)
                        self.path.replace(previous)
                        output = self.path.open('ab')
                    output.write(chunk)
                    output.flush()
                output.close()
        except OSError:
            # Disk/log errors must not block the child on a full pipe.
            while self.stream.read(16384): pass
        finally:
            self.stream.close()

    def close(self):
        self.thread.join(timeout=5)


def profile_folder(data, profile):
    # Root-generated data_id survives executable-version changes. Legacy
    # profiles retain their original path until the next managed activation.
    identity = profile.get('data_id', profile['version'] + ('-watch-only' if profile.get('watch_only') else ''))
    if not isinstance(identity, str) or not re.fullmatch(r'\d+\.\d+(?:\.\d+)?(?:-watch-only)?', identity):
        raise ValueError('Invalid profile storage identity')
    if identity.endswith('-watch-only') != bool(profile.get('watch_only',False)):
        raise ValueError('Profile storage mode mismatch')
    folder = data / (profile['network'] + '-' + identity)
    folder.mkdir(mode=0o700, exist_ok=True)
    if folder.is_symlink(): raise ValueError('Linked explorer storage refused')
    for name in ('mysql', 'cache', 'backend.log', 'database.log'):
        for suffix in ('', '.1', '.2'):
            if (folder / (name + suffix)).is_symlink(): raise ValueError('Linked explorer data refused')
    return folder


def trim_cache(cache):
    # Only disposable RBF snapshots; never SQL, chain, wallet or other files.
    for name in ('rbfcache.json', 'tmp-rbfcache.json'):
        path = cache / name
        if path.is_symlink(): raise ValueError('Linked explorer cache refused')
        if path.is_file() and path.stat().st_size > 64 * 1024 * 1024: path.unlink()
        for old in cache.glob(name + '.oversized-*'):
            if re.fullmatch(re.escape(name) + r'\.oversized-\d+', old.name) and old.is_file() and not old.is_symlink(): old.unlink()


def validate_block_cache(cache, profile, chain):
    """Do not reopen a saved tip from before a reset or incompatible fork."""
    path = cache / 'cache.json'
    if not path.exists(): return
    if path.is_symlink(): raise ValueError('Linked explorer cache refused')
    invalid = path.stat().st_size > 64 * 1024 * 1024
    tip = None
    if not invalid:
        try:
            saved = json.loads(path.read_bytes())
            blocks = saved['blocks']
            if not isinstance(blocks, list): raise ValueError('Invalid cached blocks')
            tip = max(blocks, key=lambda block: block['height']) if blocks else None
            if tip:
                height, digest = tip['height'], tip['id']
                if type(height) is not int or height < 0 or not isinstance(digest,str) or not re.fullmatch(r'[0-9a-f]{64}',digest): raise ValueError('Invalid cached tip')
                invalid = height > chain['blocks']
        except (ValueError, KeyError, TypeError):
            invalid = True
    if not invalid and tip:
        # RPC failures leave the cache untouched and defer startup.
        invalid = rpc(profile, 'getblockhash', [tip['height']]) != tip['id']
    if invalid:
        names = ['cache.json','tmp-cache.json','rbfcache.json','tmp-rbfcache.json']
        names += [prefix+str(n)+'.json' for prefix in ('cache','tmp-cache') for n in range(1,25)]
        paths = [cache / name for name in names]
        if any(p.is_symlink() for p in paths): raise ValueError('Linked explorer cache refused')
        for p in paths: p.unlink(missing_ok=True)

def stop(*_):
    global STOP
    STOP = True


def rpc(profile, method, params=None):
    cookie = Path(profile['cookie']).read_bytes().strip()
    request = urllib.request.Request('http://127.0.0.1:' + str(profile['rpc_port']),
        json.dumps({'id': 1, 'method': method, 'params': params or []}).encode(),
        {'Authorization': 'Basic ' + base64.b64encode(cookie).decode(), 'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=3) as response:
        result = json.load(response)
    if result.get('error'):
        raise ValueError('Core RPC not ready')
    return result['result']


class ElectrumProbe:
    """One connection and one outstanding pair, including during long compaction."""
    def __init__(self, port):
        self.port=port;self.sock=None;self.pending=None;self.buffer=b''
        self.sequence=0;self.size=0;self.retry_at=0;self.backoff=10

    def close(self):
        if self.sock is not None:self.sock.close()
        self.sock=None;self.pending=None;self.buffer=b''

    def poll(self):
        if self.sock is None and time.monotonic()<self.retry_at:raise OSError('Electrum reconnect pending')
        try:return self.receive()
        except TimeoutError:
            # Keep the request and partial response; do not accumulate new sockets.
            if self.sock is not None and self.pending is not None:raise
            self.failed();raise
        except (OSError,ValueError,KeyError,TypeError):
            self.failed();raise

    def failed(self):
        self.close();self.retry_at=time.monotonic()+self.backoff;self.backoff=min(60,self.backoff*2)

    def receive(self):
        if self.sock is None:self.sock=socket.create_connection(('127.0.0.1',self.port),.5)
        if self.pending is None:
            self.sequence+=2;self.size=0
            request=''.join(json.dumps({'id':self.sequence+i,'method':method,'params':[]})+'\n' for i,method in enumerate(('blockchain.headers.subscribe','server.ping')))
            try:self.sock.settimeout(.5);self.sock.sendall(request.encode())
            except OSError:
                raise OSError('Electrum write failed') from None
            self.pending={}
        deadline=time.monotonic()+3
        while len(self.pending)<2:
            while b'\n' in self.buffer:
                line,self.buffer=self.buffer.split(b'\n',1);self.size+=len(line)+1
                if self.size>16384:raise ValueError('Electrum response exceeds limit')
                value=json.loads(line)
                if not isinstance(value,dict):raise ValueError('Invalid Electrum reply')
                identity=value.get('id')
                if identity in (self.sequence,self.sequence+1):
                    if identity in self.pending:raise ValueError('Duplicate Electrum reply')
                    self.pending[identity]=value
                elif identity is not None or value.get('method')!='blockchain.headers.subscribe':raise ValueError('Invalid Electrum reply id')
                if len(self.pending)==2:break
            if len(self.pending)==2:break
            left=deadline-time.monotonic()
            if left<=0:raise TimeoutError('Electrum response pending')
            self.sock.settimeout(left);chunk=self.sock.recv(4096)
            if not chunk:raise OSError('Electrum disconnected')
            self.buffer+=chunk
            if self.size+len(self.buffer)>16384:raise ValueError('Electrum response exceeds limit')
        response=self.pending[self.sequence]
        if response.get('error'):raise ValueError('Invalid Electrum header')
        header=response['result']
        if not isinstance(header,dict) or not isinstance(header.get('hex'),str):raise ValueError('Invalid Electrum header')
        raw=bytes.fromhex(header['hex'])
        if len(raw)!=80 or type(header['height']) is not int or header['height']<0:raise ValueError('Invalid Electrum header')
        ping=self.pending[self.sequence+1]
        ready='result' in ping and ping['result'] is None and not ping.get('error')
        if not ready and ping.get('error')!={'code':-32603,'message':'unavailable index'}:raise ValueError('Invalid Electrum readiness reply')
        self.pending=None;self.backoff=10
        tip=hashlib.sha256(hashlib.sha256(raw).digest()).digest()[::-1].hex()
        return {'height':header['height'],'tip':tip,'ready':ready}


_probes={}
def electrs_status(port):
    if port not in _probes:
        # Production uses one fixed backend. Bound cached clients for administrative callers.
        if len(_probes)>=4:_probes.pop(next(iter(_probes))).close()
        _probes[port]=ElectrumProbe(port)
    return _probes[port].poll()


def atomic(path, data):
    data = {**data, 'updated':time.time()}
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
    p.add_argument('--electrum-port', type=int, default=50003)
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
            # Start HTTP and its native retrying Electrum client independently
            # of index completion. Address queries may still be unavailable.
            atomic(status, {'state':'starting', 'network':network})
            folder = profile_folder(a.data, profile)
            db = folder / 'mysql'
            db.mkdir(mode=0o700, exist_ok=True)
            cache = folder / 'cache'
            cache.mkdir(mode=0o700, exist_ok=True)
            trim_cache(cache)
            validate_block_cache(cache, profile, chain)
            sql_socket = a.runtime / 'mysql.sock'
            if not (db / 'mysql').is_dir():
                subprocess.run(['/usr/bin/mariadb-install-db', '--no-defaults', '--datadir=' + str(db), '--auth-root-authentication-method=socket', '--auth-root-socket-user=justverify', '--skip-test-db'], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            def start(command, name, **kwargs):
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **kwargs)
                logs.append(BoundedLog(folder / name, process.stdout))
                processes[:] = [p for p in processes if p.poll() is None]
                processes.append(process)
                return process
            database = start(['/usr/sbin/mariadbd', '--no-defaults', '--datadir=' + str(db), '--socket=' + str(sql_socket), '--pid-file=' + str(a.runtime / 'mysql.pid'), '--skip-networking', '--innodb-buffer-pool-size=128M', '--max-connections=20', '--innodb-log-file-size=32M'], 'database.log')
            sql = ['/usr/bin/mariadb', '--no-defaults', '--socket=' + str(sql_socket), '--user=justverify']
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
            command = ['/usr/bin/node', '--max-old-space-size=1024', str(a.bundle / 'backend/index.js')]
            backend = start(command, 'backend.log', env=env, cwd=a.bundle / 'backend')
            backend_since, retry_at, retry_delay = time.monotonic(), 0, 5
            atomic(status, {'state':'starting', 'network':network})
            while not STOP and a.profile.read_bytes() == raw:
                if database.poll() is not None: raise RuntimeError('Database stopped')
                if backend.poll() is not None:
                    if not retry_at:
                        if time.monotonic() - backend_since >= 60: retry_delay = 5
                        retry_at = time.monotonic() + retry_delay
                        retry_delay = min(retry_delay * 2, 60)
                        atomic(status, {'state':'waiting', 'network':network, 'api_available':False, 'reason':'backend_restart'})
                    if time.monotonic() >= retry_at:
                        trim_cache(cache)
                        try: validate_block_cache(cache, profile, rpc(profile,'getblockchaininfo'))
                        except (OSError, ValueError, KeyError):
                            retry_at = time.monotonic() + 5
                            time.sleep(.5)
                            continue
                        logs[:] = [log for log in logs if log.thread.is_alive()]
                        backend = start(command, 'backend.log', env=env, cwd=a.bundle / 'backend')
                        backend_since, retry_at = time.monotonic(), 0
                    time.sleep(.5)
                    continue
                available = False
                observation = {'state':'waiting', 'network':network, 'api_available':False}
                try:
                    with urllib.request.urlopen(f'http://127.0.0.1:{a.api_port}/api/v1/backend-info', timeout=3) as response:
                        info = json.load(response)
                    available = True
                    observation.update(api_available=True, version=info.get('version'), core_version=version)
                    chain = rpc(profile, 'getblockchaininfo')
                    if chain['chain'] != network:
                        available = False
                        raise ValueError('Core chain changed')
                    observation.update(blocks=chain['blocks'], headers=chain['headers'], ibd=chain['initialblockdownload'])
                    indexes = rpc(profile, 'getindexinfo')
                    phase = 'core_sync' if chain['initialblockdownload'] else ('txindex' if not indexes.get('txindex', {}).get('synced') else 'electrs_waiting')
                    observation.update(state=phase, txindex_enabled='txindex' in indexes)
                    electrs = electrs_status(a.electrum_port)
                    observation.update(electrs_height=electrs['height'], electrs_ready=electrs['ready'])
                    matches_core = electrs['tip'] == chain['bestblockhash'] and electrs['height'] == chain['blocks']
                    if phase == 'electrs_waiting':
                        observation['state'] = 'electrs_finalizing' if matches_core and not electrs['ready'] else 'electrs_sync'
                    with urllib.request.urlopen(f'http://127.0.0.1:{a.api_port}/api/v1/blocks/tip/hash', timeout=3) as response:
                        indexed_tip = response.read().decode().strip()
                    if phase == 'electrs_waiting' and matches_core and electrs['ready']:
                        observation['state'] = 'running' if indexed_tip == chain['bestblockhash'] else 'mempool_sync'
                except (OSError, ValueError, KeyError):
                    # Preserve the known phase; one slow dependency must not
                    # revoke the already-listening backend's HTTP/WebSocket.
                    pass
                atomic(status, {**observation, 'api_available':available})
                time.sleep(3)
            atomic(status, {'state':'waiting'})
        except Exception as error:
            # Credentials, URLs, Core response bodies and user addresses are never logged.
            atomic(status, {'state':'waiting', 'reason':type(error).__name__})
        finally:
            for probe in _probes.values():probe.close()
            _probes.clear()
            for process in reversed(processes):
                if process.poll() is None:
                    process.terminate()
                    try: process.wait(timeout=90)
                    except subprocess.TimeoutExpired: process.kill(); process.wait()
            for log in logs: log.close()
        if not STOP: time.sleep(5)

if __name__ == '__main__': main()
