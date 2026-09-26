#!/usr/bin/env python3
"""Resumable validation controller for the explicitly isolated public testnet4 VM."""
import json,pathlib,subprocess,time,urllib.request
from testnet4_vm_audit import guard,ROOT,EVIDENCE
STATE=EVIDENCE/'validation.json'
UNITS=['jv-testnet4-core','jv-testnet4-electrs','jv-testnet4-manager','jv-testnet4-rpc','jv-testnet4-mempool','jv-testnet4-mempool-web','jv-testnet4-observer']

def save(value):
    value['updated']=int(time.time());temporary=STATE.with_suffix('.tmp');temporary.write_text(json.dumps(value,indent=2)+'\n');temporary.chmod(0o600);temporary.replace(STATE)

def boot_id():return pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
def run(*args):subprocess.run(args,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=1000)
def evidence(name):return json.loads((EVIDENCE/name).read_text())
def ready():
    progress=evidence('progress.json');electrs=progress.get('electrs',{});core=progress['core']
    return time.time()-progress['time']<45 and not core['initialblockdownload'] and core['blocks']==core['headers'] and electrs.get('state')=='READY' and electrs.get('wallet_ready') and electrs.get('tip')==core['bestblockhash'] and len(progress.get('recent_blocks',[]))==6 and all(b.get('size') and not b.get('details_deferred') for b in progress['recent_blocks'])

def wait_checked(state,name):
    while time.time()<state['deadline']:
        guard()
        if ROOT.stat().st_dev==pathlib.Path('/').stat().st_dev:raise RuntimeError('Dedicated volume unavailable')
        try:
            if ready():
                result=subprocess.run(['runuser','-u','justverify','--','/usr/bin/python3','/usr/local/lib/jv-testnet4/testnet4_vm_audit.py','check'],capture_output=True,text=True,timeout=120)
                if result.returncode==0:
                    checked=json.loads(result.stdout)
                    with urllib.request.urlopen('http://127.0.0.1:19880/justverify/status',timeout=10) as response:mempool=json.load(response)
                    with urllib.request.urlopen('http://127.0.0.1:19880/api/blocks/tip/height',timeout=10) as response:height=int(response.read())
                    if mempool.get('state')=='running' and mempool.get('api_available') and height==checked['height']:
                        checked['mempool_tip_agrees']=True
                        for locale in ('en','ko','ja'):
                            with urllib.request.urlopen('http://127.0.0.1:19880/'+locale+'/',timeout=10) as response:assert b'<app-root' in response.read()
                        state['checks'][name]=checked;state.pop('last_check_error',None);save(state);return
                else:state['last_check_error']='Readiness or public-chain agreement checkpoint pending';save(state)
        except (OSError,ValueError,KeyError,subprocess.TimeoutExpired):pass
        time.sleep(15)
    raise TimeoutError('Public testnet4 validation deadline reached; checkpoints retained')

def main():
    guard()
    state=evidence('validation.json') if STATE.exists() else {'status':'RUNNING','stage':'initial_sync','started':int(time.time()),'deadline':int(time.time())+6*3600,'checks':{}}
    if state['status'] in ('PASS','BLOCKED'):return
    save(state)
    try:
        if state['stage']=='initial_sync':
            wait_checked(state,'fresh_ibd_and_index')
            state['db_identity']=(ROOT/'electrs/testnet4/IDENTITY').read_text().strip();state['first_index_pid']=state['checks']['fresh_ibd_and_index']['runtime']['pid']
            state['stage']='index_restart';state['restart_requested']=int(time.time());save(state)
            run('systemctl','restart','jv-testnet4-electrs')
        if state['stage']=='index_restart':
            # Require an observation from the restarted service, not cached READY.
            while time.time()<state['deadline']:
                try:
                    p=evidence('progress.json')
                    if p['time']>state['restart_requested'] and p.get('runtime',{}).get('pid')!=state['first_index_pid']:break
                except (OSError,ValueError,KeyError):pass
                time.sleep(5)
            wait_checked(state,'index_restart')
            assert (ROOT/'electrs/testnet4/IDENTITY').read_text().strip()==state['db_identity']
            state['stage']='core_restart';state['restart_requested']=int(time.time());save(state)
            run('systemctl','restart','jv-testnet4-core')
        if state['stage']=='core_restart':
            time.sleep(35)
            wait_checked(state,'core_restart')
            assert (ROOT/'electrs/testnet4/IDENTITY').read_text().strip()==state['db_identity']
            state['stage']='vm_reboot';state['previous_boot']=boot_id();save(state)
            run('systemctl','reboot');return
        if state['stage']=='vm_reboot':
            assert boot_id()!=state['previous_boot'],'VM reboot not observed'
            wait_checked(state,'vm_reboot')
            assert (ROOT/'electrs/testnet4/IDENTITY').read_text().strip()==state['db_identity']
            state['vm_reboot_observed']=True;state['status']='PASS';state['stage']='complete';state['finished']=int(time.time());state.pop('previous_boot',None);state.pop('db_identity',None);save(state)
    except Exception as error:
        state['status']='BLOCKED';state['error_type']=type(error).__name__;save(state)
        # The dedicated fixture is the only stop target. No production endpoints.
        for unit in UNITS:subprocess.run(['systemctl','stop',unit],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=1000)
        raise
if __name__=='__main__':main()
