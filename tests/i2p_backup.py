#!/usr/bin/env python3
"""Real encrypted backup/restore of a Core-generated isolated I2P identity."""
import argparse, hashlib, importlib.util, os, pathlib, shutil, tempfile

root=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('fixture_test',root/'tests/backup_bundle.py')
helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
from backup_bundle import BackupBundle, FileSpec

parser=argparse.ArgumentParser();parser.add_argument('--key',type=pathlib.Path,required=True);args=parser.parse_args()
identity=args.key.read_bytes()
assert 387 <= len(identity) <= 2048, 'expected a real Core SAM identity, not a wallet or arbitrary file'
with tempfile.TemporaryDirectory(prefix='jv-i2p-backup-') as temp:
    directory=pathlib.Path(temp).resolve();specs,cleanup,barriers,_=helper.fixture(directory)
    key=FileSpec('core/i2p_private_key',directory/'state/core/regtest/i2p_private_key',0o600,os.geteuid(),os.getegid(),False)
    def bundle(entries,name):
        return BackupBundle(entries,directory/'backup-state',directory/'boot'/name,gpg=shutil.which('gpg'),openssl=shutil.which('openssl'),cleanup=cleanup,barriers=barriers)
    password='isolated encrypted I2P identity test'
    legacy=bundle(specs,'legacy.jvb');legacy.create(password)
    current=bundle(specs+(key,),'current.jvb');current.inspect(legacy.destination,password)
    helper.write(key.path,identity,0o600)
    saved=current.create(password);snapshot=current.snapshot()
    assert identity not in current.destination.read_bytes()
    helper.write(key.path,b'damaged disposable identity',0o600)
    current.restore(password,saved['sha256'])
    assert current.snapshot()==snapshot and key.path.read_bytes()==identity
    assert key.path.stat().st_mode&0o777==0o600
    print('PASS: actual GPG roundtrip restores Core I2P key bytes and0600; accepts older complete backup without I2P entry; ciphertext has no plaintext key')
