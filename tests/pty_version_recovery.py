"""Actual version API/TUI recovery with an injected interrupted journal and unavailable target."""
import codecs,fcntl,json,os,pathlib,pty,select,struct,subprocess,termios,time,pyte

def recover_missing_target(api,system):
 previous=api({'method':'state'})['active'];target=api({'method':'preview','version':'22.0','network':'regtest'})['preview']['target']
 binary=pathlib.Path(target['binary']);saved=binary.with_name('bitcoind.recovery-test-backup');assert not saved.exists()
 system('stop','justverify-core','justverify-electrs','justverify-policy','justverify-manager')
 binary.rename(saved)
 state=pathlib.Path('/var/lib/justverify/versions');(state/'active.json').write_text(json.dumps(target));(state/'transition.json').write_text(json.dumps({'phase':'starting','previous':previous,'target':target,'error':None}))
 master,slave=pty.openpty();fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',40,120,0,0))
 process=subprocess.Popen(['runuser','-u','justverify','--','/opt/justverify/bin/justverify','tui','--socket','/run/justverify/manager.sock'],stdin=slave,stdout=slave,stderr=slave,env={**os.environ,'TERM':'xterm-256color'});os.close(slave)
 screen=pyte.Screen(120,40);stream=pyte.Stream(screen);decoder=codecs.getincrementaldecoder('utf-8')()
 def wait(text):
  end=time.monotonic()+40
  while time.monotonic()<end:
   assert process.poll() is None
   if select.select([master],[],[],.1)[0]:stream.feed(decoder.decode(os.read(master,65536)))
   if text in '\n'.join(screen.display):return
  raise AssertionError('recovery TUI state missing: '+text+'\n'+'\n'.join(screen.display))
 try:
  response=api({'method':'state'});assert response['active_error'] and response['transition']['needs_recovery']
  wait('JustVerify');os.write(master,b'v');wait('INTERRUPTED VERSION CHANGE')
  os.write(master,b'r');wait('RECOVER INTERRUPTED VERSION CHANGE');wait('31.1');os.write(master,b'\x1b');wait('INTERRUPTED VERSION CHANGE')
  assert api({'method':'state'})['transition']['phase']=='starting'
  os.write(master,b'r');wait('RECOVER INTERRUPTED VERSION CHANGE');os.write(master,b'\r');wait('Recovery result:');wait('rolled_back')
  response=api({'method':'state'});assert response['active']==previous and not response['transition']['needs_recovery']
  assert not binary.exists() # Recovery did not require, recreate or execute the target binary.
  system('is-active','--quiet','justverify-core','justverify-electrs','justverify-policy','justverify-manager')
  os.write(master,b'\x03');assert process.wait(timeout=5)==0
  print('PASS real version API exposes interrupted state despite missing target; PTY review/cancel/recover restores previous separate profile',flush=True)
 finally:
  if process.poll() is None:process.terminate();process.wait(timeout=5)
  os.close(master);saved.rename(binary)
