#!/usr/bin/env python3
"""Destructive tests only within explicitly created disposable VM virtual data FS."""
import subprocess,json,time,pathlib,os
assert os.geteuid()==0 and subprocess.check_output(['hostname'],text=True).strip()=='justverify-dev'
D=pathlib.Path('/srv/justverify/data');report=[]
def command(*args,check=True):return subprocess.run(args,capture_output=True,text=True,check=check)
def system(action,*units,check=True):return command('systemctl',action,*units,check=check)
def snap():
    return json.loads(command('runuser','-u','justverify','--','/opt/justverify/bin/justverify','snapshot','--socket','/run/justverify/manager.sock').stdout)
def wait(f,seconds=30):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        try:
            if f():return
        except (subprocess.CalledProcessError,ValueError,KeyError):pass
        time.sleep(.25)
    raise AssertionError('State transition timeout')
def healthy():return snap()['rpc']['getblockchaininfo']['error'] is None
system('start','justverify-core','justverify-manager','justverify-web');wait(healthy);before=snap()['rpc']['getblockchaininfo']['value']['blocks'];report.append('all services start with real regtest RPC')
for service in ['justverify-manager','justverify-web']:
    system('restart',service);wait(healthy);assert system('is-active',service).stdout.strip()=='active'
report.append('manager/web restart')
system('stop','justverify-core');wait(lambda:snap()['rpc']['getblockchaininfo']['error'] is not None)
assert snap()['rpc']['getblockchaininfo']['value']['blocks']==before
system('start','justverify-core');wait(healthy);report.append('Core stop stale, start recovery')
# Mount loss: no writes may fall through onto the system disk.
system('stop','justverify-core','justverify-manager');system('stop','srv-justverify-data.mount')
backing=pathlib.Path('/var/lib/justverify-dev-data.img');missing=backing.with_suffix('.img.unavailable');assert not missing.exists();backing.rename(missing)
try:
    system('start','justverify-core',check=False)
    assert system('is-active','justverify-core',check=False).stdout.strip()!='active'
    assert not (D/'core').exists(),'Core wrote onto unmounted system path'
    report.append('missing mount blocks Core and prevents system disk writes')
finally:
    missing.rename(backing);system('reset-failed','srv-justverify-data.mount','justverify-core',check=False);system('start','srv-justverify-data.mount');system('start','justverify-core','justverify-manager');wait(healthy)
# Disk full in this VM-only loop-mounted filesystem; preserve enough for fs bookkeeping.
assert '/var/lib/justverify-dev-data.img' in pathlib.Path('/etc/fstab').read_text()
system('stop','justverify-core');filler=D/'.jv-disk-full-test'
fd=os.open(filler,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
try:
    free=os.statvfs(D).f_bavail*os.statvfs(D).f_frsize
    os.posix_fallocate(fd,0,free-50*1024*1024);os.close(fd);fd=None
    system('start','justverify-core',check=False)
    wait(lambda:system('is-active','justverify-core',check=False).stdout.strip()!='active',seconds=20)
    system('stop','justverify-core')
    journal=command('journalctl','-u','justverify-core','-n','80','--no-pager').stdout.lower()
    assert 'disk space' in journal and 'low' in journal
    report.append('low disk space rejects startup with explicit diagnostic')
finally:
    if fd is not None:os.close(fd)
    filler.unlink(missing_ok=True);system('reset-failed','justverify-core',check=False);system('start','justverify-core');wait(healthy)
assert snap()['rpc']['getblockchaininfo']['value']['blocks']==before
report.append('disk recovery preserves regtest height')
result={'status':'PASS','time':time.time(),'platform':'Debian ARM64 QEMU VM','checks':report,'not_run':['Pi hardware','OS update rollback','electrs recovery','24h soak']}
pathlib.Path('/home/builder/justverify/linux-services-result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
