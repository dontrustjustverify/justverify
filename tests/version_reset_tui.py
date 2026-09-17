#!/usr/bin/env python3
"""Exercise the actual unprivileged TUI against the disposable regtest API."""
from version_reset_native import *
import codecs,fcntl,pty,select,struct,termios
import pyte

def screen_text(screen):
 # pyte.display indexes an empty wide-character continuation cell while a
 # Korean frame is being repainted. Read the actual grid without that renderer.
 return '\n'.join(''.join(screen.buffer[y][x].data for x in range(screen.columns)) for y in range(screen.lines))

def run_review():
 assert okay('state')['active']['instance']['core_version']=='31.1'
 master,slave=pty.openpty();fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',48,140,0,0))
 process=subprocess.Popen(['runuser','-u','justverify','--','/opt/justverify/bin/justverify','tui','--socket','/run/justverify/manager.sock'],stdin=slave,stdout=slave,stderr=slave,env={**os.environ,'TERM':'xterm-256color'});os.close(slave)
 screen=pyte.Screen(140,48);stream=pyte.Stream(screen);decoder=codecs.getincrementaldecoder('utf-8')()
 def visible(text,seconds=70):
  end=time.monotonic()+seconds
  while time.monotonic()<end:
   assert process.poll() is None
   if select.select([master],[],[],.1)[0]:stream.feed(decoder.decode(os.read(master,65536)))
   if text in screen_text(screen):return
  raise AssertionError('required TUI state not shown: '+text)
 try:
  visible('JustVerify');os.write(master,b'v');visible('CORE VERSION')
  # Default selection is latest. Select oldest major card (22.1), then expand
  # patches and select the explicitly installed 22.0 release.
  os.write(master,b'p');time.sleep(.2);os.write(master,b'\r');visible('버전 변경 확인')
  visible('보존 대상');visible('동기화')
  text=screen_text(screen);assert '삭제 대상' in text and '보존 대상' in text and '/blocks' in text and '동기화' in text
  assert '> 취소' in text
  os.write(master,b'\r\r\r');time.sleep(.4)
  assert okay('state')['active']['instance']['core_version']=='31.1'
  os.write(master,b'\x1b');visible('CORE VERSION');assert okay('state')['active']['instance']['core_version']=='31.1'
  os.write(master,b'\r');visible('버전 변경 확인');os.write(master,b'\x1b[C');visible('> 데이터 삭제 후 버전 변경')
  os.write(master,b' ');visible('committed',150)
  assert okay('state')['active']['instance']['core_version']=='22.0'
  assert rpc('getblockcount')==0
  print(json.dumps({'status':'PASS','checks':['real unprivileged PTY','same authoritative deletion scope and preservation warning','cancel default','repeated Enter never deletes','Escape cancellation','deliberate Right then Space commits target genesis']}))
 finally:
  if process.poll() is None:process.terminate();process.wait(timeout=10)
  os.close(master)
def run_recovery():
 before=okay('state')['transition'];assert before['needs_recovery'] and before['deletion_started']
 target=before['target']['instance']['core_version']
 master,slave=pty.openpty();fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',42,140,0,0))
 process=subprocess.Popen(['runuser','-u','justverify','--','/opt/justverify/bin/justverify','tui','--socket','/run/justverify/manager.sock'],stdin=slave,stdout=slave,stderr=slave,env={**os.environ,'TERM':'xterm-256color'});os.close(slave)
 screen=pyte.Screen(140,42);stream=pyte.Stream(screen);decoder=codecs.getincrementaldecoder('utf-8')()
 def visible(text,seconds=90):
  end=time.monotonic()+seconds
  while time.monotonic()<end:
   assert process.poll() is None
   if select.select([master],[],[],.1)[0]:stream.feed(decoder.decode(os.read(master,65536)))
   if text in screen_text(screen):return
  raise AssertionError('recovery TUI state missing: '+text)
 try:
  visible('JustVerify');os.write(master,b'v');visible('INTERRUPTED VERSION CHANGE');os.write(master,b'r');visible('RECOVER INTERRUPTED VERSION CHANGE');visible('ONLY the target')
  os.write(master,b'\x1b');visible('INTERRUPTED VERSION CHANGE');assert okay('state')['transition']['phase']==before['phase']
  os.write(master,b'r');visible('RECOVER INTERRUPTED VERSION CHANGE');os.write(master,b'\r');visible('committed')
  assert okay('state')['active']['instance']['core_version']==target and rpc('getblockcount')==0
  print('PASS actual postboot TUI recovery review/cancel/confirm resumes only the approved target',flush=True)
 finally:
  if process.poll() is None:process.terminate();process.wait(timeout=10)
  os.close(master)
if __name__=='__main__':
 import sys
 run_recovery() if sys.argv[1:]==['recover'] else run_review()
