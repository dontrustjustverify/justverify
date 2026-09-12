#!/usr/bin/env python3
"""Convert a pristine verified JustVerify image into a single-OS GPT image offline."""
import argparse,contextlib,hashlib,json,os,pathlib,subprocess,tempfile,uuid
ROOT=pathlib.Path(__file__).resolve().parents[1]
def run(args,**kwargs):return subprocess.run(args,check=True,capture_output=True,**kwargs)
@contextlib.contextmanager
def loop(path,readonly=False):
 device=run(['/usr/sbin/losetup','--find','--show','--partscan',*(['--read-only'] if readonly else []),str(path)],text=True).stdout.strip()
 try:yield device
 finally:run(['/usr/sbin/losetup','-d',device])
@contextlib.contextmanager
def mount(device,path,readonly=False):
 path.mkdir(parents=True,exist_ok=True);run(['/usr/bin/mount',*(['-o','ro'] if readonly else []),str(device),str(path)])
 try:yield path
 finally:run(['/usr/bin/umount',str(path)])
def build(source,output,expected,binary=None,binary_sha256=None):
 if os.geteuid()!=0:raise ValueError('isolated Linux root builder required')
 if not source.is_file() or source.is_symlink():raise ValueError('regular pristine source required')
 with source.open('rb') as file:
  if hashlib.file_digest(file,'sha256').hexdigest()!=expected:raise ValueError('input image SHA256 mismatch')
 if not output.is_absolute() or output.parent.resolve() not in ((ROOT/'.state').resolve(),(ROOT/'dist').resolve()) or output.suffix!='.img' or output.exists() or output.is_symlink():raise ValueError('new project image only')
 with loop(source,True) as old:
  table=json.loads(run(['/usr/sbin/sfdisk','--json',old],text=True).stdout)['partitiontable']
  if len(table['partitions'])!=2 or table['sectorsize']!=512:raise ValueError('expected two-partition pristine source')
  namespace=uuid.UUID('8f4de4f2-d1a0-45a6-8ff6-81a301f317bc');start=2048;parts=[]
  for role,size,kind in [('boot',table['partitions'][0]['size'],'c12a7328-f81f-11d2-ba4b-00a0c93ec93b'),('root',table['partitions'][1]['size'],'0fc63daf-8483-4772-8e79-3d69d8477de4'),('data',1048576,'0fc63daf-8483-4772-8e79-3d69d8477de4')]:
   parts.append({'role':role,'start':start,'size':size,'type':kind,'partuuid':str(uuid.uuid5(namespace,role))});start=((start+size+2047)//2048)*2048
  layout={'schema':1,'kind':'single-os','disk_uuid':str(uuid.uuid5(namespace,'disk')),'partitions':parts,'factory_data_uuid':str(uuid.uuid5(namespace,'data-fs'))}
  fd=os.open(output,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
  with os.fdopen(fd,'wb') as file:file.truncate((start+2048)*512)
  lines=['label: gpt','label-id: '+layout['disk_uuid'],'unit: sectors']+[f'start={p["start"]}, size={p["size"]}, type={p["type"]}, uuid={p["partuuid"]}, name="JV_{p["role"]}"' for p in parts]
  run(['/usr/sbin/sfdisk',str(output)],input='\n'.join(lines)+'\n',text=True)
  for index in (1,2):run(['/usr/bin/dd',f'if={old}p{index}',f'of={output}','bs=4M','conv=sparse,notrunc','oflag=seek_bytes',f'seek={parts[index-1]["start"]*512}','status=none'])
  with loop(output) as new:
   run(['/usr/sbin/mkfs.ext4','-q','-U',layout['factory_data_uuid'],'-L','JustVerify-data',new+'p3'])
   with tempfile.TemporaryDirectory(prefix='jv-single-') as tmp:
    tmp=pathlib.Path(tmp)
    with mount(new+'p3',tmp/'data') as data:(data/'.jv-factory').write_bytes(b'JustVerify single-OS factory data v1\n')
    with mount(new+'p2',tmp/'root') as root:
     if (root/'etc/machine-id').read_bytes().strip() or (root/'etc/justverify/node-ready.json').exists():raise ValueError('source has a device identity/registration; refuse distribution')
     if binary is not None:
      if not binary.is_file() or binary.is_symlink() or hashlib.sha256(binary.read_bytes()).hexdigest()!=binary_sha256:raise ValueError('application binary hash mismatch')
      run(['/usr/bin/install','-m','0755',str(binary),str(root/'opt/justverify/bin/justverify')])
     (root/'etc/justverify-factory.json').write_text(json.dumps(layout,indent=2)+'\n')
     for name in ('factory_volume.py','storage_service.py'):
      run(['/usr/bin/install','-m','0755',str(ROOT/'scripts'/name),str(root/'opt/justverify/scripts'/name)])
     run(['/usr/bin/install','-m','0755',str(ROOT/'scripts/profile_helper.py'),str(root/'usr/libexec/justverify-profile')])
     run(['/usr/bin/install','-m','0755',str(ROOT/'image/firstboot.sh'),str(root/'opt/justverify/scripts/firstboot.sh')])
     fstab=root/'etc/fstab';rows=[]
     for line in fstab.read_text().splitlines():
      fields=line.split()
      if fields and not line.lstrip().startswith('#') and len(fields)>1:
       if fields[1] in ('/','/boot/firmware'):
        fields[0]='PARTUUID='+parts[1 if fields[1]=='/' else 0]['partuuid'];line='\t'.join(fields)
       elif fields[1]=='/srv/justverify/data':raise ValueError('source has a registered data filesystem')
      rows.append(line)
     fstab.write_text('\n'.join(rows)+'\n')
     with mount(new+'p1',root/'boot/firmware') as boot:
      cmdline=boot/'cmdline.txt';args=cmdline.read_text().split()
      args=[('root=PARTUUID='+parts[1]['partuuid']) if a.startswith('root=') else a for a in args if not a.startswith('init=') and a != 'resize']
      cmdline.write_text(' '.join(args)+'\n')
    run(['/usr/bin/sync'])
   for index in (2,3):run(['/usr/sbin/e2fsck','-f','-n',new+f'p{index}'])
  run(['/usr/sbin/sfdisk','--verify',str(output)])
 return layout
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',type=pathlib.Path,required=True);p.add_argument('--source-sha256',required=True);p.add_argument('--output',type=pathlib.Path,required=True);p.add_argument('--binary',type=pathlib.Path);p.add_argument('--binary-sha256');a=p.parse_args()
 result=build(a.source,a.output,a.source_sha256,a.binary,a.binary_sha256);a.output.with_suffix('.layout.json').write_text(json.dumps(result,indent=2)+'\n');print('Single OS image assembled; actual boot NOT RUN')
