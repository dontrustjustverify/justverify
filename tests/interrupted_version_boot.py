"""Test-only pause of the privileged bridge, real SIGKILL, and postboot TUI recovery."""
import codecs,fcntl,json,os,pathlib,pty,select,struct,subprocess,termios,threading,time,pyte

def interrupt(api,system):
 preview=api({'method':'preview','version':'22.0','network':'regtest'})
 helper=pathlib.Path('/usr/libexec/justverify-profile');original=helper.read_bytes();real=helper.with_name('justverify-profile-interruption-test');assert not real.exists()
 pause=pathlib.Path('/var/lib/justverify/versions/paused-activation-test');pause.unlink(missing_ok=True)
 real.write_bytes(original);real.chmod(0o755)
 helper.write_text('''#!/usr/bin/python3 -I
import json,pathlib,subprocess,sys,time
raw=sys.stdin.buffer.read(4097);request=json.loads(raw)
if request=={'action':'activate','version':'22.0','network':'regtest'}:
 pathlib.Path('/var/lib/justverify/versions/paused-activation-test').write_text('ready')
 time.sleep(300)
else:
 sys.exit(subprocess.run(['/usr/libexec/justverify-profile-interruption-test'],input=raw).returncode)
''');helper.chmod(0o755)
 def apply():
  try:api({'method':'apply','token':preview['token']})
  except Exception:pass # The real socket is expected to disconnect when its server is killed.
 thread=threading.Thread(target=apply,daemon=True);thread.start()
 try:
  end=time.monotonic()+30
  while not pause.exists():
   if time.monotonic()>end:raise AssertionError('actual apply did not reach privileged activation')
   time.sleep(.05)
  state=pathlib.Path('/var/lib/justverify/versions');journal=json.loads((state/'transition.json').read_text());active=json.loads((state/'active.json').read_text())
  assert journal['phase']=='starting' and active==journal['target'] and active['instance']['core_version']=='22.0'
  system('kill','--signal=SIGKILL','justverify-versions');system('stop','justverify-versions');thread.join(timeout=5);assert not thread.is_alive()
  assert json.loads((state/'transition.json').read_text())['phase']=='starting'
  print('PASS actual apply persisted starting/target22; version service and helper killed with SIGKILL',flush=True)
 finally:
  helper.write_bytes(original);helper.chmod(0o755);real.unlink(missing_ok=True);pause.unlink(missing_ok=True)

def recover_after_boot():
 assert subprocess.check_output(['systemctl','show','justverify-core','-p','MainPID','--value'],text=True).strip()=='0'
 gate=subprocess.run(['runuser','-u','justverify','--','python3','/opt/justverify/scripts/node_ready.py'],capture_output=True);assert gate.returncode!=0
 master,slave=pty.openpty();fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',40,120,0,0))
 process=subprocess.Popen(['runuser','-u','justverify','--','/opt/justverify/bin/justverify','tui','--socket','/run/justverify/manager.sock'],stdin=slave,stdout=slave,stderr=slave,env={**os.environ,'TERM':'xterm-256color'});os.close(slave)
 screen=pyte.Screen(120,40);stream=pyte.Stream(screen);decoder=codecs.getincrementaldecoder('utf-8')()
 def wait(text):
  end=time.monotonic()+50
  while time.monotonic()<end:
   assert process.poll() is None
   if select.select([master],[],[],.1)[0]:stream.feed(decoder.decode(os.read(master,65536)))
   if text in '\n'.join(screen.display):return
  raise AssertionError('postboot recovery UI missing: '+text+'\n'+'\n'.join(screen.display))
 try:
  wait('JustVerify');os.write(master,b'v');wait('INTERRUPTED VERSION CHANGE');os.write(master,b'r');wait('RECOVER INTERRUPTED VERSION CHANGE');os.write(master,b'\r');wait('rolled_back')
  state=pathlib.Path('/var/lib/justverify/versions');assert json.loads((state/'transition.json').read_text())['phase']=='rolled_back';assert json.loads((state/'active.json').read_text())['instance']['core_version']=='31.1'
  os.write(master,b'\x03');assert process.wait(timeout=5)==0
  print('PASS postboot startup gate prevented mismatched Core; actual TUI R recovered prior31 profile',flush=True)
 finally:
  if process.poll() is None:process.terminate();process.wait(timeout=5)
  os.close(master)
