#!/usr/bin/env python3
import hashlib,json,os,pathlib,socket,subprocess,time
assert os.geteuid()==0 and socket.gethostname()=='justverify-dev'
def system(action,unit): subprocess.run(['systemctl',action,unit],check=True)
def cli(*args):
    output=subprocess.check_output(['/opt/justverify/core/bin/bitcoin-cli','-datadir=/srv/justverify/data/core','-conf=/etc/justverify/bitcoin.conf',*args],text=True)
    try:return json.loads(output)
    except ValueError:return output.strip()
def headers(onion=False):
    with socket.create_connection(('127.0.0.1',9050 if onion else 50001),3) as sock:
        sock.settimeout(15);f=sock.makefile('rb')
        if onion:
            host=pathlib.Path('/run/justverify-tor/electrum.hostname').read_text().strip().encode()
            sock.sendall(bytes([5,1,0]));assert f.read(2)==bytes([5,0])
            sock.sendall(bytes([5,1,0,3,len(host)])+host+(50001).to_bytes(2,'big'))
            response=f.read(4)
            if len(response)!=4 or response[1]!=0:raise OSError('onion circuit not ready')
            if response[3]==1:f.read(4)
            elif response[3]==4:f.read(16)
            elif response[3]==3:f.read(f.read(1)[0])
            else:raise AssertionError('invalid SOCKS address')
            f.read(2)
        sock.sendall(b'{"jsonrpc":"2.0","id":1,"method":"blockchain.headers.subscribe","params":[]}\n')
        return json.loads(f.readline(4096))['result']['height']
def wait(predicate,seconds=45):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        try:
            if predicate():return
        except (OSError,ValueError,KeyError):pass
        time.sleep(.3)
    raise AssertionError('network service did not reach expected state')
assert cli('getblockchaininfo')['chain']=='regtest'
desc=cli('getdescriptorinfo','raw(0020'+hashlib.sha256(bytes.fromhex('51')).hexdigest()+')')['descriptor']
cli('generatetodescriptor','2',desc);height=cli('getblockcount')
wait(lambda:headers()==height)
system('restart','justverify-electrs');wait(lambda:headers()==height)
identity={name:(pathlib.Path('/var/lib/justverify-tor')/name/'hostname').read_text() for name in ('p2p','electrum','rpc')}
assert len(set(identity.values()))==3
system('restart','justverify-tor')
for name,hostname in identity.items():
    assert (pathlib.Path('/run/justverify-tor')/(name+'.hostname')).read_text()==hostname
    assert (pathlib.Path('/var/lib/justverify-tor')/name/'hs_ed25519_secret_key').stat().st_mode & 0o077 == 0
print(json.dumps({'status':'PASS','checks':['Core-generated regtest blocks indexed by systemd electrs','electrs restart retains height','separate P2P/Electrum onion identities','Tor restart preserves identities','private Tor keys and public hostname export']},indent=2),flush=True)
# Independent result: keep successful lifecycle evidence even if the public Tor network is unavailable.
wait(lambda:headers(True)==height,seconds=180)
print(json.dumps({'onion_electrum':'PASS','transport':'actual Tor SOCKS circuit to systemd electrs','height':height}),flush=True)
