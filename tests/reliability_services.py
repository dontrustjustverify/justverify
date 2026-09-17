#!/usr/bin/env python3
"""Native systemd retry and failed-stop backup recovery in a disposable VM."""
import hashlib,importlib.util,json,os,pathlib,pwd,subprocess,sys,tempfile,time
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import backup_service
from backup_bundle import BackupBundle
assert os.geteuid()==0 and subprocess.check_output(['hostname'],text=True).strip()=='justverify-reset-test'
spec=importlib.util.spec_from_file_location('fixture',ROOT/'tests/backup_bundle.py');fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
def system(*args,check=True):return subprocess.run(['systemctl',*args],check=check,capture_output=True,text=True,timeout=60)
def wait(check,seconds):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        if check():return
        time.sleep(.5)
    raise TimeoutError('native service check')
assert system('show','justverify-i2p','-p','Result','--value').stdout.strip()=='exec-condition'
original_services=backup_service.SERVICES
backup_service.SERVICES=('justverify-i2p',)
backup_service.quiesce()
backup_service.SERVICES=original_services
print('PASS actual disabled I2P is a clean inactive state',flush=True)
with tempfile.TemporaryDirectory(prefix='jv-service-reliability-',dir='/var/tmp') as tmp:
    root=pathlib.Path(tmp);root.chmod(0o755)
    coreunit='jv-reliability-core.service';stopunit='jv-reliability-stop.service'
    units=[pathlib.Path('/run/systemd/system')/name for name in (coreunit,stopunit)]
    assert not any(p.exists() for p in units)
    data=root/'core';data.mkdir();account=pwd.getpwnam('justverify');os.chown(data,account.pw_uid,account.pw_gid)
    binary=pathlib.Path('/var/tmp/jv-mempool-public-tools/core')
    shipped=(ROOT/'image/systemd/justverify-core.service').read_text()
    settings={line.split('=',1)[0]:line.split('=',1)[1] for line in shipped.splitlines() if '=' in line}
    units[0].write_text(f'''[Unit]
StartLimitIntervalSec={settings['StartLimitIntervalSec']}
StartLimitBurst={settings['StartLimitBurst']}
[Service]
User=justverify
ExecStartPre=/usr/bin/test -f {root}/allow-start
ExecStart={binary}/bitcoind -regtest -datadir={data} -server=1 -listen=0 -connect=0 -rpcport=19743 -disablewallet=1 -dbcache=32
Restart={settings['Restart']}
RestartSec={settings['RestartSec']}
TimeoutStopSec={settings['TimeoutStopSec']}
''')
    units[1].write_text('[Service]\nExecStart=/usr/bin/sleep infinity\nExecStop=/usr/bin/false\nTimeoutStopSec=5\n')
    try:
        system('daemon-reload');system('start',coreunit,check=False)
        wait(lambda:int(system('show',coreunit,'-p','NRestarts','--value').stdout)>=4,150)
        (root/'allow-start').touch()
        def rpc_ready():
            result=subprocess.run([str(binary/'bitcoin-cli'),'-regtest','-datadir='+str(data),'-rpcport=19743','getblockchaininfo'],capture_output=True,text=True,timeout=3)
            return result.returncode==0 and json.loads(result.stdout)['chain']=='regtest'
        wait(rpc_ready,45)
        assert system('show',coreunit,'-p','Result','--value').stdout.strip()=='success'
        system('stop',coreunit)
        assert system('show',coreunit,'-p','Result','--value').stdout.strip()=='success'
        print('PASS shipped retry cadence survives four actual prestart failures and starts real regtest Core; clean shutdown',flush=True)
        folder=root/'backup';folder.mkdir()
        specs,cleanup,barriers,_=fixture.fixture(folder)
        bundle=BackupBundle(specs,folder/'backup-state',folder/'boot/justverify-backup.jvb',cleanup=cleanup,barriers=barriers)
        bundle.prepare_state();phrase='isolated recovery verification phrase';bundle.create(phrase)
        backup_service.SERVICES=(stopunit,)
        def resume():
            system('reset-failed',stopunit);system('start',stopunit)
        api=backup_service.BackupAPI(bundle,owner=specs[8].path,quiesce_callback=backup_service.quiesce,resume_callback=resume)
        system('start',stopunit)
        before={s.key:hashlib.sha256(s.path.read_bytes()).hexdigest() for s in specs if s.path.is_file()}
        archive=hashlib.sha256(bundle.destination.read_bytes()).hexdigest()
        for action in ('create_apply','restore_apply','recover'):
            request={'action':action,'password':fixture.OWNER_PASSWORD}
            if action=='create_apply':request.update(token=api.dispatch({'action':'create_preview'})['token'],passphrase=phrase)
            if action=='restore_apply':request.update(token=api.dispatch({'action':'restore_preview','passphrase':phrase,'password':fixture.OWNER_PASSWORD})['token'],passphrase=phrase,confirmation='RESTORE DEVICE IDENTITY')
            try:api.dispatch(request)
            except (RuntimeError,subprocess.CalledProcessError):pass
            else:raise AssertionError('failed stop accepted')
            assert system('is-active',stopunit).stdout.strip()=='active'
            assert {s.key:hashlib.sha256(s.path.read_bytes()).hexdigest() for s in specs if s.path.is_file()}==before
            assert hashlib.sha256(bundle.destination.read_bytes()).hexdigest()==archive
        print('PASS actual ExecStop failure: create/restore/recover reject writes and restart stopped services; real encrypted backup unchanged',flush=True)
    finally:
        system('stop',coreunit,stopunit,check=False)
        for path in units:path.unlink(missing_ok=True)
        system('daemon-reload');system('reset-failed',coreunit,stopunit,check=False)
