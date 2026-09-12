#!/usr/bin/env python3
"""Real isolated Core, collector and PTY. No fixture RPC responses or production funds."""
import codecs,fcntl,json,os,pathlib,pty,select,socket,struct,subprocess,tempfile,termios,time
import pyte,signal
R=pathlib.Path(__file__).resolve().parents[1]
B=R/'.cache/core/31.1/arm64-apple-darwin/bitcoin-31.1/bin'
with socket.socket() as reserve:
 reserve.bind(('127.0.0.1',0));rpcport=reserve.getsockname()[1]
E=R/'.state/ui-reference';E.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory(prefix='jv-dashboard-') as tmp:
 d=pathlib.Path(tmp);os.chmod(d,0o700)
 core=daemon=tui=None
 def cli(*args):return subprocess.check_output([str(B/'bitcoin-cli'),'-regtest',f'-datadir={d}',f'-rpcport={rpcport}','-rpcwait',*args],text=True).strip()
 try:
  core=subprocess.Popen([str(B/'bitcoind'),'-regtest',f'-datadir={d}',f'-rpcport={rpcport}','-listen=0','-networkactive=0','-server=1'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  for _ in range(100):
   if (d/'regtest/.cookie').exists():break
   time.sleep(.1)
  cli('createwallet','ui-test');addr=cli('getnewaddress');cli('generatetoaddress','8',addr)
  daemon=subprocess.Popen([str(R/'target/debug/justverify'),'daemon','--cookie',str(d/'regtest/.cookie'),'--rpc-port',str(rpcport),'--socket',str(d/'manager.sock')],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  def snapshot():
   with socket.socket(socket.AF_UNIX) as c:
    c.connect(str(d/'manager.sock'));c.sendall(b'snapshot\n');out=b''
    while x:=c.recv(65536):out+=x
   return json.loads(out)
  def await_tip(tip):
   for _ in range(100):
    try:
     s=snapshot();blocks=s['rpc']['recentblocks']['value']
     if blocks and blocks[0]['hash']==tip and not s['rpc']['recentblocks']['error']:return s
    except (OSError,KeyError,TypeError):pass
    time.sleep(.2)
   raise AssertionError('collector tip timeout')
  s=await_tip(cli('getbestblockhash'));assert len(s['rpc']['recentblocks']['value'])==6
  for a,b in zip(s['rpc']['recentblocks']['value'],s['rpc']['recentblocks']['value'][1:]):assert a['previousblockhash']==b['hash']
  old=cli('getbestblockhash');cli('invalidateblock',old);cli('generatetoaddress','2',cli('getnewaddress'));s=await_tip(cli('getbestblockhash'));assert old not in [b['hash'] for b in s['rpc']['recentblocks']['value']]
  master,slave=pty.openpty();fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',40,120,0,0))
  tui=subprocess.Popen([str(R/'target/debug/justverify'),'tui','--socket',str(d/'manager.sock')],stdin=slave,stdout=slave,stderr=slave,env={**os.environ,'TERM':'xterm-256color'});os.close(slave)
  screen=pyte.Screen(120,40);stream=pyte.Stream(screen);decoder=codecs.getincrementaldecoder('utf-8')()
  def visible():
   # pyte 0.8.2 display crashes on wide-character continuation cells after erasure.
   # Read its actual cells, retaining empty CJK continuation cells without indexing them.
   return '\n'.join(''.join(screen.buffer[y][x].data for x in range(screen.columns)) for y in range(screen.lines))
  def wait(label):
   for _ in range(100):
    if select.select([master],[],[],.1)[0]:stream.feed(decoder.decode(os.read(master,65536)))
    if label in visible():return
   raise AssertionError(label+'\n'+visible())
  wait('최근 블록');wait('#9');wait('Esc 현황');(E/'desktop.txt').write_text(visible())
  os.write(master,b'\x1bOS');wait('비트코인코어 / 피어')
  os.write(master,b'\x1b[17~');wait('기기 설정');wait('백업')
  os.write(master,b'\x1bOP');wait('Esc 현황')
  for cols,rows,name in [(80,24,'compact'),(42,24,'mobile')]:
   screen=pyte.Screen(cols,rows);stream=pyte.Stream(screen);fcntl.ioctl(master,termios.TIOCSWINSZ,struct.pack('HHHH',rows,cols,0,0));os.kill(tui.pid,signal.SIGWINCH);time.sleep(2.2);wait('노드 요약');wait('네트워크 · Mempool');wait('최근 블록');wait('S 설정' if cols<65 else '기기 설정');(E/f'{name}.txt').write_text(visible())
  cli('stop');core.wait(timeout=10)
  for _ in range(100):
   stale=snapshot()
   if stale['rpc']['recentblocks']['error']:break
   time.sleep(.2)
  assert stale['rpc']['recentblocks']['error'];wait('연결 안 됨')
  os.write(master,b'\x03');assert tui.wait(timeout=5)==0
  (E/'live-result.json').write_text(json.dumps({'core':'31.1','network':'isolated regtest','height':s['rpc']['getblockchaininfo']['value']['blocks'],'tip':s['rpc']['recentblocks']['value'][0]['hash'],'results':['linked six headers','new block refresh','invalidated tip removed after reorg','desktop/compact/mobile PTY','global menu navigation','Core stop stale flag']},indent=2))
  print('PASS real Core31.1: recent blocks, reorg, PTY120/80/42 columns, navigation, stop/stale')
 finally:
  for p in [tui,daemon,core]:
   if p and p.poll() is None:p.terminate();p.wait(timeout=10)
