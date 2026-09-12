#!/usr/bin/env python3
import json,os,pathlib,socket,subprocess,time,pty,fcntl,termios,struct,select,codecs,pyte
assert os.geteuid()==0 and socket.gethostname()=='justverify-dev'
units=['justverify-policy','justverify-electrs','justverify-core','justverify-manager']
paths=[pathlib.Path('/etc/justverify')/name for name in ('bitcoin.conf','electrs.toml','profile.json','torrc')]+[pathlib.Path('/etc/systemd/system')/f'justverify-{name}.service.d/20-profile.conf' for name in ('core','electrs','manager','policy')]+[pathlib.Path('/var/lib/justverify/versions')/name for name in ('active.json','transition.json')]
saved={p:p.read_bytes() if p.exists() else None for p in paths}
def system(*args):subprocess.run(['systemctl',*args],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
def api(value,okay=True):
 with socket.socket(socket.AF_UNIX) as s:
  s.settimeout(60);s.connect('/run/justverify-versions/control.sock');s.sendall((json.dumps(value)+'\n').encode());out=b''
  while b:=s.recv(65536):out+=b
 response=json.loads(out);assert response['ok']==okay,response
 return response.get('result',response)
def wait(f):
 end=time.monotonic()+30
 while time.monotonic()<end:
  try:
   value=f()
   if value:return value
  except (OSError,ValueError):pass
  time.sleep(.2)
 raise AssertionError('readiness timeout')
try:
 system('start','justverify-versions')
 state=wait(lambda:api({'method':'state'}));assert len(state['releases'])==34
 api({'method':'state','command':'id'},False)
 master,slave=pty.openpty();fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',40,120,0,0))
 terminal=subprocess.Popen(['runuser','-u','justverify','--','/opt/justverify/bin/justverify','tui','--socket','/run/justverify/manager.sock'],stdin=slave,stdout=slave,stderr=slave,env={**os.environ,'TERM':'xterm-256color'});os.close(slave)
 screen=pyte.Screen(120,40);stream=pyte.Stream(screen);decoder=codecs.getincrementaldecoder('utf-8')()
 def visible(text):
  if select.select([master],[],[],.1)[0]:stream.feed(decoder.decode(os.read(master,65536)))
  return text in '\n'.join(screen.display)
 try:
  wait(lambda:visible('JustVerify'));os.write(master,b'v');wait(lambda:visible('CORE VERSION'))
  os.write(master,b'nnnn');wait(lambda:visible('network: regtest'))
  os.write(master,b'\r');wait(lambda:visible('REVIEW VERSION CHANGE'))
  os.write(master,b'\x1b');wait(lambda:visible('CORE VERSION'));assert api({'method':'state'})['active'] is None
  os.write(master,b'\r');wait(lambda:visible('REVIEW VERSION CHANGE'));os.write(master,b'\r');wait(lambda:visible('committed'))
  assert api({'method':'state'})['active']['instance']['core_version']=='31.1'
  os.write(master,b'\x03');terminal.wait(timeout=5)
 finally:
  if terminal.poll() is None:terminal.terminate();terminal.wait(timeout=5)
  os.close(master)
 for version in ('22.0','31.1'):
  preview=api({'method':'preview','version':version,'network':'regtest'})
  assert preview['preview']['target']['instance']['core_version']==version
  result=api({'method':'apply','token':preview['token']});assert result['phase']=='committed',result
  assert api({'method':'state'})['active']['instance']['core_version']==version
  api({'method':'apply','token':preview['token']},False)
  system('is-active','--quiet',*units)
 print(json.dumps({'status':'PASS','checks':['actual unprivileged version service and fixed privileged bridge','real PTY V/network/review/Escape cancellation/Enter application','34 releases retained in API','real preview and systemd apply31.1 to22.0 to31.1','one-time apply token','unknown request fields denied','policy/electrs/Core/collector restart']},indent=2))
finally:
 system('stop','justverify-versions',*units)
 for p,content in saved.items():
  if content is None:p.unlink(missing_ok=True)
  else:p.write_bytes(content)
 system('daemon-reload');system('reset-failed',*units);system('start',*units)
 print('Original development profile restored; unregistered version API kept stopped.')
