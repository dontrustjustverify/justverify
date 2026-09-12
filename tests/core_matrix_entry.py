#!/usr/bin/env python3
"""Run one verified Core release in isolated Linux regtest and capture both helps."""
import sys,pathlib,subprocess,json,time,hashlib
version=sys.argv[1];root=pathlib.Path.home()/'core-matrix'/version;binary=root/f'bitcoin-{version}'/'bin';data=root/'data';data.mkdir(exist_ok=True)
result={'version':version,'platform':'aarch64-linux-gnu','time':time.time(),'checks':[],'status':'FAIL'}
for option,name in [('-help','help.txt'),('-help-debug','help-debug.txt')]:
    p=subprocess.run([str(binary/'bitcoind'),option],capture_output=True,text=True,timeout=15);assert p.returncode==0;pout=root/name;pout.write_text(p.stdout)
process=subprocess.Popen([str(binary/'bitcoind'),f'-datadir={data}','-regtest','-server','-listen=0','-connect=0','-dnsseed=0','-disablewallet','-rpcport=19743','-printtoconsole=0'],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
try:
    for _ in range(100):
        p=subprocess.run([str(binary/'bitcoin-cli'),f'-datadir={data}','-regtest','-rpcport=19743','getblockchaininfo'],capture_output=True,text=True)
        if p.returncode==0:break
        if process.poll() is not None:raise RuntimeError(process.stderr.read().decode())
        time.sleep(.1)
    assert p.returncode==0
    info=json.loads(p.stdout);assert info['chain']=='regtest'
    for method in ['getnetworkinfo','getmempoolinfo','getpeerinfo','getnettotals','getindexinfo']:
        call=subprocess.run([str(binary/'bitcoin-cli'),f'-datadir={data}','-regtest','-rpcport=19743',method],capture_output=True,text=True)
        result['checks'].append({'method':method,'returncode':call.returncode})
        assert call.returncode==0
    result.update(status='PASS',chain=info['chain'],height=info['blocks'],binary_sha256=hashlib.file_digest((binary/'bitcoind').open('rb'),'sha256').hexdigest())
finally:
    if process.poll() is None:process.terminate();process.wait(timeout=30)
(root/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
