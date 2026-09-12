#!/usr/bin/env python3
"""Download official Core; require pinned trusted signer AND archive checksum."""
import argparse, hashlib, json, os, pathlib, re, subprocess, tarfile, urllib.request, fcntl
ROOT = pathlib.Path(__file__).resolve().parents[1]
TRUST_RECORDS = json.loads((ROOT/'catalog/trusted-builders.json').read_text())
TRUSTED = {name: info['fingerprint'] for name, info in TRUST_RECORDS.items()}
KEY_COMMIT = '3b667ee3ebb3dcd9e1990cf03e38a0935eec1683'
def download(url, dest):
    if not dest.exists():
        temp = dest.with_suffix(dest.suffix + '.partial')
        with urllib.request.urlopen(url, timeout=60) as response, temp.open('wb') as out:
            while chunk := response.read(1024*1024): out.write(chunk)
        temp.replace(dest)
def _fetch(version, arch, cache_root=None, evidence_dir=None):
    if not re.fullmatch(r'\d+\.\d+(?:\.\d+)?', version) or int(version.split('.')[0]) < 22:
        raise ValueError('stable Core >=22 required')
    if arch not in ['arm64-apple-darwin','aarch64-linux-gnu','x86_64-linux-gnu','x86_64-apple-darwin']:
        raise ValueError('unsupported architecture')
    cache_root=pathlib.Path(cache_root) if cache_root else ROOT/'.cache'
    evidence_dir=pathlib.Path(evidence_dir) if evidence_dir else ROOT/'docs/evidence'
    evidence_dir.mkdir(parents=True,exist_ok=True)
    cache = cache_root / 'core' / version
    cache.mkdir(parents=True, exist_ok=True)
    home = cache_root / 'gnupg'; home.mkdir(mode=0o700, exist_ok=True); home.chmod(0o700)
    for signer, fingerprint in TRUSTED.items():
        key = home / (signer + '.gpg')
        download(f'https://raw.githubusercontent.com/bitcoin-core/guix.sigs/{KEY_COMMIT}/builder-keys/{signer}.gpg',key)
        if hashlib.sha256(key.read_bytes()).hexdigest() != TRUST_RECORDS[signer]['sha256']: raise RuntimeError('Pinned key file checksum mismatch')
        info = subprocess.run(['gpg','--homedir',str(home),'--with-colons','--show-keys',str(key)],check=True,capture_output=True,text=True)
        if f'fpr:::::::::{fingerprint}:' not in info.stdout: raise RuntimeError('Pinned key mismatch')
        subprocess.run(['gpg','--homedir',str(home),'--batch','--import',str(key)],check=True,capture_output=True)
    base = f'https://bitcoincore.org/bin/bitcoin-core-{version}/'
    name = f'bitcoin-{version}-{arch}.tar.gz'
    for file in ['SHA256SUMS','SHA256SUMS.asc', name]: download(base+file,cache/file)
    result = subprocess.run(['gpg','--homedir',str(home),'--batch','--status-fd','1','--verify',str(cache/'SHA256SUMS.asc'),str(cache/'SHA256SUMS')],capture_output=True,text=True)
    groups=[]
    for line in result.stdout.splitlines():
        if line.startswith('[GNUPG:] NEWSIG'): groups.append([])
        if groups: groups[-1].append(line.split())
    accepted=set()
    for group in groups:
        statuses={v[1] for v in group if len(v)>1}
        if 'BADSIG' in statuses: raise RuntimeError('Bad cryptographic signature present')
        if not 'GOODSIG' in statuses or statuses & {'EXPSIG','EXPKEYSIG','REVKEYSIG','ERRSIG'}: continue
        for v in group:
            if len(v)>2 and v[1]=='VALIDSIG':
                accepted.update(fp for fp in TRUSTED.values() if fp in (v[2],v[-1]))
    accepted=sorted(accepted)
    if not accepted: raise RuntimeError('No valid unexpired trusted release signature')
    hashes = {line.split()[-1].lstrip('*'): line.split()[0] for line in (cache/'SHA256SUMS').read_text().splitlines() if line.strip()}
    digest = hashlib.file_digest((cache/name).open('rb'),'sha256').hexdigest() if hasattr(hashlib,'file_digest') else hashlib.sha256((cache/name).read_bytes()).hexdigest()
    if hashes.get(name) != digest: raise RuntimeError('Archive checksum mismatch')
    output = cache / arch; output.mkdir(exist_ok=True)
    with tarfile.open(cache/name) as archive:
        for member in archive.getmembers():
            path = pathlib.PurePosixPath(member.name)
            if path.is_absolute() or '..' in path.parts:
                raise RuntimeError('Unsafe archive entry')
        archive.extractall(output, filter='data')
    evidence = dict(version=version,arch=arch,url=base+name,sha256=digest,signers=accepted,key_commit=KEY_COMMIT,status='SIGNATURE_AND_CHECKSUM_PASS')
    (evidence_dir/f'core-{version}-{arch}-download.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print(output/f'bitcoin-{version}'/'bin'/'bitcoind')
def fetch(version, arch, cache_root=None, evidence_dir=None):
    cache_root=pathlib.Path(cache_root) if cache_root else ROOT/'.cache'
    cache_root.mkdir(parents=True,exist_ok=True)
    # Serialize keyring/cache writes even if a previous caller's parent process exited.
    with (cache_root/'.fetch.lock').open('a') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX)
        return _fetch(version,arch,cache_root,evidence_dir)
if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('version');p.add_argument('arch');p.add_argument('--cache-root');p.add_argument('--evidence-dir');a=p.parse_args();fetch(a.version,a.arch,a.cache_root,a.evidence_dir)
