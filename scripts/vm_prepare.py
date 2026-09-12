#!/usr/bin/env python3
"""Private disposable Debian ARM VM; never touches physical disks."""
import hashlib, pathlib, subprocess, io, json
import pycdlib
R=pathlib.Path(__file__).resolve().parents[1];S=R/'.state/vm';S.mkdir(parents=True,exist_ok=True);S.chmod(0o700)
base=R/'.cache/vm/debian.qcow2';partial=base.with_suffix('.qcow2.partial')
expected='321adcf21b6d2941e09e96f333af0c8f35b0865904834a4eb8149cfd2286b902d4868494ddfc863052a3267886533796aa3e21db24a243c0fc56a49c753471be'
source=base if base.exists() else partial
assert hashlib.file_digest(source.open('rb'),'sha512').hexdigest()==expected,'VM base checksum mismatch'
if not base.exists():partial.rename(base)
if not (S/'id_ed25519').exists():subprocess.run(['ssh-keygen','-q','-t','ed25519','-N','','-f',str(S/'id_ed25519')],check=True)
if not (S/'disk.qcow2').exists():
    subprocess.run(['qemu-img','create','-f','qcow2','-F','qcow2','-b',str(base),str(S/'disk.qcow2'),'32G'],check=True)
key=(S/'id_ed25519.pub').read_text().strip()
user=f'''#cloud-config
hostname: justverify-dev
ssh_pwauth: false
disable_root: true
users:
  - name: builder
    groups: [sudo]
    sudo: ALL=(ALL) NOPASSWD:ALL
    shell: /bin/bash
    lock_passwd: true
    ssh_authorized_keys:
      - {key}
'''
iso=pycdlib.PyCdlib();iso.new(interchange_level=3,joliet=3,vol_ident='cidata',rock_ridge='1.09')
for name,content in [('user-data',user),('meta-data','instance-id: justverify-dev-001\nlocal-hostname: justverify-dev\n')]:
    data=content.encode();iso.add_fp(io.BytesIO(data),len(data),iso_path='/'+name.upper().replace('-','_')+';1',rr_name=name,joliet_path='/'+name)
iso.write(str(S/'seed.iso'));iso.close()
(R/'docs/evidence/vm-base.json').write_text(json.dumps({'url':'https://cloud.debian.org/images/cloud/trixie/20260831-2587/debian-13-genericcloud-arm64-20260831-2587.qcow2','sha512':expected,'validation':'official HTTPS SHA512 match; no detached signature validation yet','scope':'development VM, not Pi image'},indent=2)+'\n')
