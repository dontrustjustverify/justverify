#!/usr/bin/env python3
"""Actual PTY and root API; resumes the existing dedicated VM filesystem, never formats."""
import codecs,fcntl,json,os,pathlib,pty,select,socket,struct,subprocess,sys,tempfile,termios,time,pyte
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from disk_inventory import inventory
assert os.geteuid()==0 and socket.gethostname()=='justverify-dev'
root=pathlib.Path('/var/tmp/jv-volume-dcq9ed7o');planpath=next((root/'state').glob('*.json'));plan=json.loads(planpath.read_text())
assert plan['device']['serial']=='JUSTVERIFY_TEST_DATA' and not os.path.ismount(root/'mount')
# Recreate an interrupted journal on the already formatted dedicated fixture.
plan['phase']='formatted';planpath.write_text(json.dumps(plan))
owner=root/'owner-fixture.json';owner.write_text(json.dumps({'salt':'0'*32,'hash':'0'*128}));owner.chmod(0o600)
subprocess.run(['systemctl','stop','justverify-storage'],check=True);pathlib.Path('/run/justverify-storage').mkdir(mode=0o755,exist_ok=True)
worker=subprocess.Popen(['python3','-c',"import sys,pathlib,pwd;sys.path.insert(0,sys.argv[1]);from storage_service import StorageAPI,serve;from volume_setup import Volumes;r=pathlib.Path(sys.argv[2]);serve(StorageAPI(Volumes(r/'state',r/'mount',r/'fstab'),r/'owner-fixture.json'),'/run/justverify-storage/api.sock',pwd.getpwnam('justverify').pw_uid)",str(ROOT/'scripts'),str(root)])
deadline=time.monotonic()+10
while True:
 try:
  with socket.socket(socket.AF_UNIX) as ready:
   ready.connect('/run/justverify-storage/api.sock');ready.sendall(b'{"action":"inventory"}\n');reply=json.loads(ready.recv(65536));assert reply['ok']
  break
 except (OSError,ValueError):
  assert worker.poll() is None
  if time.monotonic()>deadline:raise
  time.sleep(.1)
master,slave=pty.openpty();fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',40,120,0,0))
process=subprocess.Popen(['runuser','-u','justverify','--','/tmp/jv-storage-tui','tui','--socket','/run/justverify/manager.sock'],stdin=slave,stdout=slave,stderr=slave,env={**os.environ,'TERM':'xterm-256color'});os.close(slave)
screen=pyte.Screen(120,40);stream=pyte.Stream(screen);decoder=codecs.getincrementaldecoder('utf-8')()
def wait(text):
 end=time.monotonic()+20
 while time.monotonic()<end:
  assert process.poll() is None
  if select.select([master],[],[],.1)[0]:stream.feed(decoder.decode(os.read(master,65536)))
  if text in '\n'.join(screen.display):return
 raise AssertionError('expected storage screen state missing: '+text+'\n'+'\n'.join(screen.display))
try:
 wait('JustVerify');os.write(master,b'\x1b[19~');wait('STORAGE SETUP');wait('SYSTEM_DEVICE');wait('CURRENT_DATA_MOUNT');wait('READ_ONLY')
 rows=inventory()['devices'];index=next(i for i,r in enumerate(rows) if r['reason']=='SYSTEM_DEVICE')
 for _ in range(index):os.write(master,b'\x1b[B');time.sleep(.1)
 os.write(master,b'\r');wait('Selected device is preserved')
 os.write(master,b'r');wait('RECOVER VOLUME');wait(plan['id']);os.write(master,b'\x1b');wait('Up/Down select')
 assert not os.path.ismount(root/'mount')
 os.write(master,b'r');wait('RECOVER VOLUME');os.write(master,b'\r');wait('Volume result:')
 assert os.path.ismount(root/'mount') and (root/'mount'/'reboot-proof').exists()
 assert json.loads(planpath.read_text())['phase']=='committed'
 os.write(master,b'\x1b');wait('Esc 현황');os.write(master,b'\x03');assert process.wait(timeout=5)==0
 print('PASS actual PTY owner API inventory, protected-device selection, recovery review/cancel and real UUID-bound mount recovery')
finally:
 if process.poll() is None:process.terminate();process.wait(timeout=5)
 os.close(master);worker.terminate();worker.wait(timeout=5)
 if os.path.ismount(root/'mount'):subprocess.run(['umount',str(root/'mount')],check=True)
 subprocess.run(['systemctl','start','justverify-storage'],check=True);owner.unlink(missing_ok=True)
