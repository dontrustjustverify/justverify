#!/usr/bin/env python3
"""Read-only startup gate binding the registered profile to its mounted data and configs."""
import hashlib,json,os,pathlib,stat,subprocess

def check(data=pathlib.Path('/srv/justverify/data'),etc=pathlib.Path('/etc/justverify'),active=pathlib.Path('/var/lib/justverify/versions/active.json')):
 transition=active.parent/'transition.json'
 if transition.exists():
  journal=json.loads(transition.read_text())
  if journal.get('reset') and journal['phase'] not in ('starting','committed','rolled_back','stop_failed') and not (journal['phase']=='restoring_previous' and not journal.get('deletion_started')):
   raise ValueError('version reset recovery must finish before services start')
 guard=etc/'version-reset-guard.json'
 if guard.exists():
  metadata=guard.lstat()
  if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid!=0 or metadata.st_mode&0o022:raise ValueError('invalid reset guard')
  blocked=json.loads(guard.read_text())
  if not blocked.get('target_ready'):raise ValueError('root reset completion check required before startup')
  if not transition.exists() or journal['phase'] not in ('starting','committed'):raise ValueError('version reset blocks automatic startup')
  if json.loads(active.read_text())['instance']!=blocked['target']:raise ValueError('old binary start forbidden after reset')
 marker=etc/'node-ready.json';metadata=marker.lstat()
 if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid!=0 or metadata.st_mode&0o022:raise ValueError('untrusted registration marker')
 ready=json.loads(marker.read_text())
 if ready.get('schema')!=1 or data.is_symlink() or not os.path.ismount(data):raise ValueError('registered volume unavailable')
 uuid=subprocess.run(['/usr/bin/findmnt','-n','-o','UUID','--target',str(data)],check=True,capture_output=True,text=True,timeout=10).stdout.strip()
 if not uuid or uuid!=ready['uuid']:raise ValueError('registered volume UUID mismatch')
 for name in ('bitcoin.conf','electrs.toml','profile.json'):
  path=etc/name;metadata=path.lstat()
  if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid!=0 or metadata.st_mode&0o022:raise ValueError('untrusted profile configuration')
  if hashlib.sha256(path.read_bytes()).hexdigest()!=ready['configs'][name]:raise ValueError('profile update incomplete')
 profile=json.loads((etc/'profile.json').read_text());selection=json.loads(active.read_text())
 if selection['instance']!=ready['instance'] or selection['binary']!=profile['binary'] or profile['version']!=ready['instance']['core_version'] or profile['network']!=ready['instance']['network']:raise ValueError('selected profile differs from registered profile')
 binary=pathlib.Path(profile['binary'])
 if hashlib.sha256(binary.read_bytes()).hexdigest()!=ready['binary_sha256'] or selection['binary_sha256']!=ready['binary_sha256']:raise ValueError('registered binary changed')
 watch_only=profile.get('watch_only',False)
 if type(watch_only) is not bool or watch_only!=ready['instance'].get('watch_only',False):raise ValueError('wallet mode differs from registered profile')
 import re
 instance=ready['instance']
 name=instance.get('data_id',profile['version']+('-watch-only' if watch_only else ''))
 if profile.get('data_id',name)!=name:raise ValueError('explorer storage identity differs from registration')
 if not re.fullmatch(r'[0-9]+\.[0-9]+(?:\.[0-9]+)?'+('-watch-only' if watch_only else ''),name):raise ValueError('invalid registered storage identity')
 folder=data/'instances'/profile['network']/name
 if instance['core_data']!=str(folder/'core') or instance['electrs_data']!=str(folder/'electrs-0.11.1'):raise ValueError('registered paths changed')
 current=data
 for part in folder.relative_to(data).parts:
  current=current/part
  if current.is_symlink():raise ValueError('linked registered data refused')
 if json.loads((folder/'instance.json').read_text())!=ready['instance']:raise ValueError('registered instance missing or changed')
 for name in ('core','electrs-0.11.1'):
  path=folder/name
  if path.is_symlink() or not path.is_dir():raise ValueError('registered data directory missing')

if __name__=='__main__':
 import sys
 if len(sys.argv)!=1:raise SystemExit('fixed registration gate takes no arguments')
 try:check()
 except Exception:raise SystemExit('Node registration incomplete or selected volume/profile changed; use setup or recovery.')
