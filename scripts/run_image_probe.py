#!/usr/bin/env python3
"""Boot a prepared private image twice with a NEW virtual data disk, never hardware."""
import argparse,hashlib,json,pathlib,re,subprocess,time
ROOT=pathlib.Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--image',type=pathlib.Path,required=True);p.add_argument('--data',type=pathlib.Path);p.add_argument('--expand-boot-disk-gib',type=int);p.add_argument('--root-partuuid',default='041bba91-02');p.add_argument('--ssh-port',type=int);p.add_argument('--memory-mib',type=int,default=2048);p.add_argument('--log',type=pathlib.Path,required=True);p.add_argument('--report',type=pathlib.Path,required=True);a=p.parse_args()
assert re.fullmatch(r"[a-f0-9-]{11,36}",a.root_partuuid)
assert a.ssh_port is None or 1024<=a.ssh_port<=65535
assert 2048<=a.memory_mib<=8192
for path in (a.image,*([a.data] if a.data else [])):
 assert path.resolve().parent==(ROOT/'.state/vm').resolve() and not path.is_symlink()
assert a.image.is_file() and (a.data is None or not a.data.exists()) and not a.log.exists() and not a.report.exists()
a.image.chmod(0o600)
original_disk_bytes=a.image.stat().st_size
if a.expand_boot_disk_gib is not None:
 assert a.data is None and 12<=a.expand_boot_disk_gib<=64
 assert original_disk_bytes<a.expand_boot_disk_gib*1024**3
 # Model flashing the compact factory image onto a larger NVMe. Leave GPT
 # and filesystems untouched: the installed first-boot service must grow data.
 with a.image.open('r+b') as disk:disk.truncate(a.expand_boot_disk_gib*1024**3)
boot_disk_bytes=a.image.stat().st_size
if a.data:
 subprocess.run(['qemu-img','create','-f','qcow2',str(a.data),'12G'],check=True,capture_output=True);a.data.chmod(0o600)
command=['qemu-system-aarch64','-machine','virt','-accel','hvf','-cpu','host','-smp','2','-m',str(a.memory_mib),'-kernel',str(ROOT/'.state/vm/probe-kernel'),'-initrd',str(ROOT/'.state/vm/probe-initrd'),'-append',f'root=PARTUUID={a.root_partuuid} rw console=ttyAMA0','-drive',f'file={a.image},if=virtio,format=raw',*(['-drive',f'file={a.data},if=none,id=jvdata,format=qcow2','-device','virtio-blk-pci,drive=jvdata,serial=JV_IMAGE_DATA_01'] if a.data else []),'-netdev','user,id=net0'+(f',hostfwd=tcp:127.0.0.1:{a.ssh_port}-:22' if a.ssh_port else ''),'-device','virtio-net-pci,netdev=net0','-nographic']
started=time.monotonic();timed_out=False
with a.log.open('xb') as log:
 process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
 try:code=process.wait(timeout=900)
 except subprocess.TimeoutExpired:
  timed_out=True;process.terminate()
  try:code=process.wait(timeout=20)
  except subprocess.TimeoutExpired:process.kill();code=process.wait()
records=[]
for line in a.log.read_text(errors='replace').splitlines():
 match=re.search(r'\[\s*([0-9.]+)\] python\[\d+\]: JV_IMAGE_PROBE (\{.*\})$',line)
 if match:
  record=json.loads(match.group(2));record['boot_elapsed_seconds']=float(match.group(1));records.append(record)
result={'status':'PASS' if code==0 and not timed_out and len(records)==2 and all(r['status']=='PASS' for r in records) else 'FAIL','environment':'QEMU virt, external Debian kernel; not Pi firmware or physical hardware','exit_code':code,'timed_out':timed_out,'elapsed_seconds':time.monotonic()-started,'boots':records,'private_image':str(a.image),'private_data':str(a.data),'original_disk_bytes':original_disk_bytes,'boot_disk_bytes':boot_disk_bytes,'console_log':str(a.log),'observer_sha256':hashlib.sha256((ROOT/'tests/image_boot_probe.py').read_bytes()).hexdigest()}
a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'status':result['status'],'boots':len(records),'report':str(a.report)}),flush=True)
if result['status']!='PASS':raise SystemExit(1)
