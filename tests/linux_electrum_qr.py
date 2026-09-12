#!/usr/bin/env python3
"""Actual PTY QR capture as module bits; public address is not printed."""
import codecs,fcntl,json,os,pathlib,pty,select,struct,subprocess,sys,termios,time,pyte
assert os.geteuid()==0
assert sys.argv[1:] in ([],['--lan'])
lan=bool(sys.argv[1:])
master,slave=pty.openpty();fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',40,120,0,0))
process=subprocess.Popen(['runuser','-u','justverify','--','/opt/justverify/bin/justverify','tui','--socket','/run/justverify/manager.sock'],stdin=slave,stdout=slave,stderr=slave,env={**os.environ,'TERM':'xterm-256color'});os.close(slave)
screen=pyte.Screen(120,40);stream=pyte.Stream(screen);decoder=codecs.getincrementaldecoder('utf-8')()
def wait(text):
 end=time.monotonic()+20
 while time.monotonic()<end:
  assert process.poll() is None
  if select.select([master],[],[],.1)[0]:stream.feed(decoder.decode(os.read(master,65536)))
  if text in '\n'.join(screen.display):return
 raise AssertionError('expected QR screen missing')
try:
 wait('JustVerify');os.write(master,b'q');wait('TOR ELECTRUM');wait('▀')
 if lan:os.write(master,b'l');wait('LAN ELECTRUM');wait('Certificate SHA256:')
 raw=json.loads(subprocess.check_output(['/opt/justverify/venv/bin/python','/opt/justverify/web/electrum_qr.py']+(['--lan'] if lan else [])))['result'];size=len(raw['matrix']);bits=[]
 if lan:
  assert raw['tls'] is True and raw['payload']=='justverify.local:50002'
  assert raw['certificate_sha256'][:32] in '\n'.join(screen.display) and raw['certificate_sha256'][32:] in '\n'.join(screen.display)
 for y in range((size+1)//2):
  cells=[screen.buffer[(8 if lan else 6)+y][1+x] for x in range(size)]
  assert all(c.fg in ('black','000000') and c.bg in ('white','brightwhite','ffffff') for c in cells),str({(c.fg,c.bg) for c in cells})
  bits.append([c.data in ('█','▀') for c in cells]);bits.append([c.data in ('█','▄') for c in cells])
 bits=bits[:size];assert bits==raw['matrix']
 out=pathlib.Path('/var/tmp/jv-electrum-'+('lan-' if lan else '')+'qr-capture.json');out.write_text(json.dumps({'payload':raw['payload'],'matrix':bits}));out.chmod(0o600)
 fcntl.ioctl(master,termios.TIOCSWINSZ,struct.pack('HHHH',24,80,0,0));screen.resize(24,80);wait('Enlarge the terminal')
 os.write(master,b'\x1b');wait('노드 요약');os.write(master,b'\x03');assert process.wait(timeout=5)==0
 print('PASS actual PTY black/white QR cells match payload matrix; 80x24 declines clipped QR; Esc returns')
finally:
 if process.poll() is None:process.terminate();process.wait(timeout=5)
 os.close(master)
