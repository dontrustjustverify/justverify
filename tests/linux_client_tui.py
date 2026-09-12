#!/usr/bin/env python3
"""Real PTY issuance/revocation and verified TLS RPC; never print captured credentials."""
import base64,codecs,fcntl,hashlib,http.client,json,os,pathlib,pty,pwd,re,secrets,select,shutil,socket,ssl,stat,struct,subprocess,sys,tempfile,termios,time,pyte
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'));from web_identity import ensure_identity
assert os.geteuid()==0 and socket.gethostname()=='justverify-dev'
work=pathlib.Path(tempfile.mkdtemp(prefix='jv-client-tui-',dir='/var/tmp'));state=pathlib.Path('/var/lib/justverify/web');account=pwd.getpwnam('justverify')
tls_active=subprocess.run(['systemctl','is-active','--quiet','justverify-electrum-tls']).returncode==0
if tls_active:subprocess.run(['systemctl','stop','justverify-electrum-tls'],check=True)
subprocess.run(['systemctl','stop','justverify-web'],check=True);state.rename(work/'original-web');process=None;server=None;master=None
try:
 ensure_identity(state);admin_password=secrets.token_urlsafe(24);salt=secrets.token_hex(16)
 (state/'admin.json').write_text(json.dumps({'salt':salt,'hash':hashlib.scrypt(admin_password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()}));(state/'setup-token').unlink()
 for p in [state,*state.rglob('*')]:os.chown(p,account.pw_uid,account.pw_gid)
 for source in (ROOT/'web').glob('*.py'):shutil.copyfile(source,pathlib.Path('/opt/justverify/web')/source.name)
 (work/'web').mkdir();shutil.copytree(ROOT/'web/static',work/'web/static')
 for source in (ROOT/'web').glob('*.py'):shutil.copyfile(source,work/'web'/source.name)
 work.chmod(0o755)
 with socket.socket() as listener:listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
 log=(work/'server.log').open('wb')
 server=subprocess.Popen(['runuser','-u','justverify','--','/opt/justverify/venv/bin/python',str(work/'web/server.py'),'--state',str(state),'--binary','/opt/justverify/bin/justverify','--socket','/run/justverify/manager.sock','--origin',f'https://127.0.0.1:{port}','--port',str(port)],stdout=log,stderr=log)
 shutil.copyfile(ROOT/'target/release/justverify',work/'justverify');(work/'justverify').chmod(0o755)
 master,slave=pty.openpty();fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',40,120,0,0))
 process=subprocess.Popen(['runuser','-u','justverify','--',str(work/'justverify'),'tui','--socket','/run/justverify/manager.sock'],stdin=slave,stdout=slave,stderr=slave,env={**os.environ,'TERM':'xterm-256color'});os.close(slave)
 screen=pyte.Screen(120,40);stream=pyte.Stream(screen);decoder=codecs.getincrementaldecoder('utf-8')()
 def wait(text):
  end=time.monotonic()+20
  while time.monotonic()<end:
   assert process.poll() is None
   if select.select([master],[],[],.1)[0]:stream.feed(decoder.decode(os.read(master,65536)))
   if text in '\n'.join(screen.display):return '\n'.join(screen.display)
  raise AssertionError('expected client screen missing') # Never dump a credential popup.
 wait('JustVerify');os.write(master,b'c');wait('RPC CLIENTS');os.write(master,b'a');wait('Client name>');os.write(master,b'Phone test\r');text=wait('Password:')
 identifier=re.search(r'Username: ([a-f0-9]{32})',text).group(1);secret=re.search(r'Password: ([a-f0-9]{48})',text).group(1)
 if os.environ.get('JV_EXPECT_TOR_RPC')=='1':
  request=json.dumps({'id':identifier,'password':secret,'label':'Phone test'}).encode()
  expected=json.loads(subprocess.check_output(['/opt/justverify/venv/bin/python','-c','import json,sys;sys.path.insert(0,"/opt/justverify/web");from rpc_qr import quick_connect;print(json.dumps(quick_connect(json.load(sys.stdin))))'],input=request));assert expected['source_commit']=='d0d1502eef2840c0457aa321b88cf606ee8b4650'
  os.write(master,b'q');wait('FULLY NODED QUICK CONNECT');wait('▀');size=len(expected['matrix']);bits=[]
  while select.select([master],[],[],.1)[0]:stream.feed(decoder.decode(os.read(master,65536)))
  locations=[(y,min(xs),max(xs),{(screen.buffer[y][x].fg,screen.buffer[y][x].bg) for x in xs}) for y in range(40) if (xs:=[x for x in range(120) if screen.buffer[y][x].data in ('█','▀','▄')])]
  assert locations and locations[0][0]==7,str(locations)
  for y in range((size+1)//2):
   cells=[screen.buffer[5+y][1+x] for x in range(size)]
   assert all(c.fg in ('black','000000') and c.bg in ('white','brightwhite','ffffff') for c in cells),str({(c.fg,c.bg,c.data) for c in cells})
   bits.append([c.data in ('█','▀') for c in cells]);bits.append([c.data in ('█','▄') for c in cells])
  assert bits[:size]==expected['matrix']
  fcntl.ioctl(master,termios.TIOCSWINSZ,struct.pack('HHHH',24,80,0,0));screen.resize(24,80);wait('Enlarge the terminal')
  fcntl.ioctl(master,termios.TIOCSWINSZ,struct.pack('HHHH',40,120,0,0));screen.resize(40,120);wait('FULLY NODED QUICK CONNECT')
  os.write(master,b'\x1b');wait('Password:')
  print('PASS explicit sensitive Fully Noded QR renders exact black/white modules; narrow terminal refuses clipping',flush=True)
 context=ssl.create_default_context(cafile=str(state/'certificate.pem'));auth='Basic '+base64.b64encode((identifier+':'+secret).encode()).decode()
 def rpc():
  connection=http.client.HTTPSConnection('127.0.0.1',port,context=context,timeout=5);connection.request('POST','/rpc',json.dumps({'jsonrpc':'2.0','id':1,'method':'getblockchaininfo'}),{'Authorization':auth,'Content-Type':'application/json'});r=connection.getresponse();body=r.read();connection.close();return r.status,body
 status,body=rpc();assert status==200 and json.loads(body)['result']['chain']=='regtest'
 connection=http.client.HTTPSConnection('127.0.0.1',port,context=context,timeout=5);connection.request('POST','/',json.dumps({'jsonrpc':'1.0','id':'node-client','method':'getblockchaininfo','params':[]}),{'Authorization':auth,'Content-Type':'application/json'});response=connection.getresponse();assert response.status==200;assert json.loads(response.read())['result']['chain']=='regtest';connection.close()
 print('PASS authenticated Core JSON-RPC 1.0 root endpoint uses the same restricted gateway',flush=True)
 for method,authorization,expected in [('getblockchaininfo','',401),('createwallet',auth,403),('stop',auth,403)]:
  connection=http.client.HTTPSConnection('127.0.0.1',port,context=context,timeout=5);connection.request('POST','/',json.dumps({'jsonrpc':'1.0','id':1,'method':method,'params':[]}),{'Authorization':authorization,'Content-Type':'application/json'});response=connection.getresponse();assert response.status==expected;response.read();connection.close()
 connection=http.client.HTTPSConnection('127.0.0.1',port,context=context,timeout=5);connection.request('GET','/');response=connection.getresponse();assert response.status==200;response.read();connection.close()
 print('PASS root RPC denies anonymous/wallet/admin requests and preserves browser GET',flush=True)
 server.terminate();server.wait(timeout=5);server=subprocess.Popen(server.args,stdout=log,stderr=log)
 deadline=time.monotonic()+15
 while True:
  try:
   status,body=rpc();assert status==200 and json.loads(body)['result']['chain']=='regtest';break
  except OSError:
   assert server.poll() is None
   if time.monotonic()>deadline:raise
   time.sleep(.1)
 print('PASS persisted client authenticates after actual TLS server process restart',flush=True)
 assert secret not in (state/'rpc-clients.json').read_text()
 os.write(master,b'\x1b');visible=wait('A add');assert secret not in visible

 control=state/'remote-control.sock';assert control.exists() and stat.S_ISSOCK(control.stat().st_mode)
 assert stat.S_IMODE(control.stat().st_mode)==0o600 and control.stat().st_uid==account.pw_uid and stat.S_IMODE(state.stat().st_mode)==0o700
 refused=subprocess.run(['runuser','-u','nobody','--','python3','-c',f"import socket;s=socket.socket(socket.AF_UNIX);s.connect({str(control)!r})"],capture_output=True)
 assert refused.returncode!=0
 original_inode=control.stat().st_ino
 with socket.socket() as listener:listener.bind(('127.0.0.1',0));duplicate_port=listener.getsockname()[1]
 duplicate=subprocess.Popen(['runuser','-u','justverify','--','/opt/justverify/venv/bin/python',str(work/'web/server.py'),'--state',str(state),'--binary','/opt/justverify/bin/justverify','--socket','/run/justverify/manager.sock','--origin',f'https://127.0.0.1:{duplicate_port}','--port',str(duplicate_port)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 assert duplicate.wait(timeout=10)!=0 and control.stat().st_ino==original_inode
 print('PASS private 0700 state/0600 owner IPC socket rejects another uid and a duplicate server preserves the live socket',flush=True)

 def remote_closed():
  with socket.socket() as sock:return sock.connect_ex(('127.0.0.1',28443))!=0
 def remote_rpc():
  connection=http.client.HTTPConnection('127.0.0.1',28443,timeout=5);connection.request('POST','/',json.dumps({'jsonrpc':'2.0','id':2,'method':'getblockchaininfo'}),{'Authorization':auth,'Content-Type':'application/json'});response=connection.getresponse();body=response.read();connection.close();return response.status,body
 assert remote_closed();os.write(master,b'o');wait('REMOTE RPC');remote_screen=wait('Saved: false | Listener: false | Recovery: false')
 rpc_hostname=pathlib.Path('/run/justverify-tor/rpc.hostname')
 if rpc_hostname.exists():assert rpc_hostname.read_text().strip() in remote_screen
 os.write(master,b'e');wait('REVIEW: remote RPC ENABLE');os.write(master,b'\x1b');wait('E enable');assert remote_closed()
 os.write(master,b'e');wait('REVIEW: remote RPC ENABLE');os.write(master,b'incorrect-password\r');wait('Client request refused');assert remote_closed()
 os.write(master,b'e');wait('REVIEW: remote RPC ENABLE');os.write(master,admin_password.encode());masked=wait('Password> '+'*'*len(admin_password));assert admin_password not in masked
 os.write(master,b'\r');wait('Remote RPC setting applied.');status,body=remote_rpc();assert status==200 and json.loads(body)['result']['chain']=='regtest'
 if os.environ.get('JV_EXPECT_TOR_RPC')=='1':
  from onion_http import request as onion_request_once
  def onion_request(*args):
   deadline=time.monotonic()+90
   while True:
    try:return onion_request_once(*args)
    except OSError:
     if time.monotonic()>deadline:raise
     print('Tor circuit temporarily unavailable; retrying read-only test within deadline',flush=True)
     time.sleep(1)
  onion=rpc_hostname.read_text().strip()
  status,result=onion_request(onion,9050,'/rpc',{'jsonrpc':'2.0','id':3,'method':'getblockchaininfo','params':[]},auth);assert status==200 and result['result']['chain']=='regtest'
  assert onion_request(onion,9050,'/rpc',{'id':4,'method':'getblockcount'})[0]==401
  assert onion_request(onion,9050,'/login',{})[0]==404
  print('PASS product systemd Tor RPC onion reaches only the authenticated restricted gateway',flush=True)
 assert admin_password not in (state/'remote-rpc.json').read_text() and admin_password.encode() not in (work/'server.log').read_bytes()
 server.terminate();server.wait(timeout=5);assert remote_closed();server=subprocess.Popen(server.args,stdout=log,stderr=log)
 deadline=time.monotonic()+15
 while True:
  try:
   status,body=remote_rpc();assert status==200 and json.loads(body)['result']['chain']=='regtest';break
  except OSError:
   assert server.poll() is None
   if time.monotonic()>deadline:raise
   time.sleep(.1)
 os.write(master,b'l');wait('Saved: true | Listener: true | Recovery: false')
 os.write(master,b'd');wait('REVIEW: remote RPC DISABLE');os.write(master,admin_password.encode()+b'\r');wait('Remote RPC setting applied.');assert remote_closed()
 assert json.loads((state/'remote-rpc.json').read_text())=={'schema':1,'enabled':False,'phase':'committed'}
 os.write(master,b'\x1b');wait('A add')
 print('PASS actual non-root TUI cancel/wrong-password/masked reauthentication, Core RPC enable, process restore, and disable',flush=True)
 if os.environ.get('JV_EXPECT_WATCH_PROFILE')=='1':
  def wallet_query(method="getwalletinfo",params=None):
   c=http.client.HTTPSConnection('127.0.0.1',port,context=context,timeout=10);c.request('POST','/rpc',json.dumps({'jsonrpc':'2.0','id':8,'method':method,'params':[] if params is None else params}),{'Authorization':auth,'Content-Type':'application/json'});r=c.getresponse();body=r.read();c.close();return r.status,body
  assert wallet_query()[0]==403
  os.write(master,b'w');wait('GRANT WATCH-ONLY');os.write(master,b'\x1b');wait('A add');assert wallet_query()[0]==403
  os.write(master,b'w');wait('GRANT WATCH-ONLY');os.write(master,b'\r');wait('Wallet permission granted.')
  status,body=wallet_query();assert status==200 and json.loads(body)['result']['private_keys_enabled'] is False
  print('PASS actual PTY wallet grant review/cancel/confirm and authorized TLS watch-only wallet query',flush=True)
  assert wallet_query('createpsbt',[[],[{'data':'00'}]])[0]==403
  os.write(master,b't');wait('GRANT TRANSACTIONS');os.write(master,b'\x1b');wait('A add');assert wallet_query('createpsbt',[[],[{'data':'00'}]])[0]==403
  os.write(master,b't');wait('GRANT TRANSACTIONS');os.write(master,b'\r');wait('Transaction permission granted.');wait('watch-only + transactions')
  assert wallet_query('createpsbt',[[],[{'data':'00'}]])[0]==200
  print('PASS actual PTY separate transaction permission review/cancel/grant and TLS PSBT creation',flush=True)

 os.write(master,b'r');wait('REVOKE');os.write(master,b'\x1b');wait('A add');assert rpc()[0]==200
 os.write(master,b'r');wait('REVOKE');os.write(master,b'\r');wait('Client revoked');assert rpc()[0]==401
 assert secret.encode() not in (work/'server.log').read_bytes()
 os.write(master,b'\x03');assert process.wait(timeout=5)==0
 print('PASS actual non-root PTY issuance/one-time hide/revoke cancel/revoke; real TLS Core query then denial; no plaintext credential persisted or logged')
finally:
 if process and process.poll() is None:process.terminate();process.wait(timeout=5)
 if master is not None:os.close(master)
 if server:server.terminate();server.wait(timeout=5)
 state.rename(work/'test-web');(work/'original-web').rename(state);work.chmod(0o700)
 subprocess.run(['systemctl','start','justverify-web'],check=True)
 if tls_active:subprocess.run(['systemctl','start','justverify-electrum-tls'],check=True)
