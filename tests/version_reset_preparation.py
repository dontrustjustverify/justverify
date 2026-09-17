#!/usr/bin/env python3
"""Real rejected download/GPG/checksum/preflight cases leave the running chain intact."""
from version_reset_native import *
import shutil,tempfile
source=pathlib.Path(__file__).resolve().parents[1]
work=pathlib.Path(tempfile.mkdtemp(prefix='jv-reset-preparation-',dir='/var/tmp'))
try:
 before=rpc('getblockchaininfo');active=(STATE/'active.json').read_bytes()
 binary=pathlib.Path('/opt/justverify/versions/22.0/bitcoin-22.0/bin/bitcoind')
 saved=binary.with_name('bitcoind.preparation-fixture');binary.rename(saved)
 try:assert not api('preview',version='22.0',network='regtest',watch_only=False)['ok']
 finally:saved.rename(binary)
 policy=pathlib.Path(json.loads(active)['policy_file']);original=policy.read_bytes()
 policy.write_bytes(original+b'\ntxospenderindex=1\n') # Absent from Core22: exact current policy must not be silently ignored
 try:
  refused=api('preview',version='22.0',network='regtest',watch_only=False);assert not refused['ok'] and 'unknown option' in refused['error']
 finally:policy.write_bytes(original)
 binary.chmod(0o644)
 try:
  refused=api('preview',version='22.0',network='regtest',watch_only=False);assert not refused['ok']
 finally:binary.chmod(0o755)
 # Reverify actual official archive/key inputs with unmodified production logic.
 official=pathlib.Path('/var/tmp/jv-reset-official')
 valid=work/'valid';shutil.copytree(official,valid)
 def fetch(cache):
  return subprocess.run(['python3',str(source/'scripts/fetch_core.py'),'22.0','aarch64-linux-gnu','--cache-root',str(cache),'--evidence-dir',str(work/'evidence')],capture_output=True,timeout=90)
 assert fetch(valid).returncode==0
 bad_signature=work/'bad-signature';shutil.copytree(official,bad_signature)
 sums=bad_signature/'core/22.0/SHA256SUMS';sums.write_bytes(sums.read_bytes()+b'\n# altered signed document\n')
 result=fetch(bad_signature);assert result.returncode!=0 and b'Bad cryptographic signature' in result.stderr
 bad_archive=work/'bad-archive';shutil.copytree(official,bad_archive)
 archive=bad_archive/'core/22.0/bitcoin-22.0-aarch64-linux-gnu.tar.gz'
 with archive.open('ab') as file:file.write(b'altered')
 result=fetch(bad_archive);assert result.returncode!=0 and b'Archive checksum mismatch' in result.stderr
 result=subprocess.run(['python3',str(source/'scripts/fetch_core.py'),'22.0','aarch64-linux-gnu','--cache-root',str(work/'offline'),'--evidence-dir',str(work/'evidence')],capture_output=True,env={**os.environ,'https_proxy':'http://127.0.0.1:9','http_proxy':'http://127.0.0.1:9'},timeout=20)
 assert result.returncode!=0
 assert (STATE/'active.json').read_bytes()==active and rpc('getblockcount')==before['blocks']
 print(json.dumps({'status':'PASS','checks':['missing target binary rejects preview without deletion','unsupported target setting refuses before application','actual isolated target startup permission failure','real trusted GPG signature/checksum success','actual signed-document and archive tampering rejected','actual official downloader connection failure','running Core and active registration unchanged']}))
finally:shutil.rmtree(work)
