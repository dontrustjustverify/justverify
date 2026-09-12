"""Real nonprivileged TUI navigation against running production storage/version services."""
import codecs,fcntl,os,pty,select,struct,subprocess,termios,time,pyte

def review_initial_profile():
 master,slave=pty.openpty();fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',40,120,0,0))
 process=subprocess.Popen(['runuser','-u','justverify','--','/opt/justverify/bin/justverify','tui','--socket','/run/justverify/manager.sock'],stdin=slave,stdout=slave,stderr=slave,env={**os.environ,'TERM':'xterm-256color'});os.close(slave)
 screen=pyte.Screen(120,40);stream=pyte.Stream(screen);decoder=codecs.getincrementaldecoder('utf-8')()
 def wait(text):
  end=time.monotonic()+30
  while time.monotonic()<end:
   assert process.poll() is None
   if select.select([master],[],[],.1)[0]:stream.feed(decoder.decode(os.read(master,65536)))
   if text in '\n'.join(screen.display):return
  raise AssertionError('expected TUI state not visible: '+text+'\n'+'\n'.join(screen.display))
 try:
  wait('JustVerify');os.write(master,b'\x1b[19~');wait('CURRENT_DATA_MOUNT')
  os.write(master,b'b');wait('Version selection ready')
  os.write(master,b'\x1b');wait('management daemon UNAVAILABLE');os.write(master,b'v');wait('CORE VERSION');wait('FIRST PROFILE')
  os.write(master,b'nnnn');wait('network: regtest')
  os.write(master,b'w');wait('mode: watch-only');os.write(master,b'\r');wait('REVIEW VERSION CHANGE');wait('mode watch-only')
  os.write(master,b'\x1b');wait('FIRST PROFILE');os.write(master,b'w');wait('mode: node')
  os.write(master,b'\r');wait('REVIEW VERSION CHANGE')
  os.write(master,b'\x1b');wait('FIRST PROFILE');os.write(master,b'\x03');assert process.wait(timeout=5)==0
  print('PASS actual non-root PTY S/B starts version service; V/W wallet mode/network/review/cancel works',flush=True)
 finally:
  if process.poll() is None:process.terminate();process.wait(timeout=5)
  os.close(master)
