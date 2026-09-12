#!/usr/bin/env python3
"""Private image fixture: wrong data UUID must block boot services; then repair and reboot."""
import json,os,pathlib,runpy,subprocess,sys,uuid
sys.path.insert(0,'/opt/justverify/scripts')
import factory_volume as f
DONE=pathlib.Path('/var/lib/jv-image-uuid-repaired')
if sys.argv[1:]==['--arm']:
 assert not DONE.exists()
 layout=f.read_root(f.LAYOUT);device=f.devices(f.boot_disk(layout),layout)['data'];plan=f.read_root(f.STATE/'provision.json',True)
 assert not os.path.ismount(f.DATA) and f.fs_uuid(device)==plan['uuid']
 f.run(['/usr/sbin/tune2fs','-U',str(uuid.uuid4()),str(device)])
 print('ARMED isolated image data UUID fault; original root journal preserved')
 raise SystemExit(0)
assert sys.argv[1:]==[]
if DONE.exists():runpy.run_path('/opt/jv-image-original-probe.py',run_name='__main__')
else:
 result={'environment':'QEMU private image only','boot':'expected-volume-fault','checks':{}}
 try:
  assert subprocess.check_output(['systemctl','show','justverify-firstboot','-p','ActiveState','--value']).strip()==b'failed'
  for name in ('core','electrs','tor','web','versions','manager'):
   assert subprocess.check_output(['systemctl','show','justverify-'+name,'-p','MainPID','--value']).strip()==b'0'
  assert not os.path.ismount(f.DATA) and not any(f.DATA.iterdir())
  layout=f.read_root(f.LAYOUT);device=f.devices(f.boot_disk(layout),layout)['data'];plan=f.read_root(f.STATE/'provision.json',True)
  assert plan['phase']=='committed' and f.fs_uuid(device)!=plan['uuid']
  result['checks']['wrong_uuid_blocks_services_without_root_data_fallback']=True
  # This is an explicit test repair of our injected UUID, not product auto-adoption.
  f.run(['/usr/sbin/tune2fs','-U',plan['uuid'],str(device)])
  check=subprocess.run(['/usr/sbin/e2fsck','-f','-p',str(device)],capture_output=True)
  assert check.returncode in (0,1) and f.fs_uuid(device)==plan['uuid']
  DONE.write_text('test repair complete\n');DONE.chmod(0o600)
  result['checks']['explicit_test_repair_restored_original_uuid']=True
  result['status']='PASS'
 except Exception as error:
  result.update(status='FAIL',error_type=type(error).__name__)
 print('JV_IMAGE_PROBE '+json.dumps(result),flush=True)
 subprocess.run(['sync'],check=True)
 subprocess.run(['systemctl','reboot' if result['status']=='PASS' else 'poweroff'],check=True)
