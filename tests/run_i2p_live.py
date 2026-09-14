#!/usr/bin/env python3
"""Own two disposable public-network I2P routers around the real Core test."""
import argparse,pathlib,socket,subprocess,sys
p=argparse.ArgumentParser();p.add_argument('--bundle',type=pathlib.Path,required=True);p.add_argument('--core',type=pathlib.Path,required=True);p.add_argument('--root',type=pathlib.Path,required=True);a=p.parse_args()
a.root=a.root.resolve();a.bundle=a.bundle.resolve();a.core=a.core.resolve()
a.root.mkdir(mode=0o700)  # Fresh output only; never use a production data directory.
subprocess.run(['sha256sum','-c','SHA256SUMS'],cwd=a.bundle,check=True,stdout=subprocess.DEVNULL)
routers=[]
try:
 for name,sam,transport in [('a',7656,17656),('b',8656,18656)]:
  with socket.socket() as check:check.bind(('127.0.0.1',sam))
  folder=a.root/name;folder.mkdir(mode=0o700)
  config=(pathlib.Path(__file__).resolve().parents[1]/'image/i2pd.conf').read_text()
  assert 'port = 7656' in config and 'certsdir = /opt/justverify/i2pd/certificates' in config
  config=config.replace('port = 7656','port = '+str(sam)).replace('certsdir = /opt/justverify/i2pd/certificates','certsdir = '+str(a.bundle/'certificates'))
  config='port='+str(transport)+'\n'+config
  (folder/'i2pd.conf').write_text(config)
  with (folder/'router.log').open('xb') as log:
   routers.append(subprocess.Popen([str(a.bundle/'i2pd'),'--conf='+str(folder/'i2pd.conf'),'--datadir='+str(folder)],stdout=log,stderr=log))
 subprocess.run([sys.executable,str(pathlib.Path(__file__).with_name('i2p_live.py')),'--core',str(a.core),'--root',str(a.root/'core-test')],check=True)
finally:
 for router in routers:
  if router.poll() is None:router.terminate()
 for router in routers:
  try:router.wait(timeout=45)
  except subprocess.TimeoutExpired:router.kill();router.wait()
