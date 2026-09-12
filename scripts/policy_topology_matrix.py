#!/usr/bin/env python3
"""Run signed topology and replacement behavior against every checksum-verified ARM Core release."""
import hashlib,json,pathlib,subprocess,sys
root=pathlib.Path(__file__).resolve().parents[1];out=root/'docs/evidence/policy-topology';out.mkdir(parents=True,exist_ok=True)
private=root/'.state/policy-topology';private.mkdir(parents=True,exist_ok=True);private.chmod(0o700)
source=hashlib.sha256((root/'tests/policy_topology.py').read_bytes()).hexdigest();results=[]
for release in json.loads((root/'catalog/releases.json').read_bytes())['releases']:
 version=release['version'];binary=pathlib.Path('/home/builder/core-matrix')/version/f'bitcoin-{version}/bin/bitcoind';report=out/(version+'.json')
 if release['verification']!='PASS':
  results.append({'version':version,'status':'BLOCKED','reason':'official verified binary unavailable'})
 else:
  if hashlib.sha256(binary.read_bytes()).hexdigest()!=release['arm64_binary_sha256']:raise ValueError('official binary differs: '+version)
  previous=json.loads(report.read_bytes()) if report.exists() else {}
  if previous.get('status')=='PASS' and previous.get('test_sha256')==source and previous.get('binary_sha256')==release['arm64_binary_sha256']:code=0
  else:
   with (private/(version+'.log')).open('wb') as log:
    run=subprocess.run([sys.executable,str(root/'tests/policy_topology.py'),'--version',version,'--report',str(report)],stdout=log,stderr=subprocess.STDOUT);code=run.returncode
  results.append({'version':version,'status':'PASS' if code==0 else 'FAIL','report':str(report.relative_to(root)),'log':str((private/(version+'.log')).relative_to(root)),'test_sha256':source})
 (root/'docs/evidence/policy-topology-matrix.json').write_text(json.dumps(results,indent=2)+'\n')
 print(version,results[-1]['status'],flush=True)
if any(row['status']!='PASS' for row in results):raise SystemExit(1)
print('PASS all '+str(len(results))+' selected releases; scope is the explicit behavioral cases, not every policy option',flush=True)
