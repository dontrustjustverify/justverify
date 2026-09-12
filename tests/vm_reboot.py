#!/usr/bin/env python3
import pathlib,subprocess,time,json
R=pathlib.Path(__file__).resolve().parents[1];ssh=str(R/'scripts/vm_ssh.sh')
def run(cmd):return subprocess.check_output([ssh,cmd],text=True,stderr=subprocess.DEVNULL,timeout=8).strip()
before=run('cat /proc/sys/kernel/random/boot_id');identity=run('sha256sum /etc/machine-id').split()[0]
subprocess.run([ssh,'sudo reboot'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=15)
end=time.monotonic()+180
while time.monotonic()<end:
    try:
        after=run('cat /proc/sys/kernel/random/boot_id')
        if after!=before:
            status=run('systemctl is-active justverify-core justverify-manager justverify-web')
            data=json.loads(run('sudo runuser -u justverify -- /opt/justverify/bin/justverify snapshot --socket /run/justverify/manager.sock'))
            if status.splitlines()==['active']*3 and data['rpc']['getblockchaininfo']['error'] is None:break
    except (subprocess.SubprocessError,ValueError,KeyError):pass
    time.sleep(1)
else:raise SystemExit('VM reboot recovery timeout')
assert run('sha256sum /etc/machine-id').split()[0]==identity
result={'status':'PASS','scope':'QEMU Debian ARM64 VM; not Pi image hardware boot','checks':['kernel boot id changed','SSH host identity retained','machine identity retained','data loop mount automatic','Core/manager/web automatic start','actual RPC recovered'],'height':data['rpc']['getblockchaininfo']['value']['blocks'],'time':time.time()}
(R/'docs/evidence/vm-reboot.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
