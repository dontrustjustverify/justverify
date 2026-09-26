#!/usr/bin/env python3
"""Nonprivileged indexer supervisor with bounded, credential-free phase reporting."""
import json,os,pathlib,queue,re,resource,signal,subprocess,threading,time,tomllib
from electrs_compaction import CompactionProgress


class Phase:
    def __init__(self):
        self.stage='starting';self.compaction=None;self.listener_error=False
        self.resource_error=False;self.compacted=False

    def observe(self,line):
        entry=re.match(r'^\[[^\]\n]+\s+(?:INFO|DEBUG|WARN|ERROR)\s+electrs::(db|index|thread)\] (.*)$',line)
        if not entry:return
        module,line=entry.groups()
        match=re.fullmatch(r'starting (config|headers|txid|funding|spending) compaction',line) if module=='db' else None
        if match:self.stage='compacting';self.compaction=match[1]
        elif module=='db' and line in ('finished full compaction','auto-compactions enabled'):
            self.stage='catching_up';self.compaction=None;self.compacted=True
        elif module=='index' and re.search(r'indexing \d+ blocks: \[\d+\.\.\d+\]',line):self.stage='indexing'
        if module=='thread' and line.startswith('accept_loop thread failed: failed to accept'):self.listener_error=True
        if module=='thread' and 'Too many open files (os error 24)' in line:self.resource_error=True


def supervise(command,port,status,db_log=None,metrics_port=None):
    phase=Phase();events=queue.Queue(maxsize=128);stopping=False;recovery=False
    progress=CompactionProgress(db_log,metrics_port) if db_log is not None and metrics_port else None
    progress_value=None;progress_checked=0.0
    child=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    def stop(*_):
        nonlocal stopping
        stopping=True
        if child.poll() is None:child.send_signal(signal.SIGINT)
    original={sig:signal.signal(sig,stop) for sig in (signal.SIGINT,signal.SIGTERM)}
    def collect():
        while True:
            line=child.stdout.readline(8193)
            if not line:break
            # Never copy raw configuration, authentication or paths into status/journal.
            if len(line)<=8192:events.put(line.decode('utf-8','replace'))
        events.put(None)
    threading.Thread(target=collect,daemon=True).start()
    status.parent.mkdir(mode=0o750,parents=True,exist_ok=True)
    def publish(running):
        nonlocal progress_value,progress_checked
        if progress and time.monotonic()-progress_checked>=2:
            progress_value=progress.snapshot(phase);progress_checked=time.monotonic()
        value={'updated':int(time.time()),'pid':child.pid,'port':port,'running':running,
            'phase':phase.stage,'compaction':phase.compaction,'listener_error':phase.listener_error,
            'resource_error':phase.resource_error,'recovery_pending':recovery,
            'compacted':phase.compacted,'compaction_progress':progress_value,
            'nofile_soft':resource.getrlimit(resource.RLIMIT_NOFILE)[0]}
        temporary=status.with_suffix('.tmp');temporary.write_text(json.dumps(value)+'\n')
        temporary.chmod(0o640);temporary.replace(status)
    try:
        publish(True)
        drained=False
        while child.poll() is None or not drained:
            previous=(phase.stage,phase.compaction,phase.listener_error,phase.resource_error)
            try:
                line=events.get(timeout=1)
                if line is None:drained=True
                else:phase.observe(line)
            except queue.Empty:pass
            current=(phase.stage,phase.compaction,phase.listener_error,phase.resource_error)
            if previous!=current:print(json.dumps({'electrs_phase':phase.stage,'compaction':phase.compaction,'listener_error':phase.listener_error,'resource_error':phase.resource_error}),flush=True)
            # Never interrupt a first full compaction to recover a dead listener.
            # Once it has finished, a normal signal lets the pinned binary flush
            # and exit; systemd retries without deleting or rebuilding its DB.
            if child.poll() is None and phase.listener_error and phase.compacted and phase.stage!='compacting' and not stopping:
                recovery=True;stop()
            publish(child.poll() is None)
        phase.stage='stopped' if stopping else 'failed';publish(False)
        # Upstream can return zero after losing Core; an unsolicited exit still
        # needs systemd recovery. Explicit service stops remain successful.
        return 1 if recovery or not stopping else 0
    finally:
        if child.poll() is None:
            child.send_signal(signal.SIGINT);child.wait()
        child.stdout.close()
        for sig,handler in original.items():signal.signal(sig,handler)


def main():
    if os.geteuid()==0:raise SystemExit('Electrs must run without root privileges')
    conf=pathlib.Path('/etc/justverify/electrs.toml')
    config=tomllib.loads(conf.read_text());address=config['electrum_rpc_addr']
    if address!='127.0.0.1:50003':raise SystemExit('Unexpected internal Electrum endpoint')
    if config['monitoring_addr']!='127.0.0.1:4224':raise SystemExit('Unexpected metrics endpoint')
    if config['network'] not in ('bitcoin','testnet','testnet4','signet','regtest'):raise SystemExit('Unexpected index network')
    log=pathlib.Path(config['db_dir'])/config['network']/'LOG'
    raise SystemExit(supervise(['/opt/justverify/bin/electrs','--skip-default-conf-files','--conf',str(conf),'--log-filters=INFO,electrs::db=DEBUG'],50003,pathlib.Path('/run/justverify-electrs/status.json'),log,4224))


if __name__=='__main__':main()
