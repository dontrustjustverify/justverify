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
 for language,rain in (('ja',None),('auto',None),('ko',{'enabled':True,'brightness':27,'speed':130,'density':120}),('en',{'enabled':False,'brightness':3,'speed':15,'density':30}),('ko',{'enabled':True,'brightness':100,'speed':400,'density':300})):
  preferences={'schema':1 if rain is None else 2,'name':'복구 시험','language':language,'theme':'amber'}
  if rain is not None:preferences['background']=rain
  helper.write(added[0].path,json.dumps(preferences,ensure_ascii=False).encode(),0o600)
  helper.write(added[1].path,b'{"schema":1,"enabled":false,"phase":"committed"}',0o600)
  result=modern.create(password);original=modern.snapshot()
  helper.write(added[0].path,b'{"schema":1,"name":"changed","language":"ko","theme":"teal"}',0o600)
  modern.restore(password,result['sha256']);assert modern.snapshot()==original
 for rain in ({'enabled':1,'brightness':18,'speed':70,'density':75},{'enabled':True,'brightness':101,'speed':70,'density':75},{'enabled':True,'brightness':18,'speed':14,'density':75},{'enabled':True,'brightness':40,'speed':401,'density':140},{'enabled':True,'brightness':18,'speed':70,'density':301}):
  helper.write(added[0].path,json.dumps({**preferences,'background':rain}).encode(),0o600)
  previous=modern.destination.read_bytes()
  try:modern.create(password)
  except ValueError:pass
  else:raise AssertionError('Invalid background was accepted into an encrypted backup')
  assert modern.destination.read_bytes()==previous
 print(json.dumps({'status':'PASS','checks':['actual GPG legacy manifest compatibility','manual/automatic language and remote-web restore','schema2 enabled/disabled Digital Rain exact restore','invalid background types/ranges rejected without replacing existing backup']}))
