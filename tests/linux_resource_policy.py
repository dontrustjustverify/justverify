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
def rpc(method,params=None):
    c=http.client.HTTPConnection('127.0.0.1',profile['rpc_port'],timeout=5)
    c.request('POST','/',json.dumps({'id':1,'method':method,'params':[] if params is None else params}),{'Authorization':'Basic '+base64.b64encode(pathlib.Path(profile['cookie']).read_bytes().strip()).decode()})
    value=json.loads(c.getresponse().read());c.close();assert not value.get('error');return value['result']
def apply(values):
    review=api({'method':'preview','values':values})
    assert api({'method':'apply','token':review['token']})['phase']=='committed'
original=api({'method':'state'})['requested']
values={'bantime':'120','maxconnections':'16','maxreceivebuffer':'4096','maxsendbuffer':'2048','peertimeout':'45','timeout':'1500','maxuploadtarget':'10','dbcache':'32','rpcworkqueue':'17'}
try:
    review=api({'method':'preview','values':{**original,**values}})
    assert len(review['preflight']['resources'])==11
    assert api({'method':'apply','token':review['token']})['phase']=='committed'
    assert api({'method':'state'})['requested']=={**original,**values}
    assert rpc('getnettotals')['uploadtarget']['target']==10*1048576
    # RFC5737 TEST-NET address only, in a verified isolated regtest profile.
    rpc('setban',['192.0.2.123','add'])
    banned=next(b for b in rpc('listbanned') if b['address']=='192.0.2.123/32')
    assert 115<=banned['banned_until']-time.time()<=121
    rpc('setban',['192.0.2.123','remove'])
    end=time.monotonic()+30
    while True:
        try:
            with socket.create_connection(('127.0.0.1',50001),2) as s:
                s.sendall(b'{"id":1,"method":"blockchain.headers.subscribe","params":[]}\n')
                header=json.loads(s.makefile('rb').readline())['result']
                import hashlib
                assert hashlib.sha256(hashlib.sha256(bytes.fromhex(header['hex'])).digest()).digest()[::-1].hex()==rpc('getblockchaininfo')['bestblockhash']
            break
        except (OSError,ValueError,AssertionError):
            if time.monotonic()>end:raise
            time.sleep(.25)
    print('PASS nine actual resource settings: Core configuration logs, effective maxconnections/uploadtarget, ban duration, electrs tip and persisted API state',flush=True)
finally:
    if any(b['address']=='192.0.2.123/32' for b in rpc('listbanned')):rpc('setban',['192.0.2.123','remove'])
    apply(original)
    assert api({'method':'state'})['requested']==original
    print('PASS original resource policy restored',flush=True)
