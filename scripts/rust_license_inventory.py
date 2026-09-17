#!/usr/bin/env python3
"""Collect packaged license notices from locked Cargo metadata without copying implementation."""
import hashlib,json,pathlib,shutil,sys
root=pathlib.Path(__file__).resolve().parents[1]
metadata=json.loads(pathlib.Path(sys.argv[1]).read_text());destination=root/'docs/licenses/rust';destination.mkdir(parents=True,exist_ok=True);records=[]
for package in metadata['packages']:
 if package.get('source') is None:continue
 directory=pathlib.Path(package['manifest_path']).parent;names=set()
 for path in directory.iterdir():
  if path.is_file() and path.name.upper().startswith(('LICENSE','LICENCE','COPYING','NOTICE')):names.add(path)
 if package.get('license_file'):
  path=(directory/package['license_file']).resolve()
  assert path.is_relative_to(directory.resolve())
  if path.is_file():names.add(path)
 key=package['name']+'-'+package['version'];folder=destination/key;folder.mkdir(exist_ok=True);files=[]
 for path in sorted(names):
  target=folder/path.name;shutil.copyfile(path,target)
  files.append({'file':str(target.relative_to(root)),'sha256':hashlib.sha256(target.read_bytes()).hexdigest()})
 records.append({'name':package['name'],'version':package['version'],'license_expression':package['license'],'source':package['source'],'repository':package['repository'],'notices':files,'status':'COLLECTED; legal/source-obligation review pending' if files else 'MISSING packaged license text'})
report={'scope':'All locked Cargo packages across platforms; superset of ARM build. Collection is not license-compliance approval. OS/Python/native bundled licenses tracked separately.','packages':records}
(root/'docs/evidence/rust-license-inventory.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'packages':len(records),'missing':[r['name']+'-'+r['version'] for r in records if not r['notices']]}))
