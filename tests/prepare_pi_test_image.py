#!/usr/bin/env python3
"""Personalize only a new private test image for the explicitly authorized Pi5."""
import argparse,hashlib,json,os,pathlib,subprocess,sys,tempfile
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from build_single_disk import loop,mount,run
p=argparse.ArgumentParser();p.add_argument('--source',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);p.add_argument('--public-key',type=pathlib.Path,required=True);p.add_argument('--owner',type=pathlib.Path,required=True);a=p.parse_args()
assert os.geteuid()==0 and not a.output.exists() and a.output.is_absolute() and a.output.parent==ROOT/'.state' and a.output.suffix=='.img'
with a.source.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()=='36430b66111db10204a37cf524ab17575d1248c4061a0bd96ed9070debcf4e42'
key=a.public_key.read_text().strip();assert key.startswith('ssh-ed25519 ') and len(key)<512 and '\n' not in key
run(['/usr/bin/ssh-keygen','-l','-f',str(a.public_key)])
owner=json.loads(a.owner.read_text());assert owner['format']=='justverify-owner-v1' and len(owner['setup_token'])>=40
with a.output.open('xb') as out:
 a.output.chmod(0o600)
 unzip=subprocess.Popen(['xz','-dc',str(a.source)],stdout=subprocess.PIPE)
 copy=subprocess.run(['dd',f'of={a.output}','bs=4M','conv=sparse','status=none'],stdin=unzip.stdout,check=True);unzip.stdout.close();assert unzip.wait()==0
with loop(a.output) as device:
 with tempfile.TemporaryDirectory() as folder:
  with mount(device+'p2',pathlib.Path(folder)/'root') as root:
   assert not (root/'etc/machine-id').read_bytes().strip() and not (root/'etc/justverify/node-ready.json').exists()
   ssh=root/'root/.ssh';ssh.mkdir(mode=0o700,exist_ok=True);ssh.chmod(0o700)
   (ssh/'authorized_keys').write_text(key+'\n');(ssh/'authorized_keys').chmod(0o600)
   config=root/'etc/ssh/sshd_config.d/00-justverify-pi5-test.conf'
   if not (root/'etc/ssh/sshd_config.d/00-justverify.conf').exists():config.write_text('PermitRootLogin prohibit-password\nPasswordAuthentication no\nKbdInteractiveAuthentication no\nPubkeyAuthentication yes\nAllowUsers root\n')
   if config.exists():config.chmod(0o600)
   unit=root/'etc/systemd/system/justverify-test-ssh-keys.service'
   unit.write_text('[Unit]\nDescription=Generate unique SSH host keys for authorized Pi test\nAfter=justverify-firstboot.service\nRequires=justverify-firstboot.service\nBefore=ssh.service\n[Service]\nType=oneshot\nExecStart=/usr/bin/ssh-keygen -A\nRemainAfterExit=yes\n')
   drop=root/'etc/systemd/system/ssh.service.d';drop.mkdir(exist_ok=True)
   (drop/'justverify-test.conf').write_text('[Unit]\nRequires=justverify-test-ssh-keys.service\nAfter=justverify-test-ssh-keys.service\n')
   link=root/'etc/systemd/system/multi-user.target.wants/ssh.service'
   if not link.exists():link.symlink_to('/usr/lib/systemd/system/ssh.service')
   else:assert link.is_symlink()
   with mount(device+'p1',root/'boot/firmware') as boot:
    (boot/'justverify-owner.json').write_bytes(a.owner.read_bytes())
   assert not list((root/'etc/ssh').glob('ssh_host_*_key'))
run(['sync']);print('PASS private Pi image prepared; per-device SSH host keys remain ungenerated; boot/SSH test NOT RUN')
