#!/usr/bin/env python3
"""Fresh, isolated installed-binary regtest: wallet signing through Electrum.

Never reads the mainnet profile or changes installed service configuration.
The explicitly named new state directory is retained for failure diagnosis.
"""
import argparse
import hashlib
import json
import pathlib
import socket
import subprocess
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--state', type=pathlib.Path, required=True)
    args = parser.parse_args()
    state = args.state.resolve()
    assert state.name.startswith('jv-validation-') and not state.exists()
    state.mkdir(mode=0o700)
    data = state / 'core'
    data.mkdir(mode=0o700)
    binary = pathlib.Path('/opt/justverify/core/bin')
    processes = []
    logs = []
    common = [str(binary / 'bitcoin-cli'), '-regtest', '-datadir=' + str(data),
              '-rpcport=19543']

    def cli(method, params=None, wallet=None):
        command = common + (['-rpcwallet=' + wallet] if wallet else [])
        command += [method] + [json.dumps(p) if not isinstance(p, str) else p
                               for p in (params or [])]
        result = subprocess.run(command, text=True, capture_output=True, timeout=20)
        if result.returncode:
            raise RuntimeError(method + ' failed: ' + result.stderr[:300])
        try:
            return json.loads(result.stdout)
        except ValueError:
            return result.stdout.strip()

    def electrum(method, params=None):
        with socket.create_connection(('127.0.0.1', 19501), 3) as connection:
            connection.settimeout(5)
            connection.sendall((json.dumps({'id': 1, 'method': method,
                                            'params': params or []}) + '\n').encode())
            response = json.loads(connection.makefile('rb').readline(4 * 1024 * 1024))
            assert not response.get('error'), response.get('error')
            return response['result']

    def wait(check, seconds=120):
        deadline = time.monotonic() + seconds
        last = None
        while time.monotonic() < deadline:
            try:
                result = check()
                if result:
                    return result
            except (OSError, RuntimeError, ValueError) as error:
                last = type(error).__name__
            time.sleep(.25)
        raise TimeoutError('isolated integration check: ' + str(last))

    def start(command, name):
        log = (state / name).open('ab')
        logs.append(log)
        process = subprocess.Popen(command, stdout=log, stderr=log)
        processes.append(process)
        return process

    def start_index():
        return start(['/opt/justverify/bin/electrs', '--skip-default-conf-files',
                      '--network=regtest', '--daemon-dir=' + str(data),
                      '--db-dir=' + str(state / 'index'),
                      '--daemon-rpc-addr=127.0.0.1:19543',
                      '--daemon-p2p-addr=127.0.0.1:19544',
                      '--electrum-rpc-addr=127.0.0.1:19501',
                      '--monitoring-addr=127.0.0.1:19524', '--log-filters=INFO'], 'electrs.log')

    def matching_tip(height):
        header = electrum('blockchain.headers.subscribe')
        tip = hashlib.sha256(hashlib.sha256(bytes.fromhex(header['hex'])).digest()).digest()[::-1].hex()
        return header['height'] == height and tip == cli('getbestblockhash')

    result = {'status': 'FAIL', 'network': 'isolated regtest', 'checks': []}
    try:
        core = start([str(binary / 'bitcoind'), '-regtest', '-datadir=' + str(data),
                      '-server=1', '-listen=1', '-bind=127.0.0.1', '-port=19544',
                      '-rpcport=19543', '-connect=0', '-dnsseed=0', '-dbcache=32',
                      '-maxmempool=64'], 'core.log')
        wait(lambda: cli('getblockchaininfo'))
        assert cli('getblockchaininfo')['chain'] == 'regtest'
        result['core_version'] = cli('getnetworkinfo')['subversion']
        for wallet in ('sender', 'receiver'):
            cli('createwallet', [wallet])
        mining_address = cli('getnewaddress', wallet='sender')
        receiver = cli('getnewaddress', wallet='receiver')
        script = cli('getaddressinfo', [receiver], wallet='receiver')['scriptPubKey']
        scripthash = hashlib.sha256(bytes.fromhex(script)).digest()[::-1].hex()
        cli('generatetoaddress', [101, mining_address])
        index = start_index()
        wait(lambda: matching_tip(101))
        result['electrs_version'] = electrum('server.version', ['JustVerifyInstalledImageTest', '1.4'])
        raw = cli('createrawtransaction', [[], {receiver: 1}])
        funded = cli('fundrawtransaction', [raw, {'fee_rate': 1}], wallet='sender')
        signed = cli('signrawtransactionwithwallet', [funded['hex']], wallet='sender')
        assert signed['complete']
        accepted = cli('testmempoolaccept', [[signed['hex']]])
        assert accepted[0]['allowed']
        txid = electrum('blockchain.transaction.broadcast', [signed['hex']])
        assert txid == cli('decoderawtransaction', [signed['hex']])['txid']
        assert txid in cli('getrawmempool')
        wait(lambda: any(t['tx_hash'] == txid and t['height'] <= 0
                         for t in electrum('blockchain.scripthash.get_history', [scripthash])))
        wait(lambda: cli('gettransaction', [txid], wallet='receiver')['confirmations'] == 0)
        result['checks'] += ['real wallet funding/creation/signature complete',
                             'testmempoolaccept allowed', 'Electrum broadcast reached Core mempool',
                             'unconfirmed Electrum history and receiver wallet']
        confirmations = [0]
        for height in (102, 103):
            cli('generatetoaddress', [1, mining_address])
            wait(lambda: matching_tip(height))
            wait(lambda: cli('gettransaction', [txid], wallet='receiver')['confirmations'] == height - 101)
            wait(lambda: any(t['tx_hash'] == txid and t['height'] == 102
                             for t in electrum('blockchain.scripthash.get_history', [scripthash])))
            confirmations.append(height - 101)
        history = electrum('blockchain.scripthash.get_history', [scripthash])
        index.terminate()
        index.wait(timeout=30)
        start_index()
        wait(lambda: matching_tip(103))
        assert electrum('blockchain.scripthash.get_history', [scripthash]) == history
        assert cli('getbalances', wallet='receiver')['mine']['trusted'] == 1
        result.update(status='PASS', txid=txid, confirmations=confirmations,
                      height=103, core_tip=cli('getbestblockhash'), electrs_tip_matches=True,
                      receiver_confirmed_btc='1.00000000')
        result['checks'] += ['confirmations 0 -> 1 -> 2', 'Core/electrs height and tip match',
                             'receiver wallet confirmed balance', 'electrs restart preserves history']
        result['not_run'] = ['public-network transaction', 'physical mobile wallet', 'mainnet full indexing']
    except Exception as error:
        result['error'] = type(error).__name__ + ': ' + str(error)
        raise
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        for log in logs:
            log.close()
        (state / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result))


if __name__ == '__main__':
    main()
