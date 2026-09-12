#!/usr/bin/env python3
"""Bind the target's downloaded wheels to exact requirements and PyPI SHA256."""
import argparse,email.parser,hashlib,json,pathlib,re,urllib.request,zipfile

def normalized(name):return re.sub(r'[-_.]+','-',name).lower()
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--wheelhouse',type=pathlib.Path,required=True);parser.add_argument('--requirements',type=pathlib.Path,required=True);parser.add_argument('--lock',type=pathlib.Path,required=True);parser.add_argument('--manifest',type=pathlib.Path,required=True);args=parser.parse_args()
 expected={}
 for line in args.requirements.read_text().splitlines():
  if not line.strip() or line.startswith('#'):continue
  match=re.fullmatch(r'([A-Za-z0-9_.-]+)==([A-Za-z0-9.]+)',line)
  if not match:raise ValueError('only exact requirements are supported')
  name,version=match.groups();expected[normalized(name)]=version
 records={}
 for wheel in sorted(args.wheelhouse.glob('*.whl')):
  with zipfile.ZipFile(wheel) as archive:
   names=[name for name in archive.namelist() if name.endswith('.dist-info/METADATA')]
   if len(names)!=1:raise ValueError('invalid wheel metadata')
   metadata=email.parser.BytesParser().parsebytes(archive.read(names[0]))
  name=normalized(metadata['Name']);version=metadata['Version']
  if expected.get(name)!=version or name in records:raise ValueError('wheel does not match exact requirements')
  with urllib.request.urlopen(f'https://pypi.org/pypi/{name}/{version}/json',timeout=30) as response:release=json.load(response)
  item=next(item for item in release['urls'] if item['filename']==wheel.name)
  digest=hashlib.sha256(wheel.read_bytes()).hexdigest()
  if digest!=item['digests']['sha256'] or not item['url'].startswith('https://files.pythonhosted.org/'):raise ValueError('PyPI wheel identity mismatch')
  records[name]={'name':name,'version':version,'filename':wheel.name,'sha256':digest,'url':item['url'],'bytes':wheel.stat().st_size}
 if set(records)!=set(expected):raise ValueError('missing locked distribution')
 args.lock.write_text('# Linux aarch64 / CPython 3.13; exact wheels verified against PyPI.\n'+'\n'.join(f'{name}=={records[name]["version"]} --hash=sha256:{records[name]["sha256"]}' for name in sorted(records))+'\n')
 args.manifest.write_text(json.dumps({'schema':1,'target':'Linux aarch64 CPython 3.13','packages':[records[name] for name in sorted(records)]},indent=2)+'\n')
 print(f'PASS {len(records)} exact wheel hashes match PyPI; target installation still requires validation')
if __name__=='__main__':main()
