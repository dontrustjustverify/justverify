#!/usr/bin/env python3
"""Actual TUI destructive test restricted to a new project VM disk JUSTVERIFY_UI_TEST."""
import codecs,fcntl,json,os,pathlib,pty,select,socket,struct,subprocess,sys,tempfile,termios,time,pyte
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from disk_inventory import inventory
from storage_probe import inspect
assert os.geteuid()==0 and socket.gethostname()=='justverify-dev'
rows=inventory()['devices'];targets=[r for r in rows if r['serial']=='JUSTVERIFY_UI_TEST'];assert len(targets)==1
target=targets[0];assert target['size_bytes']==2*1024**3 and target['review_action']=='REVIEW_NEW' and not target['mountpoints']
scan=inspect(target['name'],target['identity_digest']);assert scan['review']=='NO_KNOWN_SIGNATURES_CONTENTS_NOT_PROVEN_EMPTY'
root=pathlib.Path(tempfile.mkdtemp(prefix='jv-ui-format-',dir='/var/tmp'));(root/'fstab').write_text('# isolated TUI test fstab\n');(root/'owner.json').write_text('{}');(root/'owner.json').chmod(0o600)
original_fstab=pathlib.Path('/etc/fstab').read_bytes();original_data=os.stat('/srv/justverify/data').st_dev
subprocess.run(['systemctl','stop','justverify-storage'],check=True);pathlib.Path('/run/justverify-storage').mkdir(mode=0o755,exist_ok=True)
worker=subprocess.Popen(['python3','-c',"import sys,pathlib,pwd;sys.path.insert(0,sys.argv[1]);from storage_service import StorageAPI,serve;from volume_setup import Volumes;r=pathlib.Path(sys.argv[2]);serve(StorageAPI(Volumes(r/'state',r/'mount',r/'fstab'),r/'owner.json'),'/run/justverify-storage/api.sock',pwd.getpwnam('justverify').pw_uid)",str(ROOT/'scripts'),str(root)])
deadline=time.monotonic()+10
while True:
 try:
  with socket.socket(socket.AF_UNIX) as ready:
   ready.connect('/run/justverify-storage/api.sock');ready.sendall(b'{"action":"inventory"}\n');reply=json.loads(ready.makefile('rb').readline());assert reply['ok']
  break
 except (OSError,ValueError):
  assert worker.poll() is None
  if time.monotonic()>deadline:raise
  time.sleep(.1)
master,slave=pty.openpty();fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',40,120,0,0))
process=subprocess.Popen(['runuser','-u','justverify','--','/tmp/jv-storage-tui','tui','--socket','/run/justverify/manager.sock'],stdin=slave,stdout=slave,stderr=slave,env={**os.environ,'TERM':'xterm-256color'});os.close(slave)
screen=pyte.Screen(120,40);stream=pyte.Stream(screen);decoder=codecs.getincrementaldecoder('utf-8')()
def wait(text):
 end=time.monotonic()+30
 while time.monotonic()<end:
  assert process.poll() is None
  if select.select([master],[],[],.1)[0]:stream.feed(decoder.decode(os.read(master,65536)))
  if text in '\n'.join(screen.display):return
 raise AssertionError('expected TUI state missing: '+text+'\n'+'\n'.join(screen.display))
try:
 wait('JustVerify');os.write(master,b'\x1b[19~');wait('SYSTEM_DEVICE')
 index=next(i for i,r in enumerate(rows) if r['serial']=='JUSTVERIFY_UI_TEST')
 for _ in range(index):os.write(master,b'\x1b[B');time.sleep(.1)
 os.write(master,b'\r');wait('ERASE DEVICE');wait('ERASE JUSTVERIFY_UI_TEST')
 fcntl.ioctl(master,termios.TIOCSWINSZ,struct.pack('HHHH',24,80,0,0));screen.resize(24,80)
 wait('Type exactly: ERASE JUSTVERIFY_UI_TEST')
 os.write(master,b'WRONG\r');wait('No format requested')
 assert inspect(target['name'],target['identity_digest'])['scan_digest']==scan['scan_digest']
 os.write(master,b'\x1b');wait('Up/Down select')
 assert inspect(target['name'],target['identity_digest'])['scan_digest']==scan['scan_digest']
 print('PASS actual 80x24 TUI erasure preview/wrong confirmation/Esc preserve blank disk',flush=True)
 os.write(master,b'\r');wait('ERASE DEVICE');wait('ERASE JUSTVERIFY_UI_TEST');os.write(master,b'ERASE JUSTVERIFY_UI_TEST\r');wait('Volume result:')
 assert os.path.ismount(root/'mount')
 plans=[json.loads(p.read_text()) for p in (root/'state').glob('*.json')];committed=[p for p in plans if p['phase']=='committed'];assert len(committed)==1
 plan=committed[0];assert plan['device']['serial']=='JUSTVERIFY_UI_TEST'
 assert json.loads((root/'mount'/'justverify-volume.json').read_text())['uuid']==plan['uuid']
 assert pathlib.Path('/etc/fstab').read_bytes()==original_fstab and os.stat('/srv/justverify/data').st_dev==original_data
 (root/'mount'/'tui-proof').write_text('Actual TUI-confirmed format completed\n');subprocess.run(['sync'],check=True)
 os.write(master,b'\x1b');wait('Esc 현황');os.write(master,b'\x03');assert process.wait(timeout=5)==0
 print('PASS actual TUI exact confirmation -> root API -> mkfs.ext4 -> UUID mount/fstab commit; original data preserved',flush=True)
 print('Fixture: '+str(root),flush=True)
finally:
 if process.poll() is None:process.terminate();process.wait(timeout=5)
 os.close(master);worker.terminate();worker.wait(timeout=5)
 if os.path.ismount(root/'mount'):subprocess.run(['umount',str(root/'mount')],check=True)
 subprocess.run(['systemctl','start','justverify-storage'],check=True);(root/'owner.json').unlink(missing_ok=True)
