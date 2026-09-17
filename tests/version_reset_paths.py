#!/usr/bin/env python3
"""Filesystem adversarial tests, additional to actual Core/electrs integration."""
import copy,importlib.util,json,os,pathlib,shutil,subprocess,tempfile
assert os.geteuid()==0 and subprocess.check_output(['hostname'],text=True).strip()=='justverify-reset-test'
source=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('chain_reset',source/'scripts/chain_reset.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
work=pathlib.Path(tempfile.mkdtemp(prefix='jv-reset-paths-',dir='/var/tmp'))
root=work/'data';core=root/'regtest/31.1/core';index=root/'regtest/31.1/electrs-0.11.1';chain=core/'regtest'
for p in (chain/'blocks',chain/'chainstate',index/'regtest'):p.mkdir(parents=True,exist_ok=True)
instance={'core_version':'31.1','network':'regtest','electrs_version':'0.11.1','core_data':str(core),'electrs_data':str(index)}
req={'root':str(root),'instance':instance,'action':'prepare'}
(chain/'blocks/blk00000.dat').write_bytes(b'chain');(index/'regtest/CURRENT').write_bytes(b'index')
outside=work/'preserved';outside.write_bytes(b'preserve')
def refused(request):
 try:module.run(request)
 except (ValueError,OSError):pass
 else:raise AssertionError('unsafe filesystem request was accepted')
 assert outside.read_bytes()==b'preserve'
try:
 receipt=module.run(req)
 q={**req,'action':'reset','receipt':receipt}
 (chain/'blocks/blk00001.dat').symlink_to(outside);refused(q);(chain/'blocks/blk00001.dat').unlink()
 os.link(outside,chain/'blocks/blk00001.dat');refused(q);(chain/'blocks/blk00001.dat').unlink()
 (chain/'blocks/personal-note').write_text('preserve');refused(q);assert (chain/'blocks/personal-note').read_text()=='preserve';(chain/'blocks/personal-note').unlink()
 forged=copy.deepcopy(req);forged['instance']['core_data']=str(root/'regtest/31.1/../../preserved');refused(forged)
 original=core.with_name('core-held');core.rename(original);core.symlink_to(original,target_is_directory=True);refused(q);core.unlink();original.rename(core)
 # Same inode/device but a different bind mount must invalidate the receipt.
 subprocess.run(['mount','--bind',str(root),str(root)],check=True)
 try:refused(q)
 finally:subprocess.run(['umount',str(root)],check=True)
 subprocess.run(['mount','--bind',str(chain/'blocks'),str(chain/'blocks')],check=True)
 try:refused(q)
 finally:subprocess.run(['umount',str(chain/'blocks')],check=True)
 held=work/'data-held';root.rename(held);shutil.copytree(held,root);refused(q);shutil.rmtree(root);held.rename(root)
 for name in ('wallet.dat','settings.json'):
  file=chain/name;file.write_text('{}' if name=='wallet.dat' else '{"wallet":["outside"]}');refused(q);assert file.exists();file.unlink()
 assert module.run(q)=={'ok':True};assert not (chain/'blocks').exists() and not (index/'regtest').exists();assert core.is_dir() and index.is_dir()
 assert module.run(q)=={'ok':True} # Idempotent partial-reset/recovery scope.
 print(json.dumps({'status':'PASS','checks':['symlink, hardlink and unknown file refuse whole reset','path escape refused','linked datadir refused','same-filesystem root bind mount invalidates token','nested bind mount refused','replaced root identity refused','wallet and persistent wallet setting block reset','outside file preserved','fixed-scope reset is idempotent and keeps outer paths']}))
finally:shutil.rmtree(work)
