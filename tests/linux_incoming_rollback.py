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
    baseline={**original,'listen':'none'}
    apply(baseline)
    with socket.socket() as occupied:
        occupied.bind(('127.0.0.1',18445));occupied.listen(1)
        review=api({'method':'preview','values':{**baseline,'listen':'tor'}})
        result=api({'method':'apply','token':review['token']})
        assert result['phase']=='rolled_back', result
        assert api({'method':'state'})['requested']==baseline
        assert rpc('getblockchaininfo')['chain']=='regtest'
        print('PASS occupied onion backend: failed/incomplete Core startup refused; configuration rolled back and Core recovered',flush=True)
finally:
    apply(original)
    assert api({'method':'state'})['requested']==original
    print('PASS original policy restored after actual incoming failure injection',flush=True)
