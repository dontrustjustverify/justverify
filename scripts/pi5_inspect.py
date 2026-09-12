#!/usr/bin/env python3
"""Read-only first contact with the user-specified Pi5; no setup/restart/data mutation."""
import argparse,ipaddress,json,pathlib,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('ip');a=p.parse_args();address=ipaddress.ip_address(a.ip)
if not address.is_private or address.is_loopback or address.is_multicast:raise SystemExit('Use the Pi LAN IP address supplied by the owner')
state=ROOT/'.state/pi5-install'
remote='''import hashlib,json,pathlib,subprocess,sys
sys.path.insert(0,'/opt/justverify/scripts');import factory_volume
out={}
def command(name,args):
 try:out[name]=subprocess.check_output(args,stderr=subprocess.DEVNULL,text=True,timeout=15).strip()
 except (OSError,subprocess.SubprocessError):out[name]=None
model=pathlib.Path('/proc/device-tree/model')
out['model']=model.read_bytes().rstrip(b'\\0').decode() if model.exists() else None
out['is_raspberry_pi_5']=bool(out['model'] and out['model'].startswith('Raspberry Pi 5'))
out['application_sha256']=hashlib.sha256(pathlib.Path('/opt/justverify/bin/justverify').read_bytes()).hexdigest()
out['data_volume']=factory_volume.verify()
command('disks',['lsblk','-J','-b','-o','NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS,MODEL'])
command('memory',['free','-b'])
command('clock',['timedatectl','show','-p','NTPSynchronized','-p','Timezone'])
command('failed_units',['systemctl','--failed','--no-pager','--plain'])
command('firstboot',['systemctl','show','justverify-firstboot','-p','ActiveState','-p','SubState','-p','Result'])
command('ssh',['systemctl','show','ssh','-p','ActiveState'])
command('bootloader',['vcgencmd','bootloader_version'])
command('temperature',['vcgencmd','measure_temp'])
command('throttled',['vcgencmd','get_throttled'])
out['owner_enrolled']=pathlib.Path('/var/lib/justverify/web/admin.json').exists()
out['scope']='read-only first hardware contact; no claim of complete node synchronization'
print(json.dumps(out))
'''
result=subprocess.run(['ssh','-i',str(state/'id_ed25519'),'-o','IdentitiesOnly=yes','-o','BatchMode=yes','-o','StrictHostKeyChecking=accept-new','-o','UserKnownHostsFile='+str(state/'pi_known_hosts'),'-o','ConnectTimeout=10','root@'+str(address),'/usr/bin/python3 -'],input=remote,text=True,capture_output=True,timeout=120)
if result.returncode:raise SystemExit('SSH inspection failed; preserve media and check IP, power and firstboot status')
report=json.loads(result.stdout);(state/'hardware-first-contact.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'report':str(state/'hardware-first-contact.json'),'is_raspberry_pi_5':report['is_raspberry_pi_5'],'scope':report['scope']}))
