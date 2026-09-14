#!/usr/bin/env python3
"""Real encrypted backup restore: exact historical Tor layouts and fixed upgrade."""
import json,pathlib,secrets,sys,tempfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'tests')]
from backup_bundle import BackupBundle
from backup_guard import canonical_tor_config
from importlib.machinery import SourceFileLoader
fixture=SourceFileLoader('backup_fixture',str(ROOT/'tests/backup_bundle.py')).load_module().fixture
template=(ROOT/'image/torrc').read_bytes()
canonical=canonical_tor_config(template,template,8333)
old=canonical.removesuffix(b'HiddenServicePort 3006 127.0.0.1:28445\n')
legacy=old.removesuffix(b'HiddenServiceDir /var/lib/justverify-tor/web\nHiddenServiceVersion 3\nHiddenServicePort 80 127.0.0.1:28444\n')
assert len(legacy)<len(old)<len(canonical)
with tempfile.TemporaryDirectory(prefix='jv-tor-backup-') as temporary:
    root=pathlib.Path(temporary);specs,cleanup,barriers,_=fixture(root,device=True)
    tor=next(spec.path for spec in specs if spec.key=='etc/torrc')
    password=secrets.token_urlsafe(24)
    destination=root/'boot/backup.jvb'
    def bundle(guard=False):
        def validate(values):values['etc/torrc']=canonical_tor_config(values['etc/torrc'],template,8333)
        return BackupBundle(specs,root/'backup-state',destination,cleanup=cleanup,barriers=barriers,validate_context=validate if guard else None)
    for layout in (legacy,old,canonical):
        tor.write_bytes(layout);plain=bundle();made=plain.create(password)
        tor.write_bytes(canonical)
        guarded=bundle(True);guarded.inspect(destination,password)
        assert guarded.restore(password,made['sha256'])['phase']=='committed'
        assert tor.read_bytes()==canonical
    for bad in (old+b'SocksPort 0.0.0.0:9050\n',canonical.replace(b'127.0.0.1:28445',b'127.0.0.1:8332'),canonical+b'HiddenServicePort 9999 127.0.0.1:22\n'):
        tor.write_bytes(bad);made=bundle().create(password);tor.write_bytes(canonical)
        try:bundle(True).restore(password,made['sha256'])
        except ValueError:pass
        else:raise AssertionError('Noncanonical encrypted Tor configuration accepted')
        assert tor.read_bytes()==canonical
    print(json.dumps({'status':'PASS','checks':['three historical/current Tor layouts restored through actual GPG to fixed current template','three noncanonical encrypted configurations rejected before write'],'scope':'isolated files with real crypto; production data-volume guard tested by image probe'}))
