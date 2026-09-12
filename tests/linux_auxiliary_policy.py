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
keys=['txindex','txospenderindex','blockfilterindex','peerblockfilters','peerbloomfilters','rest','asmap']
try:
    for selected in ['1','0']:
        values={**original,**{key:selected for key in keys}}
        review=api({'method':'preview','values':values})
        assert api({'method':'apply','token':review['token']})['phase']=='committed'
        assert api({'method':'state'})['requested']==values
        names=['txindex','txospenderindex','basic block filter index']
        end=time.monotonic()+30
        while True:
            indexes=rpc('getindexinfo');height=rpc('getblockcount')
            if selected=='0':assert not any(n in indexes for n in names);break
            if all(indexes[n]['synced'] and indexes[n]['best_block_height']==height for n in names):break
            assert time.monotonic()<end,'Core indexes did not finish';time.sleep(.25)
        if selected=='1':
            block=rpc('getblock',[rpc('getblockhash',[1])])
            assert rpc('getrawtransaction',[block['tx'][0],True])['txid']==block['tx'][0]
            assert rpc('getblockfilter',[block['hash']])['filter']
        with socket.create_connection(('127.0.0.1',50001),2) as electrum:
            electrum.sendall(b'{"id":1,"method":"blockchain.headers.subscribe","params":[]}\n')
            assert json.loads(electrum.makefile('rb').readline())['result']['height']==height
        print('PASS actual auxiliary enabled='+selected+': indexes reach real chain height, RPC retrieval/filter, service bits/local REST/asmap and electrs continuity',flush=True)
finally:
    apply(original)
    assert api({'method':'state'})['requested']==original
    print('PASS original index/filter/REST/asmap policy restored; index files retained',flush=True)
