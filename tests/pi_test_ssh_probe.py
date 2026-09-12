#!/usr/bin/env python3
"""Verify actual public-key root SSH on two private VM boots; never logs secrets."""
import json,pathlib,subprocess,time
ROOT=pathlib.Path(__file__).resolve().parents[1];state=ROOT/'.state/pi5-install'
remote='''import os,json,pathlib,subprocess,hashlib,sys
sys.path.insert(0,'/opt/justverify/scripts');import factory_volume
config=dict(line.split(' ',1) for line in subprocess.check_output(['/usr/sbin/sshd','-T'],text=True).splitlines())
assert os.getuid()==0 and config['passwordauthentication']=='no' and config['kbdinteractiveauthentication']=='no' and config['permitrootlogin'] in ('without-password','prohibit-password')
assert not pathlib.Path('/boot/firmware/justverify-owner.json').exists()
print(json.dumps({'uid':os.getuid(),'boot_id':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'host_public_key_sha256':hashlib.sha256(pathlib.Path('/etc/ssh/ssh_host_ed25519_key.pub').read_bytes()).hexdigest(),'password_authentication':config['passwordauthentication'],'headless_owner_file_consumed':True,'factory_volume':factory_volume.verify()}))
'''
records=[];deadline=time.monotonic()+240
while time.monotonic()<deadline and len(records)<2:
 result=subprocess.run(['ssh','-i',str(state/'id_ed25519'),'-p','22335','-o','IdentitiesOnly=yes','-o','BatchMode=yes','-o','PreferredAuthentications=publickey','-o','StrictHostKeyChecking=accept-new','-o','UserKnownHostsFile='+str(state/'vm_known_hosts'),'-o','ConnectTimeout=2','root@127.0.0.1','/usr/bin/python3 -'],input=remote,text=True,capture_output=True,timeout=15)
 if result.returncode==0:
  record=json.loads(result.stdout)
  if not records or record['boot_id']!=records[-1]['boot_id']:
   records.append(record);(state/'ssh-observations.json').write_text(json.dumps(records,indent=2)+'\n')
 time.sleep(1)
assert len(records)==2,'public-key SSH did not succeed on both boots'
assert records[0]['host_public_key_sha256']==records[1]['host_public_key_sha256'] and records[0]['factory_volume']==records[1]['factory_volume']
report={'status':'PASS','scope':'Actual root public-key SSH on two QEMU boots, password login disabled, generated host key and data UUID preserved; physical Pi NOT RUN','boots':records}
(ROOT/'docs/evidence/pi-test-image-ssh.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS root public-key SSH on two boots; no password login; host identity preserved')
