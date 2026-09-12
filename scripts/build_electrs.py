#!/usr/bin/env python3
"""Build immutable upstream electrs source in a fresh directory, preserving old builds."""
import hashlib,json,pathlib,subprocess,sys,tarfile,urllib.request
root=pathlib.Path(__file__).resolve().parents[1]
manifest=json.loads((root/'catalog/electrs.json').read_text())
output=pathlib.Path(sys.argv[1]).resolve()
output.mkdir(parents=True,exist_ok=False)
archive=output/'source.tar.gz'
with urllib.request.urlopen(manifest['source_url'],timeout=60) as response:archive.write_bytes(response.read())
assert hashlib.sha256(archive.read_bytes()).hexdigest()==manifest['source_sha256'],'source checksum mismatch'
with tarfile.open(archive) as tar:tar.extractall(output,filter='data')
source=output/('electrs-'+manifest['commit'])
assert hashlib.sha256((source/'Cargo.lock').read_bytes()).hexdigest()==manifest['cargo_lock_sha256'],'dependency lock mismatch'
subprocess.run(['cargo','build','--release','--locked'],cwd=source,check=True)
binary=source/'target/release/electrs'
assert subprocess.check_output([str(binary),'--version'],text=True).strip()=='v'+manifest['version']
result={'version':manifest['version'],'source_sha256':manifest['source_sha256'],'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'runtime_integration':'NOT RUN for this new build'}
(output/'build-result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
