#!/usr/bin/env python3
"""Run as justverify against the real restricted administration service."""
import socket,json,time,os,pwd,subprocess,urllib.request,base64,pathlib
assert pwd.getpwuid(os.geteuid()).pw_name=='justverify'
def api(request):
    with socket.socket(socket.AF_UNIX) as s:
        s.settimeout(50);s.connect('/run/justverify-policy/control.sock');s.sendall((json.dumps(request)+'\n').encode());out=b''
        while block:=s.recv(65536):out+=block
    return json.loads(out)
def rpc(method):
    secret=pathlib.Path('/srv/justverify/data/core/regtest/.cookie').read_text().strip()
    r=urllib.request.Request('http://127.0.0.1:18443',data=json.dumps({'jsonrpc':'1.0','id':'test','method':method,'params':[]}).encode(),headers={'Authorization':'Basic '+base64.b64encode(secret.encode()).decode(),'Content-Type':'application/json'})
    return json.load(urllib.request.urlopen(r,timeout=3))['result']
deadline=time.monotonic()+10
while True:
    try:original=api({'method':'state'});break
    except (FileNotFoundError,ConnectionRefusedError):
        if time.monotonic()>deadline:raise
        time.sleep(.1)
assert original['ok'];values=original['result']['requested']
assert not api({'method':'preview','values':{'rpcbind':'0.0.0.0'}})['ok']
assert not api({'method':'preview','values':{'minrelaytxfee':'1\nrpcallowip=0.0.0.0/0'}})['ok']
assert not api({'method':'state','command':'/bin/sh'})['ok']
new={**values,'maxmempool':'421','minrelaytxfee':'0.501','datacarriersize':'42'}
preview=api({'method':'preview','values':new});assert preview['ok'],preview
assert preview['result']['preflight']['observed']['maxmempool']==421000000
result=api({'method':'apply','token':preview['result']['token']});assert result['ok'] and result['result']['phase']=='committed',result
assert rpc('getmempoolinfo')['maxmempool']==421000000
assert rpc('getmempoolinfo')['minrelaytxfee']==0.00000501
assert not api({'method':'apply','token':preview['result']['token']})['ok']
assert subprocess.run(['sudo','-n','/usr/bin/id'],capture_output=True).returncode!=0
assert subprocess.run(['sudo','-n','/usr/libexec/justverify-restart-core','extra-argument'],capture_output=True).returncode!=0
restore=api({'method':'preview','values':values});assert restore['ok'],restore
restored=api({'method':'apply','token':restore['result']['token']});assert restored['ok'] and restored['result']['phase']=='committed',restored
print(json.dumps({'status':'PASS','platform':'Debian ARM64 VM','uid_role':'unprivileged justverify','checks':['unsupported key rejected','config injection rejected','unknown API field rejected','real isolated preflight','actual systemd Core restart through fixed helper','observable policy values applied','one-use preview token','arbitrary sudo command denied','helper arguments denied','original configuration restored'],'time':time.time()},indent=2))
