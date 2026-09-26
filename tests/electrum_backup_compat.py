#!/usr/bin/env python3
"""Real encrypted restore of the historical fixed Electrum backend port."""
import hashlib,json,pathlib,secrets,sys,tempfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'tests')]
from backup_bundle import BackupBundle
from backup_guard import canonical_electrs_config
from importlib.machinery import SourceFileLoader
fixture=SourceFileLoader('backup_fixture',str(ROOT/'tests/backup_bundle.py')).load_module().fixture
canonical=(ROOT/'image/electrs.toml').read_bytes()
legacy=canonical.replace(b'127.0.0.1:50003',b'127.0.0.1:50001')
with tempfile.TemporaryDirectory(prefix='jv-electrum-backup-') as temporary:
    root=pathlib.Path(temporary);specs,cleanup,barriers,_=fixture(root,device=True)
    config=next(s.path for s in specs if s.key=='etc/electrs.toml')
    marker=next(s.path for s in specs if s.key=='etc/node-ready.json')
    def register(data):
        config.write_bytes(data);ready=json.loads(marker.read_bytes())
        ready['configs']['electrs.toml']=hashlib.sha256(data).hexdigest();marker.write_text(json.dumps(ready))
    def validate(values):
        values['etc/electrs.toml']=canonical_electrs_config(values['etc/electrs.toml'],canonical)
        ready=json.loads(values['etc/node-ready.json']);ready['configs']['electrs.toml']=hashlib.sha256(values['etc/electrs.toml']).hexdigest()
        values['etc/node-ready.json']=json.dumps(ready).encode()
    def bundle(guard=False):return BackupBundle(specs,root/'backup-state',root/'boot/backup.jvb',cleanup=cleanup,barriers=barriers,validate_context=validate if guard else None)
    password=secrets.token_urlsafe(24)
    for data in (legacy,canonical):
        register(data);made=bundle().create(password);register(canonical)
        before={s.key:s.path.read_bytes() for s in specs if s.path.is_file() and s.key not in ('etc/electrs.toml','etc/node-ready.json')}
        assert bundle(True).restore(password,made['sha256'])['phase']=='committed'
        assert config.read_bytes()==canonical
        assert all(s.path.read_bytes()==before[s.key] for s in specs if s.key in before)
        assert json.loads(marker.read_bytes())['configs']['electrs.toml']==hashlib.sha256(canonical).hexdigest()
    for bad in (legacy.replace(b'127.0.0.1:50001',b'0.0.0.0:50001'),legacy+b'jsonrpc_timeout_secs=1\n'):
        register(bad);made=bundle().create(password);register(canonical);before=marker.read_bytes()
        try:bundle(True).restore(password,made['sha256'])
        except ValueError:pass
        else:raise AssertionError('noncanonical encrypted Electrum configuration accepted')
        assert config.read_bytes()==canonical and marker.read_bytes()==before
    print('PASS actual GPG legacy/current Electrum restore, fixed loopback target and ready hash, preserved identity, noncanonical refusal before writes')
