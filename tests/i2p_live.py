#!/usr/bin/env python3
"""Two real Core nodes through two independent SAM routers on the public I2P network.

Only fresh regtest data is used. Router bootstrap is external, with a fixed ten
minute deadline. No mocked SAM server or direct-IP fallback is accepted.
"""
import argparse, base64, hashlib, json, pathlib, socket, subprocess, time, urllib.request, urllib.error

def wait(check, seconds, label):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        try:
            result=check()
            if result:return result
        except (OSError,ValueError,KeyError):pass
        time.sleep(1)
    raise AssertionError(label+' exceeded '+str(seconds)+'s')

class Core:
    def __init__(self,binary,folder,port,sam,incoming):
        self.binary,self.folder,self.port,self.sam=binary,folder,port,sam
        folder.mkdir(mode=0o700)
        self.incoming=incoming
        self.process=None
    def start(self):
        self.config=f'''regtest=1
server=1
listen=1
listenonion=0
dnsseed=0
onlynet=i2p
i2psam=127.0.0.1:{self.sam}
i2pacceptincoming={int(self.incoming)}
discover=0
fallbackfee=0.00001
[regtest]
rpcbind=127.0.0.1
rpcallowip=127.0.0.1
rpcport={self.port}
bind=127.0.0.1:{self.port+1}
'''
        (self.folder/'bitcoin.conf').write_text(self.config)
        with (self.folder/'process.log').open('ab') as log:
            self.process=subprocess.Popen([str(self.binary),'-datadir='+str(self.folder),'-printtoconsole=0'],stdout=log,stderr=log)
        wait(lambda:self.rpc('getblockchaininfo'),30,'Core startup')
    def rpc(self,method,params=None,wallet=False):
        cookie=(self.folder/'regtest/.cookie').read_bytes().strip()
        request=urllib.request.Request('http://127.0.0.1:'+str(self.port)+('/wallet/i2p-test' if wallet else '/'),json.dumps({'id':1,'method':method,'params':params or []}).encode(),{'Authorization':'Basic '+base64.b64encode(cookie).decode(),'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(request,timeout=8) as response:r=json.load(response)
        except urllib.error.HTTPError as error:
            r=json.load(error)
        if r.get('error'):raise ValueError(str(r['error']))
        return r['result']
    def address(self):
        return next((r['address'] for r in self.rpc('getnetworkinfo')['localaddresses'] if r['address'].endswith('.b32.i2p')),None)
    def peers(self):return self.rpc('getpeerinfo')
    def stop(self):
        if self.process and self.process.poll() is None:
            try:self.rpc('stop')
            finally:
                try:self.process.wait(timeout=30)
                except subprocess.TimeoutExpired:self.process.kill();self.process.wait();raise

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--core',required=True,type=pathlib.Path);parser.add_argument('--root',required=True,type=pathlib.Path);parser.add_argument('--sam-a',type=int,default=7656);parser.add_argument('--sam-b',type=int,default=8656);args=parser.parse_args()
    args.root.mkdir(mode=0o700);report={'status':'RUNNING','scope':'real public I2P transport, fresh isolated regtest','core_binary_sha256':hashlib.sha256(args.core.read_bytes()).hexdigest(),'checks':[]}
    def note(s):report['checks'].append(s);(args.root/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(s,flush=True)
    a=Core(args.core,args.root/'a',29400,args.sam_a,True);b=Core(args.core,args.root/'b',29500,args.sam_b,True)
    nodes=[a,b]
    try:
        a.start();b.start();report['core']=a.rpc('getnetworkinfo')['subversion']
        address_a=wait(a.address,600,'I2P destination A');address_b=wait(b.address,600,'I2P destination B')
        note('both real SAM routers created persistent Core I2P destinations')
        a.rpc('addnode',[address_b+':0','add'])
        def connected():
            ap,bp=a.peers(),b.peers()
            assert all(p['network']=='i2p' for p in ap+bp),'direct-IP fallback detected'
            return any(not p['inbound'] and p['version']>0 for p in ap) and any(p['inbound'] and p['version']>0 for p in bp)
        wait(connected,600,'bidirectional I2P Bitcoin handshake')
        note('outgoing A / incoming B getpeerinfo network=i2p, completed Bitcoin version handshake; no IP peers')
        for node in [a,b]:node.rpc('createwallet',['i2p-test'])
        mining=a.rpc('getnewaddress',wallet=True);a.rpc('generatetoaddress',[101,mining])
        wait(lambda:b.rpc('getbestblockhash')==a.rpc('getbestblockhash'),180,'regtest blocks across I2P')
        destination=b.rpc('getnewaddress',wallet=True);tx=a.rpc('sendtoaddress',[destination,1],True)
        wait(lambda:tx in b.rpc('getrawmempool'),120,'signed transaction over I2P')
        note('101 blocks and a signed transaction propagated solely over I2P; recipient mempool saw tx')
        a.rpc('generatetoaddress',[2,mining]);wait(lambda:b.rpc('gettransaction',[tx],True)['confirmations']==2,180,'wallet confirmations across I2P')
        report['txid']=tx;report['confirmations']=2;report['height']=a.rpc('getblockcount');report['tip']=a.rpc('getbestblockhash')
        note('Core tips and recipient wallet agree at 103 blocks / two confirmations')
        key=a.folder/'regtest/i2p_private_key';before=hashlib.sha256(key.read_bytes()).hexdigest()
        a.stop();a.start();assert wait(a.address,120,'restart identity')==address_a;assert hashlib.sha256(key.read_bytes()).hexdigest()==before
        a.rpc('addnode',[address_b+':0','add']);wait(connected,300,'I2P reconnect after Core restart')
        note('Core restart preserves I2P identity, settings, chain and reconnects through I2P')
        # Switch to outgoing-only. The persistent key must stay on disk, but no
        # persistent incoming address may be advertised or used by the new peer.
        # Use a new recipient/destination for the independent outgoing-only
        # phase. An I2P router can retain streams destined for the old identity
        # after its Core client exits; these do not identify a new connection.
        a.stop();b.stop()
        b=Core(args.core,args.root/'outgoing-recipient',29500,args.sam_b,True)
        nodes.append(b);b.start()
        address_b=wait(b.address,600,'new outgoing-only recipient')
        assert b.peers()==[]
        a.incoming=False;a.start();assert a.address() is None
        a.rpc('addnode',[address_b+':0','add']);wait(connected,300,'outgoing-only I2P connection')
        assert all(not p['inbound'] for p in a.peers())
        major=int(report['core'].split(':')[1].split('.')[0])
        # Transient outgoing identities were introduced in upstream Core24.
        if major>=24:
            assert all(not p['addr'].startswith(address_a) for p in b.peers())
        else:
            assert any(p['addr'].startswith(address_a) and p['version']>0 for p in b.peers())
        assert hashlib.sha256(key.read_bytes()).hexdigest()==before
        a.rpc('generatetodescriptor',[1,'raw(51)'])
        wait(lambda:b.rpc('getbestblockhash')==a.rpc('getbestblockhash'),180,'outgoing-only block propagation')
        assert a.rpc('getblockcount')==b.rpc('getblockcount')==104
        report['outgoing_identity']='transient' if major>=24 else 'persistent (Core22/23 upstream behavior)'
        note('incoming off keeps outbound I2P working; selected-version identity behavior and saved key verified')
        report['final_height']=104;report['final_tip']=a.rpc('getbestblockhash')
        report['status']='PASS'
    except Exception as e:
        report['status']='FAIL';report['error']=type(e).__name__+': '+str(e);raise
    finally:
        for node in nodes:node.stop()
        (args.root/'result.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
