#!/usr/bin/env python3
import json,pathlib,subprocess,shlex
R=pathlib.Path(__file__).resolve().parents[1];versions=[r['version'] for r in json.loads((R/'docs/evidence/core-matrix-summary.json').read_text()) if r['status']=='PASS'];results=[]
for v in versions:
    remote=f'python3 ~/justverify/scripts/electrs_smoke.py --version {shlex.quote(v)} --core-bin /home/builder/core-matrix/{v}/bitcoin-{v}/bin --electrs-bin /home/builder/electrs/target/release/electrs --state /home/builder/electrs-matrix/{v} --report /home/builder/electrs-matrix/{v}/result.json'
    p=subprocess.run([str(R/'scripts/vm_ssh.sh'),remote],capture_output=True,text=True,timeout=180)
    if p.returncode==0:
        data=subprocess.check_output([str(R/'scripts/vm_ssh.sh'),f'cat ~/electrs-matrix/{v}/result.json'],text=True);result=json.loads(data)
    else:result={'core':v,'status':'FAIL','error':p.stderr[-1500:]}
    results.append(result);(R/'docs/evidence/electrs-matrix-summary.json').write_text(json.dumps(results,indent=2)+'\n');print(v,result['status'],flush=True)
