#!/usr/bin/env python3
import socket,json,time,os,pwd,subprocess,pty,fcntl,termios,struct,select,codecs,pyte
assert pwd.getpwuid(os.geteuid()).pw_name=='justverify'
def api(request):
    with socket.socket(socket.AF_UNIX) as s:
        s.settimeout(2400 if request.get('method') in ('apply','recover') else 50);s.connect('/run/justverify-policy/control.sock');s.sendall((json.dumps(request)+'\n').encode());out=b''
        while block:=s.recv(65536):out+=block
    result=json.loads(out);assert result['ok'],result;return result['result']
def snapshot():
    with socket.socket(socket.AF_UNIX) as s:
        s.connect('/run/justverify/manager.sock');s.sendall(b'snapshot\n');out=b''
        while b:=s.recv(65536):out+=b
    return json.loads(out)
key=os.environ.get('JV_POLICY_TEST_KEY','maxmempool')
assert key in ('maxmempool','onlynet','proxy','listen','maxuploadtarget')
requested={'maxmempool':'422','onlynet':'ipv4','proxy':'1','listen':'none','maxuploadtarget':'11'}[key]
def observed():
    if key=='listen':
        try:
            with socket.create_connection(('127.0.0.1',18445),1):return True
        except OSError:return False
    data=snapshot()['rpc']
    if key=='maxuploadtarget':return data['getnettotals']['value']['uploadtarget']['target']
    if key=='maxmempool':return data['getmempoolinfo']['value']['maxmempool']
    networks={n['name']:n for n in data['getnetworkinfo']['value']['networks']}
    if key=='proxy':return networks['ipv4']['proxy']
    return [networks[n]['limited'] for n in ('ipv4','ipv6','onion')]
expected={'maxmempool':422000000,'onlynet':[False,True,True],'proxy':'127.0.0.1:9050','listen':False,'maxuploadtarget':11*1048576}[key]
state=api({'method':'state'});original=state['requested'];index=next(i for i,e in enumerate(state['entries']) if e['key']==key)
reset_default=os.environ.get('JV_POLICY_TEST_DEFAULT')=='1'
if reset_default:
    assert key in ('listen','onlynet')
    requested=state['entries'][index]['installation_default']
    custom={**original,key:'tor' if key=='listen' else 'ipv4'}
    prepared=api({'method':'preview','values':custom})
    assert api({'method':'apply','token':prepared['token']})['phase']=='committed'
    if key=='onlynet':
        # Core's Wants starts the condition again after the orderly stop.
        # With both I2P directions off, the correct final state is a skipped
        # ExecCondition, not the previous invocation's exit result.
        observed_unit=dict(line.split('=',1) for line in subprocess.check_output(['systemctl','show','justverify-i2p','-p','ActiveState,MainPID,ControlPID,Result'],text=True).splitlines())
        assert observed_unit=={'ActiveState':'inactive','MainPID':'0','ControlPID':'0','Result':'exec-condition'},observed_unit
    # The shared collector may still contain the pre-restart network snapshot.
    # Establish the actual custom baseline before checking that review/cancel
    # leave it unchanged; never compare a stale baseline with a fresh result.
    baseline=True if key=='listen' else [False,True,True]
    deadline=time.monotonic()+12
    while time.monotonic()<deadline:
        if snapshot()['rpc']['getnetworkinfo']['error'] is None and observed()==baseline:break
        time.sleep(.2)
    else:raise AssertionError('custom baseline not collected')
    assert api({'method':'state'})['requested']==custom
    expected=False if key=='listen' else [False,False,False]

master,slave=pty.openpty();fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',40,120,0,0))
p=subprocess.Popen(['/opt/justverify/bin/justverify','tui','--socket','/run/justverify/manager.sock'],stdin=slave,stdout=slave,stderr=slave,env={**os.environ,'TERM':'xterm-256color'});os.close(slave)
screen=pyte.Screen(120,40);terminal_stream=pyte.Stream(screen);decoder=codecs.getincrementaldecoder("utf-8")()
def read_until(text,seconds=12):
    out=b'';deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        if select.select([master],[],[],.1)[0]:
            chunk=os.read(master,65536);out+=chunk;terminal_stream.feed(decoder.decode(chunk))
        if text.decode() in '\n'.join(screen.display):return out
    raise AssertionError('TUI state text not observed: '+text.decode()+'\n'+ '\n'.join(screen.display))
try:
    read_until(b'JustVerify');os.write(master,b'm');read_until(b'MEMPOOL / RELAY')
    if reset_default:
        os.write(master,b'\x1b[B'*index+b'd');read_until(b'JustVerify default staged')
    else:
        os.write(master,b'\x1b[B'*index+b'\r');read_until(b'VALUE>')
        os.write(master,b'\x7f'*len(original.get(key,''))+requested.encode()+b'\r');read_until(b'Staged;')
    before=observed()
    os.write(master,b'a');read_until(b'REVIEW POLICY CHANGE',25);assert observed()==before
    if reset_default:assert api({'method':'state'})['requested']==custom
    os.write(master,b'\x1b');read_until(b'MEMPOOL / RELAY');assert observed()==before
    if reset_default:assert api({'method':'state'})['requested']==custom
    os.write(master,b'a');read_until(b'REVIEW POLICY CHANGE',25);os.write(master,b'\r');read_until(b'committed',45)
    deadline=time.monotonic()+10
    while time.monotonic()<deadline:
        value=snapshot()['rpc']['getmempoolinfo' if key=='maxmempool' else 'getnetworkinfo']
        if value['error'] is None and observed()==expected:break
        time.sleep(.2)
    else:raise AssertionError('applied value not collected')
    assert api({'method':'state'})['requested'][key]==requested
    os.write(master,b'\x03');p.wait(timeout=5)
    print(json.dumps({'status':'PASS','key':key,'default_reset':reset_default,'platform':'actual Linux PTY 120x40 as justverify','checks':['M policy navigation','D stages installation default' if reset_default else 'keyboard field editing','real preflight and diff','Escape does not apply changes','Enter applies via restricted API','actual Core value observed','Ctrl-C exits fixed TUI']},indent=2))
finally:
    if p.poll() is None:p.terminate();p.wait(timeout=5)
    os.close(master)
    preview=api({'method':'preview','values':original});restore=api({'method':'apply','token':preview['token']});assert restore['phase']=='committed',restore
