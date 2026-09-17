#!/usr/bin/env python3
"""Real filesystem/child-output limits and retained profile identity."""
import pathlib,subprocess,sys,tempfile
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from mempool_service import BoundedLog,LOG_BYTES,profile_folder,trim_cache

with tempfile.TemporaryDirectory(prefix='jv-storage-limits-') as tmp:
    root=pathlib.Path(tmp)
    profile={'version':'31.1','data_id':'22.0','network':'regtest'}
    folder=profile_folder(root,profile)
    marker=folder/'mysql';marker.mkdir();(marker/'preserved').write_bytes(b'unchanged')
    profile['version']='30.2'
    assert profile_folder(root,profile)==folder
    for identity in ('../22.0','/tmp/22.0','22.0/../31.1','22.0-other'):
        try:profile_folder(root,{**profile,'data_id':identity})
        except ValueError:pass
        else:raise AssertionError('invalid identity accepted')
    linked=root/'regtest-23.0';linked.symlink_to(folder)
    try:profile_folder(root,{**profile,'data_id':'23.0'})
    except ValueError:pass
    else:raise AssertionError('linked profile accepted')
    cache=folder/'cache';cache.mkdir()
    for name in ('rbfcache.json','tmp-rbfcache.json','rbfcache.json.oversized-123'):
        with (cache/name).open('wb') as f:f.truncate(65*1024**2)
    (cache/'unrelated').write_bytes(b'preserved')
    trim_cache(cache)
    assert {p.name for p in cache.iterdir()}=={'unrelated'}
    logpath=folder/'backend.log'
    with logpath.open('wb') as f:f.truncate(100*1024**2)
    child=subprocess.Popen([sys.executable,'-c','import sys;sys.stdout.buffer.write(b"x"*(12*1024**2))'],stdout=subprocess.PIPE)
    log=BoundedLog(logpath,child.stdout);assert child.wait(timeout=20)==0;log.close()
    assert not log.thread.is_alive()
    assert sum(p.stat().st_size for p in folder.glob('backend.log*'))<=3*LOG_BYTES
    assert (marker/'preserved').read_bytes()==b'unchanged'
    print('PASS stable storage identity, path refusal, disposable cache quota, real child log rotation, unrelated data preserved')
