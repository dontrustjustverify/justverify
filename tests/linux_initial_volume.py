#!/usr/bin/env python3
"""Read-only initial registration guard against the previously formatted dedicated VM disk."""
import hashlib,json,os,pathlib,secrets,shutil,subprocess,sys
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from profile_helper import check_initial
from disk_inventory import inventory
assert os.geteuid()==0
root=pathlib.Path('/var/tmp/jv-ui-format-2afymm60');data=root/'mount';state=root/'state'
plan=next(json.loads(p.read_text()) for p in state.glob('*.json') if json.loads(p.read_text())['phase']=='committed')
rows=[r for r in inventory()['devices'] if r['serial']=='JUSTVERIFY_UI_TEST'];assert len(rows)==1 and rows[0]['uuid']==plan['uuid'] and not rows[0]['mountpoints']
owner=root/'initial-owner.json';owner.write_text(json.dumps({'salt':secrets.token_hex(16),'hash':secrets.token_hex(64)}));owner.chmod(0o600)
subprocess.run(['mount','-t','ext4','-o','nodev,nosuid,noexec','UUID='+plan['uuid'],str(data)],check=True)
marker=data/'justverify-volume.json';original=marker.read_bytes();proof=data/'tui-proof';saved=root/'saved-tui-proof';proof_digest=hashlib.sha256(proof.read_bytes()).hexdigest()
def rejected():
 try:check_initial(data,owner,state)
 except ValueError:return
 raise AssertionError('unsafe initial registration accepted')
try:
 rejected() # The existing test proof counts as preserved user content.
 shutil.move(str(proof),str(saved))
 check_initial(data,owner,state)
 print('PASS genuine committed mounted volume eligible only after empty-layout review',flush=True)
 (data/'instances'/'existing').mkdir();rejected();(data/'instances'/'existing').rmdir()
 value=json.loads(original);value['uuid']='00000000-0000-0000-0000-000000000000';marker.write_text(json.dumps(value));rejected();marker.write_bytes(original)
 marker.chmod(0o666);rejected();marker.chmod(0o600)
 before=owner.read_bytes();owner.write_text('{}');rejected();owner.write_bytes(before)
 journal=next(p for p in state.glob('*.json') if json.loads(p.read_text())['phase']=='committed');before=journal.read_bytes();value=json.loads(before);value['phase']='formatted';journal.write_text(json.dumps(value));rejected();journal.write_bytes(before)
 check_initial(data,owner,state)
 print('PASS populated instances, wrong UUID, writable marker, unclaimed owner and interrupted journal rejected',flush=True)
 shutil.move(str(saved),str(proof));assert marker.read_bytes()==original;assert hashlib.sha256(proof.read_bytes()).hexdigest()==proof_digest
 subprocess.run(['umount',str(data)],check=True);rejected()
 print('PASS missing mount rejected; original dedicated proof/marker restored; no services changed',flush=True)
finally:
 if saved.exists() and os.path.ismount(data):shutil.move(str(saved),str(proof))
 if os.path.ismount(data):
  marker.write_bytes(original);marker.chmod(0o600);subprocess.run(['umount',str(data)],check=True)
 owner.unlink(missing_ok=True)
