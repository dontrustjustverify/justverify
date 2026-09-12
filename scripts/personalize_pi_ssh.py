#!/usr/bin/env python3
"""Create a private image clone with the explicitly selected owner's SSH public key."""
import argparse,hashlib,json,os,pathlib,subprocess,tempfile
from build_single_disk import loop,mount,run
p=argparse.ArgumentParser();p.add_argument('--source',type=pathlib.Path,required=True);p.add_argument('--sha256',required=True);p.add_argument('--output',type=pathlib.Path,required=True);p.add_argument('--public-key',type=pathlib.Path,required=True);a=p.parse_args()
assert os.geteuid()==0 and a.source.is_file() and not a.source.is_symlink()
assert a.output.is_absolute() and a.output.parent.name=='.state' and a.output.suffix=='.img' and not a.output.exists() and not a.output.is_symlink()
assert hashlib.file_digest(a.source.open('rb'),'sha256').hexdigest()==a.sha256
key=a.public_key.read_text().strip();assert key.startswith('ssh-ed25519 ') and '\n' not in key and len(key)<512
run(['/usr/bin/ssh-keygen','-l','-f',str(a.public_key)])
with a.output.open('xb') as out:
 a.output.chmod(0o600)
 unzip=subprocess.Popen(['xz','-dc',str(a.source)],stdout=subprocess.PIPE)
 subprocess.run(['dd',f'of={a.output}','bs=4M','conv=sparse','status=none'],stdin=unzip.stdout,check=True)
 unzip.stdout.close();assert unzip.wait()==0
with loop(a.output) as device:
 with tempfile.TemporaryDirectory() as folder:
  with mount(device+'p2',pathlib.Path(folder)/'root') as root:
   assert not (root/'etc/machine-id').read_bytes().strip()
   assert not (root/'etc/justverify/node-ready.json').exists()
   assert not (root/'var/lib/justverify/web/admin.json').exists()
   ssh=root/'root/.ssh';ssh.mkdir(mode=0o700,exist_ok=True);ssh.chmod(0o700)
   assert not (ssh/'authorized_keys').exists(), 'refuse overwriting an existing authorization'
   (ssh/'authorized_keys').write_text(key+'\n');(ssh/'authorized_keys').chmod(0o600)
   assert not list((root/'etc/ssh').glob('ssh_host_*_key'))
   assert (root/'etc/systemd/system/ssh.service.d/justverify.conf').is_file()
 run(['/usr/sbin/e2fsck','-f','-n',device+'p2'])
 run(['/usr/sbin/zerofree',device+'p2'])
run(['sync'])
print(json.dumps({'status':'PASS_OFFLINE','scope':'private SSH-authorized clone; no owner account, TLS, Tor or SSH host identities pre-generated','source_sha256':a.sha256,'public_key_sha256':hashlib.sha256((key+'\n').encode()).hexdigest(),'boot':'NOT RUN'}))
