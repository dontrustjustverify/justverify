#!/usr/bin/env python3
"""Execute only checksum-verified Core builds against actual electrs historical P2P."""
import hashlib,json,pathlib,subprocess,sys
root=pathlib.Path(__file__).resolve().parents[1]
reports=root/'docs/evidence/historical-index-matrix';reports.mkdir(parents=True,exist_ok=True)
results=[]
for release in json.loads((root/'catalog/releases.json').read_text())['releases']:
 if release['verification']!='PASS':continue
 v=release['version'];binary=pathlib.Path('/home/builder/core-matrix')/v/f'bitcoin-{v}/bin/bitcoind'
 assert hashlib.sha256(binary.read_bytes()).hexdigest()==release['arm64_binary_sha256']
 out=reports/(v+'.json')
 run=subprocess.run([sys.executable,str(root/'tests/historical_index_audit.py'),'--core-bin',str(binary.parent),'--electrs-bin','/home/builder/electrs/target/release/electrs','--report',str(out)])
 results.append({'version':v,'status':'PASS' if run.returncode==0 else 'FAIL','evidence':str(out.relative_to(root))})
 (root/'docs/evidence/historical-index-matrix.json').write_text(json.dumps(results,indent=2)+'\n')
 assert run.returncode==0,v
print('PASS all '+str(len(results))+' verified Core releases',flush=True)
