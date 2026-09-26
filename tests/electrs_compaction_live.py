#!/usr/bin/env python3
"""Real initial compaction, queued blocks, and persistent wallet RPC on isolated regtest."""
import argparse,json,os,pathlib,signal,socket,subprocess,sys,tempfile,threading,time
sys.dont_write_bytecode=True
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from electrs_service import supervise, Phase
from electrs_compaction import CompactionProgress, FAMILIES
from mempool_service import ElectrumProbe
parser=argparse.ArgumentParser();parser.add_argument('--core',type=pathlib.Path);parser.add_argument('--electrs',type=pathlib.Path);parser.add_argument('--worker',type=pathlib.Path);args=parser.parse_args()
if args.worker:
    config=json.loads(args.worker.read_text())
    raise SystemExit(supervise(config['command'],config['port'],pathlib.Path(config['status']),pathlib.Path(config['log']),config['metrics_port']))
def port():
    with socket.socket() as stream:stream.bind(('127.0.0.1',0));return stream.getsockname()[1]
def wait(check,seconds=90):
    until=time.monotonic()+seconds
    while time.monotonic()<until:
        try:
            value=check()
            if value:return value
        except (OSError,ValueError,RuntimeError,KeyError):pass
        time.sleep(.05)
    raise AssertionError('Real compaction checkpoint not reached')
