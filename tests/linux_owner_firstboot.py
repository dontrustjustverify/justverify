#!/usr/bin/env python3
"""Disposable VM firstboot/physical-PTY owner flow, restoring original credentials afterward."""
import fcntl,termios,struct,hashlib,http.client,json,os,pathlib,pty,secrets,select,shutil,socket,ssl,subprocess,time
assert os.geteuid()==0 and socket.gethostname()=='justverify-dev'
state=pathlib.Path('/var/lib/justverify/web');backup=state.with_name('web-owner-test-backup');assert not backup.exists()
boot=pathlib.Path('/boot/firmware/justverify-owner.json');assert not boot.exists();boot.parent.mkdir(parents=True,exist_ok=True)
token=secrets.token_urlsafe(32);process=None;master=None
subprocess.run(['systemctl','stop','justverify-web'],check=True);state.rename(backup)
try:
 boot.write_text(json.dumps({'format':'justverify-owner-v1','setup_token':token}));boot.chmod(0o600)
 first=subprocess.run(['/opt/justverify/scripts/firstboot.sh'],capture_output=True,check=True)
 assert token.encode() not in first.stdout+first.stderr and not boot.exists()
 assert (state/'setup-token').read_text().strip()==token
 certificate=(state/'certificate.pem').read_bytes()
 subprocess.run(['/opt/justverify/scripts/firstboot.sh'],stdout=subprocess.DEVNULL,check=True)
 assert (state/'certificate.pem').read_bytes()==certificate
 subprocess.run(['systemctl','start','justverify-web'],check=True)
 master,slave=pty.openpty();fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack("HHHH",40,120,0,0))
 process=subprocess.Popen(['runuser','-u','justverify','--','python3','/opt/justverify/scripts/owner_console.py'],stdin=slave,stdout=slave,stderr=subprocess.DEVNULL,env={**os.environ,'TERM':'xterm-256color'});os.close(slave)
 def read_until(value,seconds=10):
  data=b'';end=time.monotonic()+seconds
  while time.monotonic()<end:
   if select.select([master],[],[],.1)[0]:data+=os.read(master,65536)
   if value in data:return data
  raise AssertionError('expected console state was not displayed')
 initial=read_until(b'Enter');assert token.encode() not in initial
 os.write(master,b'\n');shown=read_until(token.encode());assert b'SHA256' in shown
 context=ssl.create_default_context(cafile=str(state/'certificate.pem'))
 end=time.monotonic()+10
 while True:
  try:
   conn=http.client.HTTPSConnection('127.0.0.1',443,context=context,timeout=5);conn.request('GET','/pairing-proof');response=conn.getresponse();assert response.status==200;response.read();conn.close();break
  except OSError:
   if time.monotonic()>end:raise
   time.sleep(.1)
 conn=http.client.HTTPSConnection('127.0.0.1',443,context=context,timeout=5)
 conn.request('POST','/login',json.dumps({'setup_token':token,'password':secrets.token_urlsafe(24)}),{'Content-Type':'application/json','Origin':'https://justverify.local'})
 response=conn.getresponse();assert response.status==200;response.read();conn.close()
 assert not (state/'setup-token').exists()
 read_until('Esc 현황'.encode())
 os.write(master,b'\x03');assert process.wait(timeout=5)==0
 print(json.dumps({'status':'PASS','checks':['actual Linux firstboot imports and removes boot owner file','firstboot output does not reveal setup secret','repeated firstboot preserves TLS identity','physical PTY requires Enter before displaying owner code','claim over certificate-verified HTTPS','one-time token removed','console switches to fixed real TUI','Ctrl-C exits without shell']},indent=2))
finally:
 if process is not None and process.poll() is None:process.terminate();process.wait(timeout=5)
 if master is not None:os.close(master)
 subprocess.run(['systemctl','stop','justverify-web'],check=True)
 if state.exists():shutil.rmtree(state)
 backup.rename(state);boot.unlink(missing_ok=True)
 subprocess.run(['systemctl','start','justverify-web'],check=True)
