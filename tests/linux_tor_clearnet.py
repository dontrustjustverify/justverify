#!/usr/bin/env python3
"""Actual Core testnet4 IPv4 peer handshake through product Tor SOCKS."""
import ipaddress,json,pathlib,socket,subprocess,sys,tempfile,time
assert socket.gethostname()=='justverify-dev'
peers=json.loads(pathlib.Path(sys.argv[1]).read_text())
assert 1<=len(peers)<=3
for peer in peers:
    host,port=peer.rsplit(':',1);ipaddress.IPv4Address(host);assert 1<=int(port)<=65535
state=pathlib.Path(tempfile.mkdtemp(prefix='jv-clearnet-tor-'));binary=pathlib.Path('/home/builder/core-matrix/31.1/bitcoin-31.1/bin')
with socket.socket() as s:s.bind(('127.0.0.1',0));rpcport=s.getsockname()[1]
def rpc(method,*args):
    value=subprocess.check_output([str(binary/'bitcoin-cli'),f'-datadir={state}','-testnet4',f'-rpcport={rpcport}',method,*args],stderr=subprocess.DEVNULL,text=True)
    try:return json.loads(value)
    except ValueError:return value.strip()
p=subprocess.Popen([str(binary/'bitcoind'),f'-datadir={state}','-testnet4','-server=1','-listen=0','-listenonion=0','-connect=0','-dnsseed=0','-disablewallet=1','-proxy=127.0.0.1:9050','-onlynet=ipv4','-onion=0',f'-rpcport={rpcport}','-dbcache=4'],stdout=open(state/'core.log','ab'),stderr=subprocess.STDOUT)
try:
    end=time.monotonic()+20
    while True:
        try:info=rpc('getnetworkinfo');break
        except subprocess.CalledProcessError:
            if time.monotonic()>end:raise
            time.sleep(.2)
    assert next(n for n in info['networks'] if n['name']=='ipv4')['proxy']=='127.0.0.1:9050'
    for peer in peers:rpc('addnode',peer,'add')
    end=time.monotonic()+180
    while time.monotonic()<end:
        if any(n['network']=='ipv4' and not n['inbound'] and n['version']>0 for n in rpc('getpeerinfo')):
            inodes=set()
            for fd in pathlib.Path(f'/proc/{p.pid}/fd').iterdir():
                try:target=fd.readlink().as_posix()
                except OSError:continue
                if target.startswith('socket:['):inodes.add(target[8:-1])
            sockets=[line.split() for line in pathlib.Path(f'/proc/{p.pid}/net/tcp').read_text().splitlines()[1:]]
            own=[row for row in sockets if row[9] in inodes and row[3]=='01']
            assert any(row[2]=='0100007F:235A' for row in own),'no actual Core TCP connection to Tor SOCKS9050'
            assert all(row[2].startswith('0100007F:') for row in own),'unexpected nonloopback direct TCP connection'
            print(json.dumps({'status':'PASS','core':'31.1','network':'testnet4','checks':['actual IPv4 Bitcoin P2P version handshake','effective proxy127.0.0.1:9050','Core-owned established TCP socket to Tor9050','no established nonloopback Core TCP connection'],'private_state':str(state)}));break
        time.sleep(2)
    else:raise AssertionError('Tor exit to public testnet4 peers handshake timeout')
finally:
    p.terminate();p.wait(timeout=30)
