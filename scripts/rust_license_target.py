#!/usr/bin/env python3
"""Select runtime/build notices from target-filtered Cargo metadata."""
import json,pathlib,sys
root=pathlib.Path(__file__).resolve().parents[1]
m=json.loads(pathlib.Path(sys.argv[1]).read_text());nodes={n['id']:n for n in m['resolve']['nodes']};todo=[m['resolve']['root']];seen=set()
while todo:
 key=todo.pop()
 if key in seen:continue
 seen.add(key)
 for dep in nodes[key]['deps']:
  if any(k['kind']!='dev' for k in dep['dep_kinds']):todo.append(dep['pkg'])
packages={(p['name'],p['version']) for p in m['packages'] if p['id'] in seen and p['source'] is not None}
report=json.loads((root/'docs/evidence/rust-license-inventory.json').read_text());rows=[p for p in report['packages'] if (p['name'],p['version']) in packages]
assert len(rows)==len(packages)
v={'target':sys.argv[2],'scope':'Cargo resolved default-feature runtime/build dependency closure; excludes dev-only and other-platform dependencies. Native embedded code/OS/Python obligations are separate.','count':len(rows),'status':'TEXTS_COLLECTED' if all(p['notices'] for p in rows) else 'MISSING_TEXTS','packages':[{'name':p['name'],'version':p['version'],'license_expression':p['license_expression'],'notices':p['notices']} for p in rows],'missing':[p['name'] for p in rows if not p['notices']]}
pathlib.Path(sys.argv[3]).write_text(json.dumps(v,indent=2)+'\n');print({k:v[k] for k in ('count','status','missing')})
