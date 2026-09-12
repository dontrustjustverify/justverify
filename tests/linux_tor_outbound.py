#!/usr/bin/env python3
"""Real isolated Core outbound over product Tor to existing regtest P2P onion."""
import base64, http.client, json, os, pathlib, subprocess, tempfile, time

assert subprocess.check_output(['hostname'],text=True).strip()=='justverify-dev'
root=pathlib.Path(tempfile.mkdtemp(prefix='jv-tor-outbound-'))
binary=pathlib.Path('/home/builder/core-matrix/31.1/bitcoin-31.1/bin')
hostname=pathlib.Path('/run/justverify-tor/p2p.hostname').read_text().strip()
assert hostname.endswith('.onion') and len(hostname)==62
config=root/'bitcoin.conf'
config.write_text('regtest=1\nserver=1\nlisten=0\nlistenonion=0\nonion=127.0.0.1:9050\n[regtest]\nrpcport=29543\nrpcbind=127.0.0.1\nrpcallowip=127.0.0.1\nconnect=0\ndnsseed=0\n')
def rpc(method,*args):
    out=subprocess.check_output([str(binary/'bitcoin-cli'),f'-datadir={root}',method,*args],stderr=subprocess.DEVNULL,text=True)
    try:return json.loads(out)
    except ValueError:return out.strip()
proc=subprocess.Popen([str(binary/'bitcoind'),f'-datadir={root}'],stdout=open(root/'console.log','ab'),stderr=subprocess.STDOUT)
try:
    deadline=time.monotonic()+20
    while True:
        try:info=rpc('getnetworkinfo');break
        except subprocess.CalledProcessError:
            if time.monotonic()>deadline:raise
            time.sleep(.2)
    networks={n['name']:n for n in info['networks']}
    assert networks['onion']['proxy']=='127.0.0.1:9050'
    assert networks['ipv4']['proxy']=='' and networks['ipv6']['proxy']==''
    rpc('addnode',hostname+':8333','add')
    deadline=time.monotonic()+180
    while time.monotonic()<deadline:
        peers=rpc('getpeerinfo')
        if any(p['network']=='onion' and not p['inbound'] and p['version']>0 for p in peers):break
        time.sleep(2)
    else:raise AssertionError('actual outbound onion P2P handshake timeout')
    if os.environ.get('JV_EXPECT_TAGGED_ONION')=='1':
        profile=json.loads(pathlib.Path('/etc/justverify/profile.json').read_text());assert profile['network']=='regtest'
        c=http.client.HTTPConnection('127.0.0.1',profile['rpc_port'],timeout=5)
        c.request('POST','/',json.dumps({'id':1,'method':'getpeerinfo','params':[]}),{'Authorization':'Basic '+base64.b64encode(pathlib.Path(profile['cookie']).read_bytes().strip()).decode()})
        value=json.loads(c.getresponse().read());c.close();assert not value.get('error')
        assert any(peer['inbound'] and peer['network']=='onion' and peer['version']>0 for peer in value['result'])
        assert all(not {'download','noban'} & set(peer.get('permissions',[])) for peer in value['result'] if peer['inbound'] and peer['network']=='onion')
        print('PASS product Core classifies real Tor incoming peer as onion, not IPv4',flush=True)
    print(json.dumps({'status':'PASS','core':'31.1','network':'regtest','checks':['onion SOCKS effective RPC','clearnet remains direct','actual Tor SOCKS onion outbound Bitcoin P2P version handshake'],'private_state':str(root)}))
finally:
    proc.terminate();proc.wait(timeout=30)
