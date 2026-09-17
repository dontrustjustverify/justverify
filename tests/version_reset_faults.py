#!/usr/bin/env python3
"""Fault/reboot phases for the actual disposable-VM API, never for a Pi."""
from version_reset_native import *
import threading,sys
ROOT=pathlib.Path('/var/tmp/jv-reset-native')
def system(*args,check=True):return subprocess.run(['systemctl',*args],check=check,capture_output=True,text=True)
def wait(predicate,seconds=60):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  try:
   result=predicate()
   if result:return result
  except (OSError,ValueError,KeyError,AssertionError):pass
  time.sleep(.05)
 raise AssertionError('fixture checkpoint timeout')
def journal():return json.loads((STATE/'transition.json').read_text())
def core_path():return pathlib.Path(json.loads((STATE/'active.json').read_text())['instance']['core_data'])
def config_binding():
 p=preview('22.0');path=pathlib.Path('/etc/justverify/torrc');saved=path.read_bytes();path.write_bytes(saved+b'\n# fixture binding change\n')
 try:assert not api('apply',token=p['token'])['ok']
 finally:path.write_bytes(saved)
 assert journal()['phase']=='committed'
 print('PASS changed privileged configuration invalidates review',flush=True)
def stop_failure():
 core=core_path();old=(core/'regtest/blocks/blk00000.dat').read_bytes()
 p=preview('22.0');fault=pathlib.Path('/etc/systemd/system/justverify-core.service.d/50-reset-fault.conf')
 fault.write_text('[Service]\nExecStop=/usr/bin/sleep 30\nTimeoutStopSec=1\n')
 system('daemon-reload');result=apply(p)
 assert result['phase']=='stop_failed',result
 assert (core/'regtest/blocks/blk00000.dat').read_bytes()==old
 assert not journal()['deletion_started']
 fault.unlink();system('daemon-reload');system('reset-failed','justverify-core')
 assert okay('recover')['phase']=='rolled_back'
 assert rpc('getnetworkinfo')['version']==310100
 print('PASS real systemd stop timeout: no deletion; existing runtime restored',flush=True)
def interrupt_reset():
 core=core_path();blocks=core/'regtest/blocks'
 # Extra allowlisted block-file slots make a partial filesystem reset observable;
 # the authoritative chain/index is still from the real regtest Core process.
 for n in range(10000,13000):(blocks/f'blk{n:05}.dat').write_bytes(b'fault-window')
 p=preview('22.0');out=[]
 def apply_thread():
  try:out.append(apply(p))
  except Exception:out.append('connection interrupted')
 thread=threading.Thread(target=apply_thread);thread.start()
 wait(lambda:journal()['phase']=='resetting')
 wait(lambda:not (blocks/'blk10000.dat').exists())
 system('kill','--signal=SIGKILL','justverify-versions')
 thread.join(timeout=15);assert not thread.is_alive()
 remaining=len(list(blocks.glob('blk1????.dat')))
 assert 0<remaining<3000,remaining
 assert journal()['deletion_started'] and journal()['phase']=='resetting'
 wait(lambda:okay('state')['transition']['needs_recovery'])
 verify_interrupted()
def verify_interrupted():
 assert journal()['deletion_started'] and journal()['phase']=='resetting'
 remaining=len(list((core_path()/'regtest/blocks').glob('blk1????.dat')))
 assert 0<remaining<3000,remaining
 system('reset-failed','justverify-core');system('start','justverify-core',check=False)
 assert system('show','justverify-core','-p','MainPID','--value').stdout.strip()=='0'
 legitimate=(STATE/'transition.json').read_bytes()
 try:
  tampered=json.loads(legitimate)
  for phase in ('rolled_back','committed'):
   tampered['phase']=phase;tampered['deletion_started']=False
   (STATE/'transition.json').write_text(json.dumps(tampered))
   release=subprocess.run(['/usr/libexec/justverify-profile'],input=json.dumps({'action':'release'}),capture_output=True,text=True)
   assert release.returncode!=0 and pathlib.Path('/etc/justverify/version-reset-guard.json').exists()
  tampered['phase']='starting';tampered['deletion_started']=True
  (STATE/'transition.json').write_text(json.dumps(tampered))
  gate=subprocess.run(['python3','/opt/justverify/scripts/node_ready.py'],capture_output=True)
  assert gate.returncode!=0
 finally:(STATE/'transition.json').write_bytes(legitimate)
 print('PASS root irreversible/completion checks reject forged rollback, commit and premature start journal',flush=True)
 (ROOT/'interrupted.json').write_text(json.dumps({'remaining':remaining,'version_before':'31.1','target':'22.0'}))
 print('PASS actual daemon/worker SIGKILL during partial deletion; Core startup blocked. READY_FOR_REBOOT',flush=True)
def after_reboot():
 assert (ROOT/'interrupted.json').exists()
 assert journal()['phase']=='resetting' and journal()['deletion_started']
 assert system('show','justverify-core','-p','MainPID','--value').stdout.strip()=='0'
 assert pathlib.Path('/etc/justverify/version-reset-guard.json').exists()
 system('reset-failed','justverify-core','justverify-electrs','justverify-policy')
 subprocess.run(['/opt/justverify-tests/bin/python','-c','from pty_version_recovery import recover_missing_target; recover_missing_target()'],env={**os.environ,'PYTHONPATH':str(pathlib.Path(__file__).parent)},check=True)
 assert journal()['phase']=='committed'
 assert rpc('getnetworkinfo')['version']==220000 and rpc('getblockcount')==0
 assert not (core_path()/'regtest/blocks/blk10001.dat').exists()
 assert (core_path()/'auth-fixture').read_text()=='preserve-fixture'
 print('PASS actual reboot preserves start inhibition; recovery resets only reviewed scope and starts target genesis',flush=True)
def target_failure():
 p=preview('31.1');fault=pathlib.Path('/etc/systemd/system/justverify-core.service.d/50-reset-fault.conf')
 fault.write_text('[Service]\nExecStartPre=/usr/bin/false\n');system('daemon-reload')
 result=apply(p);assert result['phase']=='target_start_failed',result
 assert json.loads((STATE/'active.json').read_text())['instance']['core_version']=='31.1'
 assert journal()['deletion_started']
 fault.unlink();system('daemon-reload');system('reset-failed','justverify-core','justverify-electrs','justverify-policy')
 result=okay('recover');assert result['phase']=='committed',result
 assert rpc('getnetworkinfo')['version']==310100
 print('PASS native target start failure retains target and guard; explicit recovery retries target',flush=True)
if __name__=='__main__':
 if sys.argv[1:] == ['before-reboot']:config_binding();stop_failure();interrupt_reset()
 elif sys.argv[1:] == ['after-reboot']:after_reboot();target_failure()
 elif sys.argv[1:] == ['verify-interrupted']:verify_interrupted()
 else:raise SystemExit('explicit fault-test phase required')
