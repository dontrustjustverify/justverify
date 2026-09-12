#!/usr/bin/env python3
"""Real service crash between durable config write and Core restart, then TUI recovery."""
import codecs, fcntl, json, os, pty, pwd, select, signal, socket, struct, subprocess, termios, threading, time
import pyte
assert os.geteuid() == 0 and socket.gethostname() == 'justverify-dev'

def api(value):
    with socket.socket(socket.AF_UNIX) as sock:
        sock.settimeout(50)
        sock.connect('/run/justverify-policy/control.sock')
        sock.sendall((json.dumps(value)+'\n').encode())
        data = b''
        while part := sock.recv(65536): data += part
    reply = json.loads(data)
    assert reply['ok'], reply
    return reply['result']

def wait(predicate, seconds=25):
    deadline = time.monotonic()+seconds
    while time.monotonic()<deadline:
        try:
            result = predicate()
            if result: return result
        except (OSError, ValueError): pass
        time.sleep(.1)
    raise AssertionError('bounded wait timed out')

def control(*args):
    return subprocess.check_output(['systemctl', *args], text=True).strip()

original = wait(lambda: api({'method':'state'}))['requested']
preview = api({'method':'preview','values':{**original, 'maxmempool':'423'}})
core_pid = int(control('show','-p','MainPID','--value','justverify-core'))
worker_result = []
def apply_worker():
    try: worker_result.append(api({'method':'apply','token':preview['token']}))
    except Exception as error: worker_result.append(type(error).__name__)
process = None
master = None
try:
    os.kill(core_pid, signal.SIGSTOP)
    thread = threading.Thread(target=apply_worker)
    thread.start()
    journal_path = '/var/lib/justverify/config/managed.transaction.json'
    wait(lambda: json.load(open(journal_path))['phase'] == 'restarting', 10)
    control('kill','--kill-whom=main','--signal=KILL','justverify-policy')
    os.kill(core_pid, signal.SIGCONT)
    thread.join(10)
    assert not thread.is_alive()
    state = wait(lambda: api({'method':'state'}))
    assert state['transaction']['needs_recovery'] is True
    assert state['requested']['maxmempool'] == '423'
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH',40,120,0,0))
    process = subprocess.Popen(['runuser','-u','justverify','--','/opt/justverify/bin/justverify','tui','--socket','/run/justverify/manager.sock'],stdin=slave,stdout=slave,stderr=slave,env={**os.environ,'TERM':'xterm-256color'})
    os.close(slave)
    screen = pyte.Screen(120,40)
    stream = pyte.Stream(screen)
    decoder = codecs.getincrementaldecoder('utf-8')()
    def visible(text):
        assert process.poll() is None, 'TUI exited before expected screen'
        if select.select([master],[],[],.1)[0]: stream.feed(decoder.decode(os.read(master,65536)))
        return text in '\n'.join(screen.display)
    wait(lambda: visible('JustVerify'))
    os.write(master,b'm')
    wait(lambda: visible('INTERRUPTED CHANGE'))
    os.write(master,b'r')
    wait(lambda: visible('RECOVER INTERRUPTED POLICY CHANGE'))
    os.write(master,b'\x1b')
    wait(lambda: visible('MEMPOOL / RELAY'))
    assert api({'method':'state'})['transaction']['needs_recovery'] is True
    os.write(master,b'r')
    wait(lambda: visible('RECOVER INTERRUPTED POLICY CHANGE'))
    os.write(master,b'\r')
    wait(lambda: visible('rolled_back'),45)
    state = api({'method':'state'})
    assert state['requested'] == original and state['transaction']['needs_recovery'] is False
    os.write(master,b'\x03')
    process.wait(timeout=5)
    print(json.dumps({'status':'PASS','checks':['actual Core paused during restart','actual policy service SIGKILL after durable save','systemd automatically restarts policy service','TUI displays unfinished transaction','recovery Escape preserves transaction','confirmed TUI recovery restores prior settings and healthy Core']},indent=2))
finally:
    try: os.kill(core_pid,signal.SIGCONT)
    except ProcessLookupError: pass
    if process is not None and process.poll() is None: process.terminate(); process.wait(timeout=5)
    if master is not None: os.close(master)
    state = wait(lambda: api({'method':'state'}))
    if state['transaction']['needs_recovery']: api({'method':'recover'})
    if api({'method':'state'})['requested'] != original:
        ready=api({'method':'preview','values':original})
        assert api({'method':'apply','token':ready['token']})['phase']=='committed'
