#!/usr/bin/env python3
import json,os,pathlib,socket,subprocess,time
assert os.geteuid()==0 and socket.gethostname()=='justverify-dev'
config=pathlib.Path('/etc/justverify/versions.json');saved=config.read_bytes()
def system(action):subprocess.run(['systemctl',action,'justverify-versions'],check=True)
def api(value):
 with socket.socket(socket.AF_UNIX) as s:
  s.settimeout(10);s.connect('/run/justverify-versions/control.sock');s.sendall((json.dumps(value)+'\n').encode());out=b''
  while b:=s.recv(65536):out+=b
 return json.loads(out)
try:
 value=json.loads(saved);value.pop('allow_initial_selection',None);config.write_text(json.dumps(value))
 system('start')
 end=time.monotonic()+10
 while True:
  try:state=api({'method':'state'});break
  except OSError:
   if time.monotonic()>end:raise
   time.sleep(.1)
 assert state['ok'] and state['result']['active'] is None
 result=api({'method':'preview','version':'31.1','network':'regtest'})
 assert not result['ok'] and 'registration' in result['error'],result
 print('PASS unregistered existing profile cannot be replaced through production-default version API')
finally:
 system('stop');config.write_bytes(saved)
