#!/usr/bin/env python3
"""Download+verify, transfer, actually execute all inventoried ARM Linux releases."""
import json,pathlib,subprocess,shlex,traceback,time
from fetch_core import fetch
R=pathlib.Path(__file__).resolve().parents[1];records=json.loads((R/'catalog/releases.json').read_text())['releases']
results=[]
for release in records:
    v=release['version'];start=time.time()
    try:
        fetch(v,'aarch64-linux-gnu')
        archive=R/'.cache/core'/v/f'bitcoin-{v}-aarch64-linux-gnu.tar.gz'
        target=f'core-matrix/{v}'
        subprocess.run([str(R/'scripts/vm_ssh.sh'),f'mkdir -p {target}'],check=True,capture_output=True)
        scp=['scp','-i',str(R/'.state/vm/id_ed25519'),'-P','22222','-o','IdentitiesOnly=yes','-o',f'UserKnownHostsFile={R}/.state/vm/known_hosts']
        subprocess.run(scp+[str(archive),f'builder@127.0.0.1:{target}/core.tar.gz'],check=True,capture_output=True)
        # Archive previously checked locally, and protected by SSH in transit.
        command=f'cd {target} && tar xzf core.tar.gz && python3 ~/justverify/tests/core_matrix_entry.py {shlex.quote(v)}'
        proc=subprocess.run([str(R/'scripts/vm_ssh.sh'),command],capture_output=True,text=True,timeout=90)
        if proc.returncode:raise RuntimeError(proc.stderr[-2000:])
        result=json.loads(proc.stdout.strip().splitlines()[-1])
        evidence=R/'docs/evidence/core-matrix'/v;evidence.mkdir(parents=True,exist_ok=True)
        for name in ['result.json','help.txt','help-debug.txt']:
            subprocess.run(scp+[f'builder@127.0.0.1:{target}/{name}',str(evidence/name)],check=True,capture_output=True)
    except Exception as e:result={'version':v,'status':'FAIL','error':str(e)}
    result['elapsed_seconds']=round(time.time()-start,2);results.append(result)
    (R/'docs/evidence/core-matrix-summary.json').write_text(json.dumps(results,indent=2)+'\n')
    print(v,result['status'],flush=True)
