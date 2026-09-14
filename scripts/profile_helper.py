#!/usr/bin/python3 -I
"""Root-only fixed service profile bridge. Input permits identifiers, never paths or commands."""
import hashlib, json, os, pathlib, re, subprocess, sys, tempfile
ETC=pathlib.Path('/etc/justverify')
DATA=pathlib.Path('/srv/justverify/data')
BINARIES=pathlib.Path('/opt/justverify/versions')
CATALOG=pathlib.Path('/opt/justverify/catalog')
EXPLORER_UNITS=('justverify-mempool',) if pathlib.Path('/etc/systemd/system/justverify-mempool.service').is_file() else ()
UNITS=EXPLORER_UNITS+('justverify-policy','justverify-electrum-tls','justverify-electrs','justverify-core','justverify-manager','justverify-i2p')
NETWORKS={'main':('bitcoin','',8332,8333),'test':('testnet','testnet3',18332,18333),'testnet4':('testnet4','testnet4',48332,48333),'signet':('signet','signet',38332,38333),'regtest':('regtest','regtest',18443,18444)}
def system(*args):
    subprocess.run(['/usr/bin/systemctl',*args],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
def atomic(path,text):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='.profile-',dir=path.parent)
    try:
        with os.fdopen(fd,'w') as file:file.write(text);file.flush();os.fsync(file.fileno())
        os.chmod(name,0o644);os.replace(name,path)
        folder=os.open(path.parent,os.O_RDONLY);os.fsync(folder);os.close(folder)
    finally:
        if os.path.exists(name):os.unlink(name)
def real_path(path,root):
    relative=path.relative_to(root)
    current=root
    if root.is_symlink():raise ValueError('linked managed root refused')
    for part in relative.parts:
        current=current/part
        if current.is_symlink():raise ValueError('linked managed path refused')
    return path

def check_initial(data=DATA,owner=pathlib.Path('/var/lib/justverify/web/admin.json'),state=pathlib.Path('/var/lib/justverify-storage')):
    # Fixed production paths; injectable paths are used only by direct VM tests.
    if data.is_symlink() or not os.path.ismount(data):raise ValueError('initial volume must be mounted')
    for path in (data,state):
        metadata=path.stat()
        if path.is_symlink() or metadata.st_uid!=0 or metadata.st_mode&0o022:raise ValueError('initial volume and journal root must be root controlled')
    if owner.is_symlink():raise ValueError('linked owner record refused')
    enrollment=json.loads(owner.read_text())
    if not re.fullmatch('[a-f0-9]{32}',enrollment.get('salt','')) or not re.fullmatch('[a-f0-9]{128}',enrollment.get('hash','')):raise ValueError('owner enrollment required')
    marker=data/'justverify-volume.json';metadata=marker.lstat()
    if marker.is_symlink() or metadata.st_uid!=0 or metadata.st_mode&0o022:raise ValueError('untrusted volume marker')
    volume=json.loads(marker.read_text())
    if volume.get('schema')!=1 or volume.get('layout')!='versioned-instances':raise ValueError('unsupported initial volume')
    actual=subprocess.run(['/usr/bin/findmnt','-n','-o','UUID','--target',str(data)],check=True,capture_output=True,text=True,timeout=10).stdout.strip()
    if not actual or volume.get('uuid')!=actual:raise ValueError('initial volume UUID mismatch')
    committed=False
    for path in state.glob('*.json'):
        metadata=path.lstat()
        if path.is_symlink() or metadata.st_uid!=0 or metadata.st_mode&0o077:raise ValueError('untrusted volume journal')
        plan=json.loads(path.read_text())
        if plan.get('phase') not in ('prepared','committed'):raise ValueError('volume recovery required')
        if plan.get('uuid')==actual and plan.get('mount')==str(data) and plan.get('phase')=='committed':committed=True
    if not committed and pathlib.Path('/etc/justverify-factory.json').exists():
        factory=json.loads(subprocess.run(['/usr/bin/python3','/opt/justverify/scripts/factory_volume.py','--verify'],check=True,capture_output=True,text=True,timeout=30).stdout)
        committed=factory.get('uuid')==actual and factory.get('mount')==str(data)
    if not committed:raise ValueError('no committed provisioning record for initial volume')
    if any(path.name not in ('lost+found','instances','justverify-volume.json') for path in data.iterdir()):raise ValueError('existing volume contents must be preserved')
    instances=real_path(data/'instances',data)
    if not instances.is_dir() or any(instances.iterdir()):raise ValueError('existing instance data cannot be initially registered')