processes=[];paused=None;phases=[];held=threading.Event();fault=[]
rpc,p2p,ep,mp=[port() for _ in range(4)]
with tempfile.TemporaryDirectory(prefix='jv-compaction-',dir='/var/tmp') as tmp:
    root=pathlib.Path(tmp);(root/'core').mkdir();status=root/'status.json'
    def cli(*values):
        result=subprocess.run([str(args.core/'bitcoin-cli'),'-regtest','-datadir='+str(root/'core'),'-rpcport='+str(rpc),*map(str,values)],capture_output=True,text=True,timeout=120)
        if result.returncode:raise RuntimeError('Core RPC failed')
        try:return json.loads(result.stdout)
        except ValueError:return result.stdout.strip()
    def read():return json.loads(status.read_text())
    def consume(worker):
        global paused
        for line in worker.stdout:
            value=json.loads(line);phases.append(value)
            if value['electrs_phase']=='compacting' and not held.is_set():
                try:
                    paused=read()['pid']
                    # Stop only the disposable real process, before its initial
                    # compaction finishes. Mine while it is stopped, then resume.
                    os.kill(paused,signal.SIGSTOP);held.set()
                except Exception as error:fault.append(type(error).__name__);held.set()
    probe=None
    try:
        core=subprocess.Popen([str(args.core/'bitcoind'),'-regtest','-server','-datadir='+str(root/'core'),'-rpcport='+str(rpc),'-port='+str(p2p),'-bind=127.0.0.1','-connect=0','-dnsseed=0','-dbcache=128'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);processes.append(core)
        wait(lambda:cli('getblockchaininfo'))
        descriptor=cli('getdescriptorinfo','raw(51)')['descriptor']
        # A long rapid regtest chain advances median time. Keep mock time
        # moving between batches, with every block still before wall time.
        start_time=int(time.time())-100000
        for batch in range(100):
            cli('setmocktime',start_time+batch*1000)
            cli('generatetodescriptor',500,descriptor)
            if (batch+1)%10==0:
                print(json.dumps({'checkpoint':'isolated regtest generated','height':(batch+1)*500}),flush=True)
        cli('setmocktime',0)
        assert cli('getblockcount')==50000
        # Include real spends so the final spending family has nonzero work.
        spends=[]
        for height in range(1,51):
            coinbase=cli('getblock',cli('getblockhash',height),2)['tx'][0]
            amount=int(coinbase['vout'][0]['value']*100000000)-1000
            raw='02000000'+'01'+bytes.fromhex(coinbase['txid'])[::-1].hex()+'00000000'+'00'+'ffffffff'+'01'+amount.to_bytes(8,'little').hex()+'0151'+'00000000'
            spends.append(raw)
        # These OP_TRUE fixtures are consensus-valid but nonstandard relay
        # transactions. Put them into a real regtest block without relaxing
        # the node's relay policy; this test measures index accounting.
        spend_block=cli('generateblock',descriptor,json.dumps(spends))
        assert len(cli('getblock',spend_block['hash'],2)['tx'])==51
        initial_height=50001
        # Keep actual DB phase events, without queuing thousands of indexing
        # log lines ahead of the short fault-injection boundary. Indexing and
        # readiness are still verified from the real protocol and database.
        command=[str(args.electrs),'--skip-default-conf-files','--network=regtest','--daemon-dir='+str(root/'core'),'--db-dir='+str(root/'index'),'--daemon-rpc-addr=127.0.0.1:'+str(rpc),'--daemon-p2p-addr=127.0.0.1:'+str(p2p),'--electrum-rpc-addr=127.0.0.1:'+str(ep),'--monitoring-addr=127.0.0.1:'+str(mp),'--log-filters=ERROR,electrs::db=DEBUG']
        db_log=root/'index/regtest/LOG'
        config=root/'worker.json';config.write_text(json.dumps({'command':command,'port':ep,'status':str(status),'log':str(db_log),'metrics_port':mp}))
        worker=subprocess.Popen([sys.executable,'-B',__file__,'--worker',str(config)],stdout=subprocess.PIPE,text=True,stderr=subprocess.DEVNULL);processes.append(worker)
        reader=threading.Thread(target=consume,args=(worker,),daemon=True);reader.start()
        assert held.wait(120),'Initial compaction was not observed';assert not fault,fault
        time.sleep(.3)
        assert not any(p['electrs_phase']=='catching_up' for p in phases),'Compaction completed before fault boundary; test invalid'
        assert read()['phase']=='compacting' and read()['running']
        before_identity=(root/'index/regtest/IDENTITY').read_bytes()
        cli('generatetodescriptor',2,descriptor)
        assert cli('getblockcount')==initial_height+2
        probe=ElectrumProbe(ep)
        try:probe.poll()
        except TimeoutError:pass
        else:raise AssertionError('Paused indexer unexpectedly answered')
        connection=probe.sock;pending=probe.pending
        try:probe.poll()
        except TimeoutError:pass
        assert probe.sock is connection and probe.pending is pending
        os.kill(paused,signal.SIGCONT);paused=None
        current=wait(lambda:(value if value['ready'] and value['height']==initial_height+2 else None) if (value:=probe.poll()) else None)
        assert current['tip']==cli('getbestblockhash')
        assert (root/'index/regtest/IDENTITY').read_bytes()==before_identity
        assert probe.sock is connection,'Pending wallet connection was unnecessarily replaced'
        cli('generatetodescriptor',1,descriptor)
        current=wait(lambda:(value if value['ready'] and value['height']==initial_height+3 else None) if (value:=probe.poll()) else None)
        assert current['tip']==cli('getbestblockhash')
        assert worker.poll() is None and read()['running']
        wait(lambda:(read().get('compaction_progress') or {}).get('complete'))
        worker.terminate();assert worker.wait(timeout=30)==0;reader.join(timeout=2)
        assert any(p['electrs_phase']=='catching_up' for p in phases)
        probe.close();probe=None
        # A second real index on the same fixed chain tests the observer without
        # SIGSTOP. A stopped process cannot answer metrics, and these small DB
        # compactions finish too quickly to add an HTTP round trip before pause.
        db_log=root/'progress-index/regtest/LOG'
        command=[arg.replace('--db-dir='+str(root/'index'),'--db-dir='+str(root/'progress-index')) for arg in command]
        config.write_text(json.dumps({'command':command,'port':ep,'status':str(status),'log':str(db_log),'metrics_port':mp}))
        # A tiny initial DB can compact by moving its one SST per family,
        # without writing output tables. Preserve the first real flush, stop
        # only this disposable process, and add real spends before reopening.
        # This creates overlapping SSTs and exercises actual merge output in
        # all three transaction families, without changing RocksDB settings.
        held.clear();phases.clear();fault.clear()
        worker=subprocess.Popen([sys.executable,'-B',__file__,'--worker',str(config)],stdout=subprocess.PIPE,text=True,stderr=subprocess.DEVNULL);processes.append(worker)
        reader=threading.Thread(target=consume,args=(worker,),daemon=True);reader.start()
        assert held.wait(120) and not fault
        time.sleep(.3)
        assert read()['phase']=='compacting' and not any(p['electrs_phase']=='catching_up' for p in phases)
        progress_identity=(root/'progress-index/regtest/IDENTITY').read_bytes()
        os.kill(paused,signal.SIGKILL);paused=None
        assert worker.wait(timeout=30)==1;reader.join(timeout=2)
        extra=[]
        for height in range(51,101):
            coinbase=cli('getblock',cli('getblockhash',height),2)['tx'][0]
            amount=int(coinbase['vout'][0]['value']*100000000)-1000
            extra.append('02000000'+'01'+bytes.fromhex(coinbase['txid'])[::-1].hex()+'00000000'+'00'+'ffffffff'+'01'+amount.to_bytes(8,'little').hex()+'0151'+'00000000')
        extra_block=cli('generateblock',descriptor,json.dumps(extra))
        assert len(cli('getblock',extra_block['hash'],2)['tx'])==51
        accounting_height=initial_height+4
        assert cli('getblockcount')==accounting_height
        accounting_live=CompactionProgress(db_log,mp);measurements=[];measurement_fault=[]
        def measure(actual):
            for line in actual.stdout:
                value=json.loads(line)
                if value['electrs_phase']=='compacting':
                    phase=Phase();phase.stage='compacting';phase.compaction=value['compaction']
                    try:
                        if result:=accounting_live.snapshot(phase):measurements.append(result)
                    except Exception as error:measurement_fault.append(type(error).__name__)
        worker=subprocess.Popen([sys.executable,'-B',__file__,'--worker',str(config)],stdout=subprocess.PIPE,text=True,stderr=subprocess.DEVNULL);processes.append(worker)
        reader=threading.Thread(target=measure,args=(worker,),daemon=True);reader.start()
        probe=ElectrumProbe(ep)
        wait(lambda:(value if value['ready'] and value['height']==accounting_height and value['tip']==cli('getbestblockhash') else None) if (value:=probe.poll()) else None)
        assert (root/'progress-index/regtest/IDENTITY').read_bytes()==progress_identity
        wait(lambda:(read().get('compaction_progress') or {}).get('complete'))
        worker.terminate();assert worker.wait(timeout=30)==0;reader.join(timeout=2)
        assert measurements and not measurement_fault,measurement_fault
        counts=accounting_live.counts
        assert counts['spending']>0
        assert all(m['basis']=='estimated_records' and not m['complete'] and m['total_records']==sum(counts.values()) for m in measurements)
        # Replay actual table-completion events against the fixed real metrics
        # captured by the observer at its first compaction notification.
        accounting=CompactionProgress(root/'not-created',mp);accounting.counts=counts
        points=[];families=set()
        for line in db_log.read_text().splitlines():
            if 'EVENT_LOG_v1 ' not in line:continue
            event=json.loads(line.split('EVENT_LOG_v1 ',1)[1])
            manual=event.get('job') in accounting.jobs
            accounting.observe(line)
            if manual and event.get('event')=='table_file_creation':
                family=event['cf_name'];families.add(family)
                points.append(accounting.estimate(family)['percent_basis_points'])
        assert {'txid','funding','spending'}<=families and len(set(points))>1
        assert points==sorted(points) and all(0<=p<10000 for p in points)
        print(json.dumps({'status':'PASS','core':cli('getnetworkinfo')['subversion'],'electrs':subprocess.check_output([str(args.electrs),'--version'],text=True).strip(),'indexed_height':current['height'],'accounting_index_height':accounting_height,'db_progress_basis_points':points,'db_input_estimates':counts,'checks':['actual initial compaction observed before completion','actual weighted record estimates across transaction, funding and spending families','monotonic whole-DB progress from real output events; no early 100 percent','two real blocks mined while first compaction paused','pending wallet RPC retains one socket','same process catches up to Core after compaction','new block after readiness indexed without restart','same index identity preserved','separate disposable index reopened after interrupted first compaction; real additional spends force merged output tables'],'limitation':'SIGSTOP controls ordering and SIGKILL prepares overlapping real SSTs only on isolated regtest; does not measure mainnet compaction duration or storage reliability'}),flush=True)
    finally:
        if paused:
            os.kill(paused,signal.SIGCONT)
        if probe:probe.close()
        for child in reversed(processes):
            if child.poll() is None:
                child.terminate()
                try:child.wait(timeout=30)
                except subprocess.TimeoutExpired:child.kill();child.wait()
