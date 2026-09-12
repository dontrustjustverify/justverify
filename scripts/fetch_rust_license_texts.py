#!/usr/bin/env python3
"""Fetch missing license texts using registry VCS commits; retain missing provenance as a gap."""
import concurrent.futures,hashlib,json,pathlib,urllib.request
root=pathlib.Path(__file__).resolve().parents[1];meta=json.loads((root/'.state/cargo-license-metadata.json').read_text());report_path=root/'licenses/rust-license-inventory.json';report=json.loads(report_path.read_text());packages={(p['name'],p['version']):p for p in meta['packages']}
def fetch(record):
 if record['notices']:return record
 p=packages[(record['name'],record['version'])];vcs=pathlib.Path(p['manifest_path']).parent/'.cargo_vcs_info.json'
 if not vcs.exists():return record
 commit=json.loads(vcs.read_text())['git']['sha1'];repo=p['repository'].removeprefix('https://github.com/').removesuffix('.git')
 if repo.startswith('http'):return record
 for name in ('LICENSE','LICENSE.md','LICENSE-MIT','LICENSE-APACHE','LICENSES/MIT.txt','LICENSES/Apache-2.0.txt') + (('AUTHORS',) if p['name']=='r-efi' else ()):
  url=f'https://raw.githubusercontent.com/{repo}/{commit}/{name}'
  try:
   with urllib.request.urlopen(url,timeout=6) as response:data=response.read(200000)
  except Exception:continue
  if len(data)>100000 or not data:continue
  text=data.decode('utf-8');assert any(w in text.lower() for w in ('license','copyright','permission'))
  file=root/'licenses/rust'/(record['name']+'-'+record['version'])/('upstream-'+name.replace('/','-'));file.write_bytes(data)
  record['notices'].append({'file':str(file.relative_to(root)),'sha256':hashlib.sha256(data).hexdigest(),'url':url,'commit':commit})
 if record['notices']:record['status']='COLLECTED from registry VCS-pinned upstream; legal/source-obligation review pending'
 return record
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:report['packages']=list(pool.map(fetch,report['packages']))
report_path.write_text(json.dumps(report,indent=2)+'\n');print({'missing':[r['name'] for r in report['packages'] if not r['notices']]})