def validate(request):
    if not isinstance(request,dict):raise ValueError('request must be an object')
    if request=={'action':'stop'}:return None
    if set(request) not in ({'action','version','network'},{'action','version','network','watch_only'}) or request['action']!='activate':raise ValueError('unknown action or field')
    version=request['version'];network=request['network'];watch_only=request.get('watch_only',False)
    if type(watch_only) is not bool:raise ValueError('invalid wallet mode')
    if not isinstance(version,str) or not re.fullmatch(r'[0-9]+\.[0-9]+(?:\.[0-9]+)?',version) or network not in NETWORKS:raise ValueError('invalid version/network')
    releases=json.loads((CATALOG/'releases.json').read_text())['releases']
    release=next((r for r in releases if r['version']==version),None)
    if not release or release['availability']!='OFFICIAL_BINARY_VERIFIED' or network not in release['networks']:raise ValueError('unverified release/network')
    if release['electrs']['version']!='0.11.1' or release['electrs']['status']!='PASS':raise ValueError('unverified indexer combination')
    binary=real_path(BINARIES/version/('bitcoin-'+version)/'bin/bitcoind',BINARIES)
    if hashlib.sha256(binary.read_bytes()).hexdigest()!=release['arm64_binary_sha256']:raise ValueError('Core hash mismatch')
    folder=real_path(DATA/'instances'/network/(version+'-watch-only' if watch_only else version),DATA)
    expected={'core_version':version,'network':network,'electrs_version':'0.11.1','core_data':str(folder/'core'),'electrs_data':str(folder/'electrs-0.11.1')}
    if watch_only:expected['watch_only']=True
    marker=real_path(folder/'instance.json',DATA)
    if json.loads(marker.read_text())!=expected:raise ValueError('unmarked or incompatible data')
    for name in ('core','electrs-0.11.1'):
        if not real_path(folder/name,DATA).is_dir():raise ValueError('missing data directory')
    policy=real_path(folder/'managed.conf',DATA)
    if not policy.is_file():raise ValueError('managed policy must be prepared by unprivileged service')
    return version,network,binary,folder,policy,watch_only

