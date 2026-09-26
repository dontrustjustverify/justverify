#!/usr/bin/env python3
"""Signed broadcasts and inclusion proofs on a disposable, peerless regtest.

Uses real Core/electrs binaries and the production TCP/TLS relay. Never accepts
an existing data directory or remote endpoint. Ports 50001–50003 must be free.
"""
import argparse
import asyncio
import contextlib
from decimal import Decimal
import hashlib
import json
import pathlib
import socket
import ssl
import subprocess
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'web'))
from electrum_tls import ElectrumTLS, listeners


def sha256d(value):
    return hashlib.sha256(hashlib.sha256(value).digest()).digest()


def spare_port():
    with socket.socket() as connection:
        connection.bind(('127.0.0.1', 0))
        return connection.getsockname()[1]


class Client:
    def __init__(self, reader, writer):
        self.reader, self.writer = reader, writer
        self.identifier = 0

    async def call(self, method, params=None, *, error=False):
        self.identifier += 1
        self.writer.write(json.dumps({'id': self.identifier, 'method': method,
                                      'params': params or []}).encode() + b'\n')
        await self.writer.drain()
        deadline = time.monotonic() + 10
        while True:
            remaining = deadline - time.monotonic()
            assert remaining > 0, 'Electrum response deadline: ' + method
            line = await asyncio.wait_for(self.reader.readline(), remaining)
            assert line, 'Unexpected Electrum EOF: ' + method
            response = json.loads(line)
            if response.get('id') != self.identifier:
                continue
            if error:
                assert response.get('error'), 'Invalid transaction was accepted'
                return response['error']
            assert not response.get('error'), 'Electrum RPC failed: ' + method
            return response['result']

    async def close(self):
        self.writer.close()
        await self.writer.wait_closed()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--core', required=True, type=pathlib.Path)
    parser.add_argument('--electrs', required=True, type=pathlib.Path)
    args = parser.parse_args()
    assert not sys.flags.optimize, 'Run with assertions enabled'
    for number in (50001, 50002, 50003):
        with socket.socket() as connection:
            connection.bind(('127.0.0.1', number))
    rpc, p2p, metrics = [spare_port() for _ in range(3)]
    processes = []
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix='jv-broadcast-', dir='/var/tmp') as temporary:
        root = pathlib.Path(temporary)
        data = root / 'core'
        data.mkdir()

        def start(command):
            process = subprocess.Popen(list(map(str, command)), stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL)
            processes.append(process)
            return process

        def cli(method, *values, wallet=None):
            command = [str(args.core / 'bitcoin-cli'), '-regtest', '-datadir=' + str(data),
                       '-rpcport=' + str(rpc)]
            if wallet:
                command.append('-rpcwallet=' + wallet)
            result = subprocess.run(command + [method, *map(str, values)], capture_output=True,
                                    text=True, timeout=20)
            if result.returncode:
                raise RuntimeError('Isolated Core RPC failed: ' + method)
            try:
                return json.loads(result.stdout, parse_float=Decimal)
            except ValueError:
                return result.stdout.strip()

        def sender(method, *values):
            return cli(method, *values, wallet='sender')

        async def connect(host, number, **options):
            return Client(*await asyncio.wait_for(asyncio.open_connection(host, number, **options), 5))

        async def wait_tip(client, height, block_hash):
            deadline = time.monotonic() + 30
            while True:
                header = await client.call('blockchain.headers.subscribe')
                if header['height'] == height and sha256d(bytes.fromhex(header['hex']))[::-1].hex() == block_hash:
                    return
                assert time.monotonic() < deadline, 'Electrs did not index the new block'
                await asyncio.sleep(.25)

        async def run():
            deadline = time.monotonic() + 90
            while True:
                client = None
                try:
                    client = await connect('127.0.0.1', 50003)
                    await wait_tip(client, 101, cli('getbestblockhash'))
                    features = await client.call('server.features')
                    assert features['hosts'] == {'tcp_port': 50003}
                    break
                except (OSError, asyncio.TimeoutError):
                    assert time.monotonic() < deadline, 'Electrs startup deadline'
                    await asyncio.sleep(.25)
                finally:
                    if client:
                        await client.close()

            subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                            '-subj', '/CN=justverify.local', '-days', '1',
                            '-keyout', str(root / 'private-key.pem'),
                            '-out', str(root / 'certificate.pem')], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            trusted = ssl.create_default_context(cafile=str(root / 'certificate.pem'))
            bridge = ElectrumTLS()
            servers = await listeners(root, bridge, hosts=('127.0.0.1', '::1'))
            receipts = []
            try:
                for tls in (False, True):
                    for host in ('127.0.0.1', '::1'):
                        endpoint = 50002 if tls else 50001
                        options = {'ssl': trusted, 'server_hostname': 'justverify.local'} if tls else {}
                        client = await connect(host, endpoint, **options)
                        try:
                            assert (await client.call('server.features'))['hosts'] == {'tcp_port': 50001}
                            assert await client.call('server.ping') is None
                            address = cli('getnewaddress', wallet='receiver')
                            script = cli('getaddressinfo', address, wallet='receiver')['scriptPubKey']
                            scripthash = hashlib.sha256(bytes.fromhex(script)).digest()[::-1].hex()
                            raw = sender('createrawtransaction', '[]', json.dumps({address: '0.10000000'}))
                            funded = sender('fundrawtransaction', raw, '{"fee_rate":2}')
                            signed = sender('signrawtransactionwithwallet', funded['hex'])
                            assert signed['complete']
                            decoded = cli('decoderawtransaction', signed['hex'])
                            txid = decoded['txid']
                            # Changing nLockTime preserves serialization but invalidates SIGHASH_ALL.
                            changed_locktime = 1 if decoded['locktime'] != 1 else 2
                            altered = signed['hex'][:-8] + changed_locktime.to_bytes(4, 'little').hex()
                            altered_id = cli('decoderawtransaction', altered)['txid']
                            rejection = cli('testmempoolaccept', json.dumps([altered]))[0]
                            assert rejection['allowed'] is False
                            assert 'script' in rejection['reject-reason'].lower(), 'Expected signature verification failure'
                            await client.call('blockchain.transaction.broadcast', [altered], error=True)
                            assert cli('getrawmempool') == []
                            assert await client.call('blockchain.transaction.broadcast', [signed['hex']]) == txid
                            assert cli('getrawmempool') == [txid]
                            assert await client.call('blockchain.transaction.get', [txid]) == signed['hex']
                            # An uncertain response must not require creating a different payment.
                            assert await client.call('blockchain.transaction.broadcast', [signed['hex']]) == txid
                            assert cli('getrawmempool') == [txid]
                            await client.close()
                            client = await connect(host, endpoint, **options)
                            assert await client.call('blockchain.transaction.get', [txid]) == signed['hex']
                            assert await client.call('blockchain.transaction.broadcast', [signed['hex']]) == txid
                            assert cli('getrawmempool') == [txid]

                            block_hash = sender('generatetoaddress', 1, sender('getnewaddress'))[0]
                            block = cli('getblock', block_hash)
                            height = block['height']
                            assert txid in block['tx'] and altered_id not in block['tx']
                            assert cli('getrawmempool') == []
                            await wait_tip(client, height, block_hash)
                            assert await client.call('blockchain.transaction.get', [txid]) == signed['hex']
                            proof = await client.call('blockchain.transaction.get_merkle', [txid, height])
                            assert proof['block_height'] == height
                            assert block['tx'][proof['pos']] == txid
                            value, position = bytes.fromhex(txid)[::-1], proof['pos']
                            for sibling in proof['merkle']:
                                other = bytes.fromhex(sibling)[::-1]
                                value = sha256d(other + value if position & 1 else value + other)
                                position >>= 1
                            assert position == 0 and value[::-1].hex() == block['merkleroot']
                            history = await client.call('blockchain.scripthash.get_history', [scripthash])
                            assert history == [{'tx_hash': txid, 'height': height}]
                            outputs = await client.call('blockchain.scripthash.listunspent', [scripthash])
                            assert len(outputs) == 1
                            output = outputs[0]
                            assert output['tx_hash'] == txid and output['height'] == height
                            assert output['value'] == 10_000_000
                            original = decoded['vout'][output['tx_pos']]
                            assert original['scriptPubKey']['hex'] == script
                            assert int(original['value'] * 100_000_000) == output['value']
                            assert cli('getreceivedbyaddress', address, wallet='receiver') == Decimal('0.1')
                            receipts.append({
                                'transport': 'TLS' if tls else 'TCP',
                                'address_family': 'IPv6' if ':' in host else 'IPv4',
                                'external_port': endpoint, 'txid': txid, 'block_hash': block_hash,
                                'block_height': height, 'received_satoshis': output['value'],
                                'fee_satoshis': int(funded['fee'] * 100_000_000),
                                'broadcast_attempts_same_transaction': 3,
                                'single_mempool_entry': True, 'exact_raw_transaction': True,
                                'reconnect_lookup': True, 'altered_signature_rejected': True,
                                'block_inclusion': True, 'merkle_proof_verified': True,
                                'history_and_unspent_match': True,
                            })
                            print(json.dumps({'progress': 'confirmed', 'case': len(receipts),
                                              'transport': receipts[-1]['transport'],
                                              'address_family': receipts[-1]['address_family']}), file=sys.stderr, flush=True)
                        finally:
                            await client.close()
                peers = cli('getpeerinfo')
                assert len(peers) == 1 and peers[0]['inbound'] is True
                assert peers[0]['addr'].startswith('127.0.0.1:'), 'Unexpected external peer'
                return {'status': 'PASS', 'network': 'regtest',
                        'core_version': cli('getnetworkinfo')['version'],
                        'electrs_version': features['server_version'], 'receipts': receipts,
                        'only_core_peer': 'local electrs', 'fresh_disposable_wallets': True,
                        'mainnet_transactions': False, 'pi_accessed': False,
                        'physical_wallet_app_tested': False}
            finally:
                for server in servers:
                    server.close()
                await asyncio.gather(*(server.wait_closed() for server in servers))
                for writer in list(bridge.connections):
                    writer.close()
                await asyncio.sleep(.1)

        try:
            start([args.core / 'bitcoind', '-regtest', '-server', '-datadir=' + str(data),
                   '-rpcport=' + str(rpc), '-port=' + str(p2p), '-bind=127.0.0.1',
                   '-connect=0', '-dnsseed=0', '-discover=0'])
            deadline = time.monotonic() + 30
            while True:
                try:
                    assert cli('getblockchaininfo')['chain'] == 'regtest'
                    break
                except RuntimeError:
                    assert time.monotonic() < deadline, 'Core startup deadline'
                    time.sleep(.2)
            cli('createwallet', 'sender')
            cli('createwallet', 'receiver')
            sender('generatetoaddress', 101, sender('getnewaddress'))
            start([args.electrs, '--skip-default-conf-files', '--network=regtest',
                   '--daemon-dir=' + str(data), '--db-dir=' + str(root / 'index'),
                   '--daemon-rpc-addr=127.0.0.1:' + str(rpc),
                   '--daemon-p2p-addr=127.0.0.1:' + str(p2p),
                   '--electrum-rpc-addr=127.0.0.1:50003',
                   '--monitoring-addr=127.0.0.1:' + str(metrics)])
            result = asyncio.run(run())
        finally:
            for process in reversed(processes):
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
    assert not root.exists()
    result.update({'temporary_data_removed': True, 'owned_processes_stopped': True,
                   'elapsed_seconds': round(time.monotonic() - started, 1)})
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
