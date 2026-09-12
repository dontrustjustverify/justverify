#!/usr/bin/env python3
"""Actual registered policy API -> preflight -> systemd restart -> RPC/electrs."""
import base64, http.client, json, pathlib, socket, time

assert socket.gethostname()=='justverify-dev'
profile=json.loads(pathlib.Path('/etc/justverify/profile.json').read_text())
assert profile['network']=='regtest' and '/instances/regtest/' in profile['cookie']
def api(request):
    with socket.socket(socket.AF_UNIX) as s:
        s.settimeout(90);s.connect('/run/justverify-policy/control.sock');s.sendall((json.dumps(request)+'\n').encode());out=b''
        while part:=s.recv(65536):out+=part
    value=json.loads(out);assert value['ok'],value;return value['result']
def rpc(method):
    c=http.client.HTTPConnection('127.0.0.1',profile['rpc_port'],timeout=5)
    c.request('POST','/',json.dumps({'id':1,'method':method,'params':[]}),{'Authorization':'Basic '+base64.b64encode(pathlib.Path(profile['cookie']).read_bytes().strip()).decode()})
    value=json.loads(c.getresponse().read());c.close();assert not value.get('error');return value['result']
def apply(values):
    review=api({'method':'preview','values':values})
    assert api({'method':'apply','token':review['token']})['phase']=='committed'
original=api({'method':'state'})['requested']
def reachable(host,port):
    try:
        with socket.create_connection((host,port),1):return True
    except OSError:return False
lan=__import__('subprocess').check_output(['hostname','-I'],text=True).split()[0]
assert not lan.startswith('127.')
try:
    for selected in ['none','clearnet','tor','clearnet,tor']:
        apply({**original,'listen':selected})
        assert api({'method':'state'})['requested']['listen']==selected
        assert reachable('127.0.0.1',18444), 'ordinary loopback P2P must remain listening'
        assert reachable(lan,18444)==('clearnet' in selected.split(',')), 'external clearnet binding differs'
        assert reachable('127.0.0.1',18445)==('tor' in selected.split(',')), 'onion backend binding differs'
        assert not reachable(lan,18443), 'RPC escaped loopback'
        assert profile['p2p_backend_port']==18446
        assert reachable('127.0.0.1',18446) and not reachable(lan,18446)
        assert 'daemon_p2p_addr = "127.0.0.1:18446"' in pathlib.Path('/etc/justverify/electrs.toml').read_text()
        end=time.monotonic()+30
        while True:
            try:
                with socket.create_connection(('127.0.0.1',50001),2) as s:
                    s.sendall(b'{"id":1,"method":"blockchain.headers.subscribe","params":[]}\n')
                    header=json.loads(s.makefile('rb').readline())['result']
                    chain=rpc('getblockchaininfo')
                    assert header['height']==chain['blocks']
                    import hashlib
                    assert hashlib.sha256(hashlib.sha256(bytes.fromhex(header['hex'])).digest()).digest()[::-1].hex()==chain['bestblockhash']
                break
            except (OSError,ValueError,AssertionError):
                if time.monotonic()>end:raise
                time.sleep(.25)
        peer=next(p for p in rpc('getpeerinfo') if p.get('addrbind','').endswith(':18446') and p['version']>0)
        assert set(peer['permissions'])=={'download','noban'}
        print('PASS actual incoming save/restart/LAN+onion listeners/RPC isolation/electrs tip: '+selected,flush=True)
finally:
    apply(original)
    assert api({'method':'state'})['requested']==original
    print('PASS original incoming policy restored',flush=True)
