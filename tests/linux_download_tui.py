#!/usr/bin/env python3
import codecs,fcntl,json,os,pathlib,pty,select,socket,struct,subprocess,termios,time,pyte
assert os.geteuid()==0 and socket.gethostname()=='justverify-dev'
subprocess.run(['systemctl','start','justverify-versions'],check=True)
master,slave=pty.openpty();fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',40,120,0,0))
process=subprocess.Popen(['runuser','-u','justverify','--','/opt/justverify/bin/justverify','tui','--socket','/run/justverify/manager.sock'],stdin=slave,stdout=slave,stderr=slave,env={**os.environ,'TERM':'xterm-256color'});os.close(slave)
screen=pyte.Screen(120,40);stream=pyte.Stream(screen);decoder=codecs.getincrementaldecoder('utf-8')()
def wait(text,seconds=20):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  assert process.poll() is None
  if select.select([master],[],[],.1)[0]:stream.feed(decoder.decode(os.read(master,65536)))
  if text in '\n'.join(screen.display):return
 raise AssertionError('missing TUI text: '+text+'\n'+'\n'.join(screen.display))
try:
 wait('JustVerify');os.write(master,b'v');wait('CORE VERSION')
 os.write(master,b'p')
 # Expanded catalog order is the displayed order.
 releases=json.loads(pathlib.Path('/opt/justverify/catalog/releases.json').read_text())['releases']
 index=next(i for i,r in enumerate(releases) if r['version']=='23.2')
 os.write(master,b'\x1b[B'*index+b'd');wait('Official download started')
 wait('Download: 23.2 complete',40)
 os.write(master,b'\x03');process.wait(timeout=5)
 print('PASS actual PTY V/P/selection/D and background verified-download completion display')
finally:
 if process.poll() is None:process.terminate();process.wait(timeout=5)
 os.close(master);subprocess.run(['systemctl','stop','justverify-versions'],check=True)
