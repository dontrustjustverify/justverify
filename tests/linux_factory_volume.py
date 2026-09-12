#!/usr/bin/env python3
"""Actual single-OS loop filesystem expansion, crash recovery and preservation."""
import hashlib,json,os,pathlib,signal,socket,subprocess,sys,tempfile,uuid
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import factory_volume as f
assert os.geteuid()==0 and socket.gethostname()=='justverify-dev'
work=pathlib.Path(tempfile.mkdtemp(prefix='jv-single-factory-',dir='/var/tmp'));image=work/'disk.img'
with image.open('xb') as file:file.truncate(2*1024**3)
parts=[];start=2048
for role,size in [('boot',65536),('root',262144),('data',1048576)]:
 parts.append({'role':role,'start':start,'size':size,'type':'0fc63daf-8483-4772-8e79-3d69d8477de4','partuuid':str(uuid.uuid4())});start+=size
layout={'schema':1,'kind':'single-os','disk_uuid':str(uuid.uuid4()),'factory_data_uuid':str(uuid.uuid4()),'partitions':parts}
text='label: gpt\nlabel-id: '+layout['disk_uuid']+'\n'+''.join(f'start={p["start"]},size={p["size"]},type={p["type"]},uuid={p["partuuid"]}\n' for p in parts)
f.run(['/usr/sbin/sfdisk',str(image)],input=text,text=True)
loop=f.run(['/usr/sbin/losetup','--find','--show','--partscan',str(image)],text=True).stdout.strip()
data=work/'data';root=work/'root';state=work/'state';data.mkdir();root.mkdir()
try:
 found=f.devices(pathlib.Path(loop),layout)
 for role in ('root','data'):f.run(['/usr/sbin/mkfs.ext4','-q','-U',layout['factory_data_uuid'] if role=='data' else str(uuid.uuid4()),str(found[role])])
 f.run(['/usr/bin/mount',str(found['root']),str(root)]);(root/'sentinel').write_bytes(b'protected OS files\n')
 f.mount_data(found['data'],data);(data/'.jv-factory').write_bytes(f.MARKER);(data/'unexpected').write_bytes(b'preserve me')
 f.run(['/usr/bin/umount',str(data)])
 try:f.provision(pathlib.Path(loop),layout,state,data)
 except ValueError:pass
 else:raise AssertionError('unexpected existing data accepted')
 assert not (state/'provision.json').exists()
 f.mount_data(found['data'],data);assert (data/'unexpected').read_bytes()==b'preserve me';(data/'unexpected').unlink();f.run(['/usr/bin/umount',str(data)])
 original=f.save;pid=os.fork()
 if pid==0:
  def crash(path,value):
   if value['phase']=='committed':os.kill(os.getpid(),signal.SIGKILL)
   original(path,value)
  f.save=crash;f.provision(pathlib.Path(loop),layout,state,data);os._exit(99)
 _,status=os.waitpid(pid,0);assert os.WIFSIGNALED(status) and os.WTERMSIG(status)==signal.SIGKILL
 saved=f.read_root(state/'provision.json',True);assert saved['phase']=='prepared'
 # A real reboot releases this mount; reproduce that prerequisite explicitly.
 f.run(['/usr/bin/umount',str(data)])
 result=f.provision(pathlib.Path(loop),layout,state,data);assert result['uuid']==saved['uuid'] and result['uuid']!=layout['factory_data_uuid']
 assert f.provision(pathlib.Path(loop),layout,state,data)==result
 assert (root/'sentinel').read_bytes()==b'protected OS files\n'
 (data/'instances/sentinel').write_bytes(b'node data preserved\n');f.run(['/usr/bin/umount',str(data)])
 assert f.provision(pathlib.Path(loop),layout,state,data)==result and (data/'instances/sentinel').read_bytes()==b'node data preserved\n'
 capacity=os.statvfs(data).f_blocks*os.statvfs(data).f_frsize;assert capacity>1024**3
 report={'status':'PASS','scope':'actual three-partition GPT/ext4, SIGKILL before commit, unmount/remount; OS boot and physical Pi NOT RUN','unique_data_uuid':True,'crash_reuses_uuid':True,'existing_files_refused_and_preserved':True,'os_and_node_sentinels_preserved':True,'data_filesystem_bytes':capacity,'source_sha256':hashlib.sha256((ROOT/'scripts/factory_volume.py').read_bytes()).hexdigest(),'private_fixture':str(work)}
 (ROOT/'docs/evidence/single-os-factory-volume.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
finally:
 for target in (data,root):
  if os.path.ismount(target):f.run(['/usr/bin/umount',str(target)])
 f.run(['/usr/sbin/losetup','-d',loop])
