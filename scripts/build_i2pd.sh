#!/bin/bash
# Build the pinned, unmodified router and a small native-runtime bundle.
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
work=${1:?new absolute ARM Linux build directory required}
[[ $(uname -m) = aarch64 && $(uname -s) = Linux && "$work" = /* && ! -e "$work" ]]
mkdir -p "$work/source" "$work/bundle/certificates"
python3 - "$root/catalog/i2pd.json" "$work" <<'PY'
import hashlib,json,pathlib,sys,urllib.request,tarfile
m=json.load(open(sys.argv[1]));work=pathlib.Path(sys.argv[2])
with urllib.request.urlopen(m['source_url'],timeout=120) as response:content=response.read()
assert hashlib.sha256(content).hexdigest()==m['source_sha256'],'I2Pd source checksum mismatch'
p=work/'i2pd-source.tar.gz';p.write_bytes(content)
with tarfile.open(p) as archive:
    for member in archive.getmembers():
        pieces=pathlib.PurePosixPath(member.name).parts[1:]
        if not pieces:continue
        member.name='/'.join(pieces)
        archive.extract(member,work/'source',filter='data')
PY
cmake -S "$work/source/build" -B "$work/build" -DCMAKE_BUILD_TYPE=Release -DWITH_HARDENING=ON -DWITH_UPNP=OFF -DWITH_LIBRARY=OFF
cmake --build "$work/build" -j2
install -m 0755 "$work/build/i2pd" "$work/bundle/i2pd"
strip --strip-unneeded "$work/bundle/i2pd"
cp -a "$work/source/contrib/certificates/." "$work/bundle/certificates/"
cp "$work/source/LICENSE" "$work/bundle/LICENSE"
cp "$root/catalog/i2pd.json" "$work/bundle/manifest.json"
cp "$work/i2pd-source.tar.gz" "$work/bundle/"
python3 - "$work/bundle" <<'PY'
import hashlib,json,pathlib,subprocess,sys
p=pathlib.Path(sys.argv[1]);m=json.loads((p/'manifest.json').read_text());m['binary_sha256']=hashlib.sha256((p/'i2pd').read_bytes()).hexdigest()
m['build_tools']={tool:subprocess.check_output([tool,'--version'],text=True).splitlines()[0] for tool in ['c++','cmake']}
m['runtime_libraries']=subprocess.check_output(['ldd',str(p/'i2pd')],text=True)
assert 'not found' not in m['runtime_libraries']
m['version_output']=subprocess.check_output([str(p/'i2pd'),'--version'],text=True).strip()
assert m['version'] in m['version_output']
(p/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
files=sorted(f for f in p.rglob('*') if f.is_file())
(p/'SHA256SUMS').write_text(''.join(hashlib.sha256(f.read_bytes()).hexdigest()+'  '+str(f.relative_to(p))+'\n' for f in files))
PY
