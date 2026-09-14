#!/usr/bin/env python3
"""Extract policy evidence from executed help and source, flag review gaps explicitly."""
import pathlib,re,json,hashlib,urllib.request,urllib.error
from annotate_policy_evidence import annotate
R=pathlib.Path(__file__).resolve().parents[1]
extra=set('maxmempool mempoolexpiry persistmempool persistmempoolv1 limitancestorcount limitancestorsize limitdescendantcount limitdescendantsize limitclustercount limitclustersize maxorphantx mempoolfullrbf acceptnonstdtxn blocksonly'.split())
boolean=set('persistmempool persistmempoolv1 mempoolfullrbf acceptnonstdtxn blocksonly datacarrier permitbaremultisig whitelistrelay whitelistforcerelay privatebroadcast'.split())
fee=set('minrelaytxfee incrementalrelayfee dustrelayfee blockmintxfee'.split())
release_networks={r['version']:r['networks'] for r in json.loads((R/'catalog/releases.json').read_text())['releases']}
for directory in sorted((R/'docs/evidence/core-matrix').iterdir()):
    if not (directory/'help-debug.txt').exists():continue
    version=directory.name;help=(directory/'help-debug.txt').read_text();basic=(directory/'help.txt').read_text()
    source=R/'.cache/core'/version/'init.cpp'
    if not source.exists():
        with urllib.request.urlopen(f'https://raw.githubusercontent.com/bitcoin/bitcoin/v{version}/src/init.cpp',timeout=30) as response:source.write_bytes(response.read())
    init=source.read_text();rows=[];section='';current=None
    for line in help.splitlines()+['  -END']:
        if line and not line.startswith(' '):
            section=line
            continue
        match=re.match(r'  -([a-z0-9]+)(.*)',line)
        if match:
            if current:
                key,category,description=current
                description=' '.join(description)
                if key in extra or category in ['Node relay options:','Block creation options:']:
                    default=re.search(r'default: ([^),]+)',description)
                    ignored=any(t in description.lower() for t in ['has no effect','no longer has any effect','removed option','only used by wallet','ignored'])
                    rows.append({'core_version':version,'key':key,'source':f'https://github.com/bitcoin/bitcoin/blob/v{version}/src/init.cpp','help_sha256':hashlib.sha256(help.encode()).hexdigest(),'source_sha256':hashlib.sha256(init.encode()).hexdigest(),'source_registration_present':f'"-{key}' in init,'type':'boolean' if key in boolean else 'decimal' if key in fee else 'integer','unit':'BTC/kvB (input sat/vB)' if key in fee else 'MB (1000000 bytes)' if key=='maxmempool' else 'hours' if key=='mempoolexpiry' else 'see upstream description','default':default.group(1) if default else None,'range':None,'network_scope':release_networks[version],'introduced_removed_changed':'see adjacent-version diff','restart_required':True,'dependencies':[],'conflicts':[],'verification_method':'executed -help/-help-debug and source registration; semantic ranges/behavior NOT RUN','advanced':f'  -{key}' not in basic,'ignored_or_wallet_only':ignored,'description':description,'editable':False,'review':'SEMANTIC_REVIEW_REQUIRED'})
            current=[match.group(1),section,[]]
        elif current and line.strip():current[2].append(line.strip())
    (R/'catalog'/f'policy-{version}.json').write_text(json.dumps(annotate(rows,version),indent=2)+'\n')
    print(version,len(rows),'policy entries',flush=True)
versions=sorted((p for p in (R/'catalog').glob('policy-*.json') if re.fullmatch(r'policy-[0-9]+(?:\.[0-9]+)+',p.stem)),key=lambda p:tuple(map(int,p.stem[7:].split('.'))))
diffs=[]
for before,after in zip(versions,versions[1:]):
    a={r['key']:r for r in json.loads(before.read_text())};b={r['key']:r for r in json.loads(after.read_text())}
    diffs.append({'from':before.stem[7:],'to':after.stem[7:],'added':sorted(b.keys()-a.keys()),'removed':sorted(a.keys()-b.keys()),'changed':[k for k in sorted(a.keys()&b.keys()) if any(a[k][f]!=b[k][f] for f in ['default','description','advanced','ignored_or_wallet_only'])]})
(R/'catalog/policy-diff.json').write_text(json.dumps(diffs,indent=2)+'\n')
