#!/usr/bin/env python3
"""Real encrypted v1 backup compatibility for optional device preferences."""
import importlib.util,json,os,pathlib,shutil,tempfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('fixture_test',ROOT/'tests/backup_bundle.py');helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
from backup_bundle import BackupBundle,FileSpec
with tempfile.TemporaryDirectory(prefix='jv-backup-device-') as temp:
 root=pathlib.Path(temp).resolve();specs,cleanup,barriers,expected=helper.fixture(root)
 def bundle(items,destination):return BackupBundle(items,root/'backup-state',destination,gpg=shutil.which('gpg'),openssl=shutil.which('openssl'),cleanup=cleanup,barriers=barriers)
 password='isolated device backup test phrase'
 legacy=bundle(specs,root/'boot/legacy.jvb');legacy.create(password)
 added=tuple(FileSpec('web/'+name,root/'state/web'/name,0o600,os.geteuid(),os.getegid(),False) for name in ('preferences.json','remote-web.json'))
 modern=bundle(specs+added,root/'boot/current.jvb')
 # A new installation accepts the complete legacy catalog, without weakening
 # the original mandatory entries or the encrypted manifest authentication.
 modern.inspect(legacy.destination,password)
 preferences={'schema':1,'name':'복구 시험','language':'ja','theme':'amber'}
 helper.write(added[0].path,json.dumps(preferences,ensure_ascii=False).encode(),0o600)
 helper.write(added[1].path,b'{"schema":1,"enabled":false,"phase":"committed"}',0o600)
 result=modern.create(password);original=modern.snapshot()
 helper.write(added[0].path,b'{"schema":1,"name":"changed","language":"ko","theme":"teal"}',0o600)
 modern.restore(password,result['sha256']);assert modern.snapshot()==original
 print('PASS: actual GPG legacy manifest compatibility + preference and remote-web restore')
