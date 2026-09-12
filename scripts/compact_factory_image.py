#!/usr/bin/env python3
"""Compact a disposable, unbooted single-OS factory image; never physical media."""
import argparse,hashlib,json,os,pathlib,subprocess,tempfile,sys
from build_single_disk import loop,mount,run
p=argparse.ArgumentParser();p.add_argument('image',type=pathlib.Path);p.add_argument('--sha256',required=True);a=p.parse_args()
assert os.geteuid()==0 and a.image.is_file() and not a.image.is_symlink() and a.image.suffix=='.img' and a.image.parent.name in ('.state','dist')
assert hashlib.file_digest(a.image.open('rb'),'sha256').hexdigest()==a.sha256
root_sectors=5*1024**3//512
with loop(a.image) as dev:
 with tempfile.TemporaryDirectory() as tmp:
  with mount(dev+'p2',pathlib.Path(tmp)/'root') as root:
   assert not (root/'etc/machine-id').read_bytes().strip() and not (root/'etc/justverify/node-ready.json').exists()
   layout=json.loads((root/'etc/justverify-factory.json').read_text())
   assert [x['role'] for x in layout['partitions']]==['boot','root','data']
   for relative in ('var/lib/apt/lists','var/cache/apt','root/.cache/pip'):
    target=root/relative
    if target.exists():
     import shutil
     for item in target.iterdir():
      if item.is_dir() and not item.is_symlink():shutil.rmtree(item)
      else:item.unlink()
   (root/'var/lib/apt/lists/partial').mkdir(exist_ok=True)
   (root/'var/cache/apt/archives/partial').mkdir(parents=True,exist_ok=True)
   usage=subprocess.check_output(['/usr/bin/du','-x','-B1','--max-depth=3',str(root)],text=True)
   rows=[{'bytes':int(line.split('\t',1)[0]),'path':'/'+line.split('\t',1)[1].removeprefix(str(root)).lstrip('/')} for line in usage.splitlines()]
   report={'scope':'unbooted factory filesystem allocated bytes after cache removal','largest_directories':sorted(rows,key=lambda r:r['bytes'],reverse=True)[:50],
           'excluded':'Bitcoin Qt and upstream libexec test executable; apt/pip download caches; filesystem free blocks zeroed before xz',
           'retained':'Pi boot firmware/modules, runtime CLI utilities, Tor, Core, electrs, Python runtime, OS license notices'}
   a.image.with_suffix('.size-audit.json').write_text(json.dumps(report,indent=2)+'\n')
   layout['partitions'][1]['size']=root_sectors
   layout['partitions'][2]['start']=layout['partitions'][1]['start']+root_sectors
   (root/'etc/justverify-factory.json').write_text(json.dumps(layout,indent=2)+'\n')
  with mount(dev+'p3',pathlib.Path(tmp)/'data') as data:
   assert (data/'.jv-factory').read_bytes()==b'JustVerify single-OS factory data v1\n'
   assert set(x.name for x in data.iterdir())=={'lost+found','.jv-factory'}
  run(['/usr/sbin/e2fsck','-f','-p',dev+'p2'])
  run(['/usr/sbin/resize2fs',dev+'p2','5G'])
# Rewrite only the disposable image GPT, then recreate its empty factory data volume.
parts=layout['partitions'];lines=['label: gpt','label-id: '+layout['disk_uuid'],'unit: sectors']+[f'start={x["start"]}, size={x["size"]}, type={x["type"]}, uuid={x["partuuid"]}, name="JV_{x["role"]}"' for x in parts]
size=(parts[-1]['start']+parts[-1]['size']+2048)*512
with a.image.open('r+b') as f:f.truncate(size)
run(['/usr/sbin/sfdisk',str(a.image)],input='\n'.join(lines)+'\n',text=True)
with loop(a.image) as dev:
 run(['/usr/sbin/mkfs.ext4','-q','-U',layout['factory_data_uuid'],'-L','JustVerify-data',dev+'p3'])
 with tempfile.TemporaryDirectory() as tmp:
  with mount(dev+'p3',pathlib.Path(tmp)/'data') as data:(data/'.jv-factory').write_bytes(b'JustVerify single-OS factory data v1\n')
 for i in (2,3):
  run(['/usr/sbin/e2fsck','-f','-n',dev+f'p{i}'])
  # Deleted package/cache bytes still occupy free ext4 blocks. Zero only the
  # unmounted disposable factory image, so compression actually removes them.
  run(['/usr/sbin/zerofree',dev+f'p{i}'])
run(['/usr/sbin/sfdisk','--verify',str(a.image)])
a.image.with_suffix('.layout.json').write_text(json.dumps(layout,indent=2)+'\n')
print(json.dumps({'result':'PASS_OFFLINE','size':size,'root_bytes':root_sectors*512,'boot':'NOT RUN'}))