def render_profile(checked):
    version,network,binary,folder,policy,watch_only=checked
    electrum_network,subdir,rpc,p2p=NETWORKS[network]
    cookie=folder/'core'/subdir/'.cookie'
    # Tor owns persistent inbound identities; Core uses SOCKS only for onion
    # destinations. Clearnet remains direct unless separately configured.
    core_config=f'includeconf={policy}\nserver=1\ndisablewallet={0 if watch_only else 1}\nprune=0\nlisten=1\nlistenonion=0\nonion=127.0.0.1:9050\n'
    options=json.loads((CATALOG/'runtime-options.json').read_text())[version]['options']
    for option in ('natpmp','upnp'):
        if option in options:core_config+=option+'=0\n'
    if network!='main':core_config+=f'chain={network}\n'
    core_config+=f'[{network}]\nrpcbind=127.0.0.1\nrpcallowip=127.0.0.1\n'
    if network=='regtest':core_config+=f'connect=0\ndnsseed=0\nbind=127.0.0.1:{p2p}\n'
    else:core_config+=f'bind=0.0.0.0:{p2p}\nbind=[::]:{p2p}\n'
    core_config+=f'bind=127.0.0.1:{p2p+1}=onion\nwhitebind=download,noban@127.0.0.1:{p2p+2}\n'
    files={'etc/bitcoin.conf':core_config}
    files['etc/electrs.toml']=f'network = "{electrum_network}"\ndaemon_dir = "{folder}/core"\ncookie_file = "{cookie}"\ndb_dir = "{folder}/electrs-0.11.1"\ndaemon_rpc_addr = "127.0.0.1:{rpc}"\ndaemon_p2p_addr = "127.0.0.1:{p2p+2}"\nelectrum_rpc_addr = "127.0.0.1:50001"\nmonitoring_addr = "127.0.0.1:4224"\nno_auto_reindex = true\nlog_filters = "INFO"\n'
    profile={'version':version,'network':network,'binary':str(binary),'catalog':str(CATALOG),'managed_config':str(policy),'staging':'/var/lib/justverify/preflight','cookie':str(cookie),'rpc_port':rpc,'p2p_backend_port':p2p+2,'watch_only':watch_only}
    files['etc/profile.json']=json.dumps(profile,indent=2)+'\n'
    overrides={
      'core':f'ExecStart=\nExecStart={binary} -datadir={folder}/core -conf=/etc/justverify/bitcoin.conf\nReadWritePaths=\nReadWritePaths={folder}/core\n',
      'electrs':f'ReadWritePaths=\nReadWritePaths={folder}/electrs-0.11.1\n',
      'manager':f'ExecStart=\nExecStart=/opt/justverify/bin/justverify daemon --cookie {cookie} --rpc-port {rpc} --socket /run/justverify/manager.sock\n',
      'policy':f'ReadWritePaths=\nReadWritePaths=/var/lib/justverify/config /var/lib/justverify/preflight {folder}\n',
    }
    for name,body in overrides.items():files[f'systemd/{name}-profile.conf']='[Service]\n'+body
    return {name:text.encode() for name,text in files.items()}

def activate(checked):
    version,network,binary,folder,policy,watch_only=checked
    p2p=NETWORKS[network][3]
    for name,content in render_profile(checked).items():
        path=ETC/name[4:] if name.startswith('etc/') else pathlib.Path('/etc/systemd/system')/('justverify-'+name[8:].removesuffix('-profile.conf')+'.service.d/20-profile.conf')
        atomic(path,content.decode())
    # Keep existing Tor identities; only the selected chain's P2P target changes.
    tor=(ETC/'torrc').read_text()
    old_tor=tor
    tor=re.sub(r'(?m)^HiddenServicePort 8333 127\.0\.0\.1:[0-9]+$',f'HiddenServicePort 8333 127.0.0.1:{p2p+1}',tor)
    atomic(ETC/'torrc',tor)
    system('daemon-reload')
    system('reset-failed',*UNITS)
    uuid=subprocess.run(['/usr/bin/findmnt','-n','-o','UUID','--target',str(DATA)],check=True,capture_output=True,text=True,timeout=10).stdout.strip()
    if not uuid:raise ValueError('selected volume has no UUID')
    ready={'schema':1,'uuid':uuid,'instance':json.loads((folder/'instance.json').read_text()),'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'configs':{name:hashlib.sha256((ETC/name).read_bytes()).hexdigest() for name in ('bitcoin.conf','electrs.toml','profile.json')}}
    atomic(ETC/'node-ready.json',json.dumps(ready)+'\n')
    system('start','justverify-i2p')
    system('start','justverify-core','justverify-electrs','justverify-manager','justverify-policy','justverify-electrum-tls',*EXPLORER_UNITS)
    if tor!=old_tor:system('reload-or-restart','justverify-tor')

def main():
    if os.geteuid()!=0 or len(sys.argv)!=1:raise ValueError('root fixed helper requires no arguments')
    raw=sys.stdin.buffer.read(4097)
    if len(raw)>4096:raise ValueError('request too large')
    request=json.loads(raw)
    if request=={'action':'check_initial'}:
        check_initial();print(json.dumps({'ok':True}));return
    if not os.path.ismount(DATA):raise ValueError('required data mount is absent')
    checked=validate(request)
    system('stop',*UNITS)
    if checked is not None:activate(checked)
    print(json.dumps({'ok':True}))
if __name__=='__main__':
    try:main()
    except Exception as error:
        # Paths/credentials from OS or RPC exceptions must not escape the helper.
        print(json.dumps({'ok':False,'error':type(error).__name__}));sys.exit(1)
