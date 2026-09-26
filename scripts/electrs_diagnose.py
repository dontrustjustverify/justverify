#!/usr/bin/env python3
"""Bounded read-only appliance index diagnosis; never prints credentials or paths."""
import argparse,base64,collections,json,os,pathlib,re,socket,subprocess,time,tomllib,urllib.request
P=pathlib.Path

def command(*args):
    result=subprocess.run(args,capture_output=True,text=True,timeout=10)
    if result.returncode:raise RuntimeError('Command unavailable')
    return result.stdout

def capture(fn):
    try:return fn()
    except (OSError,ValueError,KeyError,TypeError,RuntimeError,subprocess.SubprocessError) as e:
        return {'unavailable':type(e).__name__}

def process(pid):
    root=P('/proc')/str(pid)
    # The configured upstream executable, never a caller-provided process/path.
    if (root/'exe').resolve()!=P('/opt/justverify/bin/electrs'):raise ValueError('Unexpected process')
    stat=(root/'stat').read_text().rsplit(')',1)[1].split()
    io={k:int(v) for line in (root/'io').read_text().splitlines() for k,v in [line.split(':',1)]}
    limits=next(line.split() for line in (root/'limits').read_text().splitlines() if line.startswith('Max open files'))
    sockets=[]
    for descriptor in (root/'fd').iterdir():
        try:
            match=re.fullmatch(r'socket:\[(\d+)\]',str(descriptor.readlink()))
            if match:sockets.append(match[1])
        except FileNotFoundError:pass
    states=collections.Counter();listen=[]
    for protocol in ('tcp','tcp6'):
        for line in (root/'net'/protocol).read_text().splitlines()[1:]:
            fields=line.split()
            if fields[9] in sockets:
                states[{'01':'ESTABLISHED','08':'CLOSE_WAIT','0A':'LISTEN'}.get(fields[3],'OTHER')]+=1
                if fields[3]=='0A':listen.append(int(fields[1].rsplit(':',1)[1],16))
    return {'pid':pid,'state':stat[0],'cpu_ticks':int(stat[11])+int(stat[12]),
        'read_bytes':io['read_bytes'],'write_bytes':io['write_bytes'],
        'fd_count':len(list((root/'fd').iterdir())),'socket_descriptors':len(sockets),
        'socket_states':dict(states),'listening_ports':sorted(listen),'nofile':limits[3:5],
        'rss_kib':int(stat[21])*os.sysconf('SC_PAGE_SIZE')//1024}

def runtime():
    value=json.loads(P('/run/justverify-electrs/status.json').read_text())
    keys=('updated','pid','port','running','phase','compaction','listener_error','resource_error','recovery_pending','nofile_soft')
    return {k:value.get(k) for k in keys}

def core():
    profile=json.loads(P('/etc/justverify/profile.json').read_text())
    cookie=P(profile['cookie']).read_bytes().strip()
    request=urllib.request.Request('http://127.0.0.1:'+str(int(profile['rpc_port'])),json.dumps({'id':1,'method':'getblockchaininfo','params':[]}).encode(),{'Authorization':'Basic '+base64.b64encode(cookie).decode(),'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=5) as response:value=json.load(response)['result']
    return {k:value[k] for k in ('blocks','headers','bestblockhash','initialblockdownload')}

def phase_events():
    raw=command('journalctl','-u','justverify-electrs','-b','-n','80','-o','json','--no-pager','--quiet')
    events=[]
    for line in raw.splitlines():
        row=json.loads(line);message=row.get('MESSAGE','')
        try:phase=json.loads(message)
        except (TypeError,ValueError):continue
        if not isinstance(phase,dict):continue
        if phase.get('electrs_phase') in ('starting','indexing','compacting','catching_up','failed','stopped'):
            events.append({'at':int(row['__REALTIME_TIMESTAMP'])//1000000,**{k:phase[k] for k in ('electrs_phase','compaction','listener_error','resource_error') if k in phase}})
    return events

def db_log():
    config=tomllib.loads(P('/etc/justverify/electrs.toml').read_text())
    folder={'bitcoin':'bitcoin','testnet':'testnet','testnet4':'testnet4','regtest':'regtest','signet':'signet'}[config['network']]
    path=P(config['db_dir'])/folder/'LOG'
    with path.open('rb') as f:
        f.seek(max(0,path.stat().st_size-65536));lines=f.read(65536).decode('utf-8','replace').splitlines()
    events=[]
    for line in lines:
        kinds=[key for key,pattern in {'compaction_start':r'Compacting|compaction_started','compaction_end':r'compaction_finished|Compacted','table_created':r'"event"\s*:\s*"table_file_creation"','flush':r'flush_finished','error':r'\bERROR\b|IO error|Corruption'}.items() if re.search(pattern,line,re.I)]
        if kinds:
            stamp=re.match(r'^(\d{4}/\d{2}/\d{2}-\d{2}:\d{2}:\d{2})',line)
            cf=re.search(r'\[(config|headers|txid|funding|spending)\]',line)
            event={'time':stamp[1] if stamp else None,'column':cf[1] if cf else None,'events':kinds}
            if 'EVENT_LOG_v1' in line:
                try:details=json.loads(line.split('EVENT_LOG_v1',1)[1].strip())
                except ValueError:details={}
                if isinstance(details,dict):
                    # Completed SST outputs prove work beyond a live process or
                    # a log timestamp. They do not measure total completion %.
                    for key in ('time_micros','job','file_number','file_size','input_data_size'):
                        if type(details.get(key)) is int and details[key]>=0:event[key]=details[key]
                    if details.get('cf_name') in ('config','headers','txid','funding','spending'):event['column']=details['cf_name']
            events.append(event)
    return {'mtime':int(path.stat().st_mtime),'tail_bytes':min(65536,path.stat().st_size),'events':events[-20:]}

def kernel_errors():
    raw=command('journalctl','-k','-b','-n','2000','-o','json','--no-pager','--quiet')
    events=[]
    for line in raw.splitlines():
        row=json.loads(line);msg=row.get('MESSAGE','')
        kinds=[k for k,pattern in {'nvme_timeout':r'nvme.*timeout','io_error':r'I/O error','controller_reset':r'reset controller|resetting controller','out_of_memory':r'Out of memory|oom-kill','pcie_error':r'AER:.*(?:error|fatal)|PCIe Bus Error','filesystem_error':r'EXT4-fs error'}.items() if re.search(pattern,msg,re.I)]
        if kinds:events.append({'at':int(row['__REALTIME_TIMESTAMP'])//1000000,'events':kinds})
    return {'bounded_last_events':events,'journal_rows':len(raw.splitlines()),'visibility':'root' if os.geteuid()==0 else 'may be permission limited'}

def storage():
    links=[]
    for entry in P('/sys/bus/pci/devices').iterdir():
        item={}
        for name in ('current_link_speed','current_link_width','max_link_speed','max_link_width'):
            path=entry/name
            if path.exists():item[name]=path.read_text().strip()
        if item:links.append(item)
    memory={line.split(':')[0]:line.split(':')[1].strip() for line in P('/proc/meminfo').read_text().splitlines() if line.startswith(('MemAvailable:','SwapTotal:','SwapFree:','Dirty:','Writeback:'))}
    return {'pcie_links':links,'nvme_power_latency_us':capture(lambda:int(P('/sys/module/nvme_core/parameters/default_ps_max_latency_us').read_text())),
        'cpu_throttled':capture(lambda:command('vcgencmd','get_throttled').strip()),'memory':memory}

def electrum():
    start=time.monotonic();replies=[];buf=b''
    try:
        with socket.create_connection(('127.0.0.1',50003),timeout=2) as stream:
            stream.sendall(b'{"id":1,"method":"blockchain.headers.subscribe","params":[]}\n{"id":2,"method":"server.ping","params":[]}\n')
            while len(replies)<2 and len(buf)<16384:
                remaining=8-(time.monotonic()-start)
                if remaining<=0:break
                stream.settimeout(remaining);part=stream.recv(4096)
                if not part:break
                buf+=part
                while b'\n' in buf:
                    line,buf=buf.split(b'\n',1);value=json.loads(line)
                    if value.get('id')==1:replies.append({'id':1,'height':value.get('result',{}).get('height'),'error_code':(value.get('error') or {}).get('code')})
                    if value.get('id')==2:replies.append({'id':2,'ping_ok':'result' in value and value['result'] is None,'error_code':(value.get('error') or {}).get('code')})
    except OSError as error:return {'error':type(error).__name__,'responses':replies,'seconds':round(time.monotonic()-start,2)}
    return {'responses':replies,'seconds':round(time.monotonic()-start,2)}

def sample():
    state=capture(runtime)
    return {'at':int(time.time()),'core':capture(core),'runtime':state,'upstream':capture(lambda:process(int(state['pid']))),'db_log':capture(db_log)}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--interval',type=int,default=30,choices=range(10,61));args=parser.parse_args()
    first=sample();time.sleep(args.interval);second=sample()
    a,b=first['upstream'],second['upstream'];delta=None
    if a.get('pid') and a.get('pid')==b.get('pid'):
        delta={k:b[k]-a[k] for k in ('cpu_ticks','read_bytes','write_bytes')}
    services={}
    for service in ('core','electrs','mempool'):
        services[service]=capture(lambda service=service:dict(line.split('=',1) for line in command('systemctl','show','justverify-'+service,'--property=ActiveState,SubState,NRestarts,ActiveEnterTimestamp').strip().splitlines()))
    wallet={'not_run':'Initial compaction active; avoid adding a waiting connection'} if second['runtime'].get('phase')=='compacting' else capture(electrum)
    report={'scope':'read-only; no files, configuration or services changed','version':capture(lambda:json.loads(P('/etc/justverify/os-release.json').read_text())['version']),
        'samples':[first,second],'same_process_deltas':delta,'services':services,'phase_events':capture(phase_events),'kernel_errors':capture(kernel_errors),'storage':capture(storage),'electrum':wallet}
    print(json.dumps(report,indent=2),flush=True)
if __name__=='__main__':main()
