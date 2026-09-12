#!/usr/bin/env python3
"""Real isolated Core -> daemon -> TUI PTY -> stop/stale/restart integration."""
import json, os, pathlib, subprocess, time, socket, signal, pty, select, fcntl, struct, termios, hashlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
version='31.1'
bin=ROOT/f'.cache/core/{version}/arm64-apple-darwin/bitcoin-{version}/bin'
state=ROOT/'.state/smoke';state.mkdir(parents=True,exist_ok=True);state.chmod(0o700)
data=state/'core';data.mkdir(exist_ok=True)
sock=state/'manager.sock'
if sock.exists(): raise SystemExit('Existing socket; inspect prior smoke process before retry')
args=[str(bin/'bitcoind'),f'-datadir={data}','-regtest','-server','-listen=0','-dnsseed=0','-connect=0','-rpcport=19443','-disablewallet','-printtoconsole=0']
processes=[]
def start():
    p=subprocess.Popen(args,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE);processes.append(p)
    for _ in range(100):
        r=subprocess.run([str(bin/'bitcoin-cli'),f'-datadir={data}','-regtest','-rpcport=19443','getblockchaininfo'],capture_output=True)
        if r.returncode==0:return p
        if p.poll() is not None:raise RuntimeError(p.stderr.read().decode())
        time.sleep(.1)
    raise RuntimeError('Core startup timeout')
def cli(*a):return subprocess.check_output([str(bin/'bitcoin-cli'),f'-datadir={data}','-regtest','-rpcport=19443',*a],text=True).strip()
def snapshot():
    with socket.socket(socket.AF_UNIX) as s:
        s.connect(str(sock));s.sendall(b'snapshot\n');out=b''
        while chunk:=s.recv(65536):out+=chunk
    return json.loads(out)
def wait(predicate):
    for _ in range(80):
        try:
            s=snapshot()
            if predicate(s):return s
        except (FileNotFoundError,ConnectionRefusedError,KeyError):pass
        time.sleep(.2)
    raise RuntimeError('Snapshot assertion timed out')
try:
    core=start()
    # Mine without enabling a private-key wallet: raw OP_TRUE descriptor.
    descriptor=json.loads(cli('getdescriptorinfo','raw(51)'))['descriptor']
    cli('generatetodescriptor','3',descriptor)
    height=int(cli('getblockcount'))
    daemon=subprocess.Popen([str(ROOT/'target/debug/justverify'),'daemon','--cookie',str(data/'regtest/.cookie'),'--rpc-port','19443','--socket',str(sock)],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE);processes.append(daemon)
    initial=wait(lambda s:s['rpc']['getblockchaininfo']['value']['blocks']==height)
    master,slave=pty.openpty();fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',40,120,0,0))
    tui=subprocess.Popen([str(ROOT/'target/debug/justverify'),'tui','--socket',str(sock)],stdin=slave,stdout=slave,stderr=slave,env={**os.environ,'TERM':'xterm-256color'});processes.append(tui);os.close(slave)
    output=b'';deadline=time.time()+4
    while time.time()<deadline:
        if select.select([master],[],[],.2)[0]:output+=os.read(master,65536)
    assert b'JustVerify' in output and b'CHAIN' in output and b'MEMPOOL' in output
    os.write(master,b'\x03');tui.wait(timeout=5);os.close(master)
    cli('stop');core.wait(timeout=10)
    stale=wait(lambda s:s['rpc']['getblockchaininfo']['error'] is not None)
    assert stale['rpc']['getblockchaininfo']['value']['blocks']==height
    core=start()
    recovered=wait(lambda s:s['rpc']['getblockchaininfo']['error'] is None)
    assert recovered['rpc']['getblockchaininfo']['value']['blocks']==height
    secret=(data/'regtest/.cookie').read_text().strip()
    assert secret not in json.dumps(recovered) and secret.encode() not in output
    report={'status':'PASS','core':version,'platform':os.uname().sysname+' '+os.uname().machine,'time':time.time(),'height':height,'checks':['actual Core RPC','wallet disabled mining','shared daemon snapshot','120x40 actual PTY TUI','Core stop stale preserving last value','Core restart recovery','no cookie in API or TUI'],'binary_sha256':hashlib.sha256((ROOT/'target/debug/justverify').read_bytes()).hexdigest()}
    (ROOT/'docs/evidence/regtest-smoke.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
finally:
    for p in reversed(processes):
        if p.poll() is None:
            p.terminate()
            try:p.wait(timeout=15)
            except subprocess.TimeoutExpired:p.kill();p.wait()
    sock.unlink(missing_ok=True)
