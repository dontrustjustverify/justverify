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
try:
    for selected,proxy in [('ipv4,ipv6','0'),('onion','0'),('ipv4,ipv6,onion','1')]:
        apply({**original,'onlynet':selected,'proxy':proxy})
        state=api({'method':'state'});assert state['requested']['onlynet']==selected and state['requested']['proxy']==proxy
        networks={n['name']:n for n in rpc('getnetworkinfo')['networks']}
        for name in ['ipv4','ipv6','onion']:assert networks[name]['limited']==(name not in selected.split(','))
        assert networks['onion']['proxy']==('127.0.0.1:9050' if 'onion' in selected.split(',') else '')
        assert networks['ipv4']['proxy']==('127.0.0.1:9050' if proxy=='1' else '')
        end=time.monotonic()+30
        while True:
            try:
                with socket.create_connection(('127.0.0.1',50001),2) as s:
                    s.sendall(b'{"id":1,"method":"blockchain.headers.subscribe","params":[]}\n')
                    assert json.loads(s.makefile('rb').readline())['result']['height']==rpc('getblockchaininfo')['blocks']
                break
            except (OSError,ValueError,AssertionError):
                if time.monotonic()>end:raise
                time.sleep(.25)
        print('PASS actual policy save/systemd restart/RPC/electrs: '+selected+' clearnet_tor='+proxy,flush=True)
finally:
    apply(original)
    assert api({'method':'state'})['requested']==original
    print('PASS original registered outgoing policy restored',flush=True)
