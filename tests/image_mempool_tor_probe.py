#!/usr/bin/env python3
"""Packaged Tor explorer listeners across two disposable generic ARM boots.

Checks actual loopback routing, not public Tor transport; mempool_tor_live.py
tests that transport separately. Never run on a physical node.
"""
import asyncio,base64,hashlib,json,os,secrets,ssl,subprocess,sys,time
from pathlib import Path
import aiohttp

STATE=Path('/var/lib/jv-mempool-image-probe')
REPORT={'status':'FAIL','environment':'QEMU virt with external Debian kernel; physical Pi NOT RUN','checks':[]}

async def main():
    assert subprocess.check_output(['systemd-detect-virt','--vm'],text=True).strip()=='qemu'
    STATE.mkdir(mode=0o700,exist_ok=True)
    checkpoint=STATE/'checkpoint.json'
    previous=json.loads(checkpoint.read_text()) if checkpoint.exists() else None
    REPORT['boot']='second' if previous else 'first'
    password=previous['password'] if previous else secrets.token_urlsafe(32)
    boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    expected_version=sys.argv[1] if len(sys.argv)==2 else '0.1.0-beta9'
    assert json.loads(Path('/etc/justverify/os-release.json').read_text())['version']==expected_version
    assert subprocess.check_output(['/opt/justverify/bin/justverify','--version'],text=True).strip()=='justverify '+expected_version
    assert 'HiddenServicePort 3006 127.0.0.1:28445' in Path('/etc/justverify/torrc').read_text()
    assert 'HiddenServicePort 50001 127.0.0.1:50001' in Path('/etc/justverify/torrc').read_text()
    if not previous:
        assert json.loads(Path('/etc/justverify/profile.json').read_text())['network']=='main'
        REPORT['checks'].append('factory profile defaults to mainnet before isolated regtest selection')
    async def wait(check,seconds=120):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            try:
                value=await check()
                if value:return value
            except (OSError,ValueError,KeyError,aiohttp.ClientError):pass
            await asyncio.sleep(.5)
        raise TimeoutError('Packaged service readiness deadline')
    async with aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True),timeout=aiohttp.ClientTimeout(total=120)) as c:
        payload={'password':password}
        if not previous:payload['setup_token']=Path('/var/lib/justverify/web/setup-token').read_text().strip()
        async with c.post('http://127.0.0.1/login',headers={'Origin':'http://127.0.0.1'},json=payload) as r:
            assert r.status==200;csrf=(await r.json())['csrf']
        async def post(path,body):
            async with c.post('http://127.0.0.1'+path,headers={'Origin':'http://127.0.0.1','X-CSRF-Token':csrf},json=body) as r:
                assert r.status==200,(path,r.status)
                return await r.json()
        if expected_version in ('0.1.0-beta10-test5','0.1.0','0.1.1','0.1.2'):
            saved_rain={'enabled':True,'brightness':100,'speed':400,'density':300} if expected_version in ('0.1.0','0.1.1','0.1.2') else {'enabled':True,'brightness':26,'speed':110,'density':95}
            preferences=(await post('/device-settings',{'action':'state'}))['preferences']
            assert preferences['schema']==2
            if previous:
                assert preferences['background']==saved_rain
                REPORT['checks'].append('Digital Rain values survive actual VM reboot')
            else:
                assert preferences['background']==({'enabled':False,'brightness':40,'speed':160,'density':140} if expected_version in ('0.1.0','0.1.1','0.1.2') else {'enabled':False,'brightness':18,'speed':70,'density':75})
                saved=await post('/device-settings',{'action':'background','background':saved_rain})
                assert saved['preferences']['background']==saved_rain
                assert saved['preferences']['language']==preferences['language']
                REPORT['checks'].append('factory Digital Rain off; authenticated save preserves language')
            async with c.get('http://127.0.0.1/genesis-rain.js') as r:
                assert r.status==200 and await r.read()==Path('/opt/justverify/web/static/genesis-rain.js').read_bytes()
            REPORT['checks'].append('packaged Digital Rain asset is served intact')
        if not previous:
            assert (await post('/storage',{'action':'prepare_profile'}))['ok']
            review=await post('/versions',{'method':'preview','version':'31.1','network':'regtest','watch_only':False})
            assert (await post('/versions',{'method':'apply','token':review['token']}))['phase']=='committed'
        config=json.loads(Path('/etc/justverify/profile.json').read_text());assert config['network']=='regtest'
        async def rpc(method,params=None):
            cookie=Path(config['cookie']).read_bytes().strip()
            async with c.post('http://127.0.0.1:'+str(config['rpc_port']),headers={'Authorization':'Basic '+base64.b64encode(cookie).decode()},json={'id':1,'method':method,'params':params or []}) as r:
                value=await r.json();assert not value.get('error'),method
                return value['result']
        if expected_version=='0.1.2':
            factory=await post('/policy',{'method':'state'})
            assert factory['requested']['listen']=='none'
            assert factory['requested']['onlynet']=='i2p,ipv4,ipv6,onion'
            for key in ('listen','onlynet'):
                entry=next(e for e in factory['entries'] if e['key']==key)
                assert entry['installation_default']==factory['requested'][key]
            info=await rpc('getnetworkinfo')
            assert not any(a['address'].endswith('.onion') for a in info['localaddresses'])
            assert next(n for n in info['networks'] if n['name']=='i2p')['reachable']
            assert subprocess.check_output(['systemctl','is-active','justverify-i2p'],text=True).strip()=='active'
            router_pid=subprocess.check_output(['systemctl','show','justverify-i2p','-p','MainPID','--value'],text=True).strip()
            assert int(router_pid)>0
            assert subprocess.check_output(['systemctl','show','justverify-i2p','-p','NRestarts','--value'],text=True).strip()=='0'
            policy_text=Path(config['managed_config']).read_text()
            assert 'i2pacceptincoming=0' in policy_text
            assert 'bind=0.0.0.0:' not in policy_text and 'bind=[::]:' not in policy_text
            assert not any(line.startswith('bind=') and line.endswith('=onion') for line in policy_text.splitlines())
            REPORT['checks'].append('new incoming-none/outgoing-all policy, no onion announcement, I2P router active with incoming disabled; retained across reboot')
        if expected_version=='0.1.1':
            announced=Path('/run/justverify-tor/p2p.hostname').read_text().strip()
            info=await rpc('getnetworkinfo')
            assert any(a['address']==announced and a['port']==8333 for a in info['localaddresses'])
            pid=int(subprocess.check_output(['systemctl','show','justverify-core','--property=MainPID','--value'],text=True))
            assert Path(f'/proc/{pid}/exe').resolve()==Path(config['binary']).resolve()
            assert b'-externalip='+announced.encode()+b':8333' in Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0')
            REPORT['checks'].append('registered launcher execs selected Core and registers persistent P2P onion on both boots')
        if not previous:await rpc('generatetodescriptor',[2,'raw(51)'])
        tip=await rpc('getbestblockhash');height=await rpc('getblockcount')
        if previous:assert previous['boot_id']!=boot_id and previous['tip']==tip
        async def lan_ready():
            async with c.get('http://127.0.0.1:3006/api/blocks/tip/hash') as r:return r.status==200 and await r.text()==tip
        await wait(lan_ready,240)
        async def indexed():
            reader,writer=await asyncio.open_connection('127.0.0.1',50001)
            writer.write(b'{"id":1,"method":"blockchain.headers.subscribe","params":[]}\n');await writer.drain()
            header=json.loads(await asyncio.wait_for(reader.readline(),5))['result'];writer.close();await writer.wait_closed()
            return header['height']==height and hashlib.sha256(hashlib.sha256(bytes.fromhex(header['hex'])).digest()).digest()[::-1].hex()==tip
        await wait(indexed)
        async def dashboard():
            async with c.get('http://127.0.0.1/dashboard',headers={'X-CSRF-Token':csrf}) as r:
                assert r.status==200
                return await r.json()
        async def status_ready():
            value=await dashboard();index=value.get('host',{}).get('electrs',{})
            return index if index.get('wallet_ready') and index.get('height')==height and index.get('target_height')==height and index.get('tip')==tip else None
        current=await wait(status_ready)
        if expected_version=='0.1.2':
            # External reseed is deliberately blocked in this boot environment.
            # Exceed the former ten-second SAM startup deadline and establish
            # that real Core/electrs stay usable without restarting the router.
            await asyncio.sleep(12)
            assert subprocess.check_output(['systemctl','show','justverify-i2p','-p','MainPID','--value'],text=True).strip()==router_pid
            assert subprocess.check_output(['systemctl','show','justverify-i2p','-p','NRestarts','--value'],text=True).strip()=='0'
            assert await indexed()
            REPORT['checks'].append('fresh router bootstrap cannot block Core/electrs startup or trigger SAM timeout restart loops')
        if expected_version in ('0.1.1','0.1.2') and previous:
            original=(await post('/policy',{'method':'state'}))['requested']
            try:
                for incoming in ('none','clearnet','clearnet,tor'):
                    review=await post('/policy',{'method':'preview','values':{**original,'listen':incoming}})
                    assert (await post('/policy',{'method':'apply','token':review['token']}))['phase']=='committed'
                    addresses=(await rpc('getnetworkinfo'))['localaddresses']
                    assert any(a['address'].endswith('.onion') for a in addresses)==('tor' in incoming.split(','))
                    import socket
                    for address,family in [('127.0.0.1',socket.AF_INET),('::1',socket.AF_INET6)]:
                        with socket.socket(family) as peer:
                            peer.settimeout(2)
                            connected=peer.connect_ex((address,18444))==0
                            assert connected==(family==socket.AF_INET or 'clearnet' in incoming.split(','))
                    await wait(status_ready,60)
                    assert await rpc('getbestblockhash')==tip
            finally:
                review=await post('/policy',{'method':'preview','values':original})
                assert (await post('/policy',{'method':'apply','token':review['token']}))['phase']=='committed'
            await wait(status_ready,60)
            REPORT['checks'].append('authenticated peer selection apply: incoming off/dual-stack clearnet/Tor; onion advertisement removed/restored; electrs and chain preserved')
        if expected_version=='0.1.2' and previous:
            for key in ('listen','onlynet'):
                subprocess.run(['runuser','-u','justverify','--','env','PYTHONPATH=/opt/jv-test-modules','JV_POLICY_TEST_DEFAULT=1','JV_POLICY_TEST_KEY='+key,'/usr/bin/python3','-B','/opt/jv-peer-defaults-tui.py'],check=True,timeout=600)
            await wait(status_ready,60)
            REPORT['checks'].append('actual unprivileged PTY default-reset for incoming/outgoing: staged review, cancel, apply, observed Core state and original selection restored')
        assert not current['height_stale'] and not current['target_stale']
        if expected_version in ('0.1.0-beta10-test2','0.1.0-beta10-test3','0.1.0-beta10-test4','0.1.0-beta10-test5','0.1.1','0.1.2'):
            async def db_completed():
                value=await dashboard()
                return value.get('host',{}).get('electrs',{}).get('compaction_complete') is True
            await wait(db_completed)
            assert Path('/opt/justverify/scripts/electrs_compaction.py').is_file()
            REPORT['checks'].append('packaged DB progress observer and finalization completion after boot')
        async with c.get('http://127.0.0.1/electrs_status.js') as r:
            assert r.status==200 and 'progress' in await r.text()
        REPORT['checks'].append('packaged live Electrs metrics, exact progress heights, fresh matching tip and wallet readiness')
        identity=config['data_id']
        assert identity==Path(config['cookie']).parents[2].name
        assert Path('/srv/justverify/data/mempool/'+config['network']+'-'+identity+'/mysql/mysql').is_dir()
        for unit in ('core','electrs','electrum-tls'):
            assert 'RestartSec=30' in Path('/etc/systemd/system/justverify-'+unit+'.service').read_text()
        context=ssl.create_default_context(cafile='/var/lib/justverify/web/certificate.pem')
        for ip in ('127.0.0.1','::1'):
            async def tls_ready():
                reader,writer=await asyncio.open_connection(ip,50002,ssl=context,server_hostname='justverify.local')
                try:
                    writer.write(b'{"id":1,"method":"blockchain.headers.subscribe","params":[]}\n');await writer.drain()
                    response=json.loads(await asyncio.wait_for(reader.readline(),5))['result']
                    assert response['height']==height and hashlib.sha256(hashlib.sha256(bytes.fromhex(response['hex'])).digest()).digest()[::-1].hex()==tip
                    return True
                finally:writer.close();await writer.wait_closed()
            # Type=simple and cached dashboard readiness can precede the actual
            # wallet listener after settings restart. Require its real response.
            await wait(tls_ready,30)
        REPORT['checks'].append('packaged stable explorer identity, retry cadence and actual IPv4/IPv6 Electrum TLS headers')
        for ip in ('127.0.0.1','::1'):
            reader,writer=await asyncio.open_connection(ip,50001)
            writer.write(b'{"id":1,"method":"blockchain.headers.subscribe","params":[]}\n');await writer.drain()
            response=json.loads(await asyncio.wait_for(reader.readline(),5))['result']
            assert response['height']==height and hashlib.sha256(hashlib.sha256(bytes.fromhex(response['hex'])).digest()).digest()[::-1].hex()==tip
            writer.close();await writer.wait_closed()
        for query,tls in (('network=lan',False),('network=lan&transport=tls',True)):
            async with c.get('http://127.0.0.1/electrum?'+query,headers={'X-CSRF-Token':csrf}) as r:
                assert r.status==200;endpoint=await r.json()
                assert endpoint['payload']==('justverify.local:50002' if tls else 'justverify.local:50001')
                assert endpoint['tls']==tls and endpoint['service_active'] and endpoint['backend_active']
                assert bool(endpoint['certificate_sha256'])==tls
        assert 'electrum_rpc_addr = "127.0.0.1:50003"' in Path('/etc/justverify/electrs.toml').read_text()
        REPORT['checks'].append('packaged default LAN TCP50001 on both IP families, optional TLS50002 API/QR, fixed internal50003 and Tor50001 route')

        async def features(ip,port,tls=False):
            options={'ssl':context,'server_hostname':'justverify.local'} if tls else {}
            reader,writer=await asyncio.open_connection(ip,port,**options)
            writer.write(b'{"id":50003,"method":"server.features","params":[]}\n');await writer.drain()
            reply=json.loads(await asyncio.wait_for(reader.readline(),5))
            writer.close();await writer.wait_closed()
            assert reply['id']==50003 and not reply.get('error')
            return reply['result']
        upstream=await features('127.0.0.1',50003)
        assert upstream['hosts']=={'tcp_port':50003}
        expected_features=json.loads(json.dumps(upstream));expected_features['hosts']['tcp_port']=50001
        for ip in ('127.0.0.1','::1'):
            for port,tls in ((50001,False),(50002,True)):
                assert await features(ip,port,tls)==expected_features
        tor_line=next(line for line in Path('/etc/justverify/torrc').read_text().splitlines() if line.startswith('HiddenServicePort 50001 '))
        tor_host,tor_port=tor_line.split()[2].split(':')
        assert await features(tor_host,int(tor_port))==expected_features
        REPORT['checks'].append('packaged feature metadata: internal50003; IPv4/IPv6 TCP/TLS and Tor local destination advertise50001, IDs and other fields unchanged')

        policy=await post('/policy',{'method':'state'})
        assert policy['requested']['datacarrier']=='0' and policy['requested']['datacarriersize']=='83'
        assert (await rpc('getmempoolinfo'))['maxdatacarriersize']==0
        preview=await post('/policy',{'method':'preview_config','config':policy['config']+'\ndebug=mempoolrej\n'})
        assert preview['plan']['requested']['debug']=='mempoolrej'
        assert preview['preflight']['observed']['maxdatacarriersize']==0
        assert (await post('/policy',{'method':'state'}))['requested']==policy['requested']
        async def block_sizes():
            rows=(await dashboard()).get('rpc',{}).get('recentblocks',{}).get('value',[])
            return rows if rows and rows[0]['hash']==tip and all(row.get('size',0)>0 for row in rows) else None
        rows=await wait(block_sizes)
        for row in rows:assert row['size']==(await rpc('getblock',[row['hash'],1]))['size']
        for name,terms in [('dashboard.js',['CoreStatus','block-size','1000000']),('app.css',['--status-icon-size','prefers-reduced-motion','block-identity']),('settings.js',['preview_config','datacarrier'])]:
            async with c.get('http://127.0.0.1/'+name) as r:
                assert r.status==200;body=await r.text();assert all(term in body for term in terms)
        REPORT['checks'].append('beta6 factory data policy, real editor preflight, exact recent-block byte sizes and current status interface')

        async def address():return (await post('/device-settings',{'action':'state'}))['remote_web']['onion_host']
        host=await wait(address,60)
        async def toggle(enabled):
            review=await post('/device-settings',{'action':'tor_preview','enabled':enabled})
            return await post('/device-settings',{'action':'apply','token':review['token'],'password':password})
        if previous:
            assert previous['onion']==host
            assert (await post('/device-settings',{'action':'state'}))['remote_web']['running']
        else:assert (await toggle(True))['running']
        async def tor_login():
            async with c.post('http://127.0.0.1:28444/login',headers={'Host':host,'Origin':'http://'+host},json={'password':password}) as r:
                assert r.status==200;issued=r.cookies['jv_tor_session'].value
                # Keep explicit saved-cookie probes independent of the newest login.
                c.cookie_jar.clear(lambda cookie:cookie.key=='jv_tor_session')
                return issued
        token=previous['token'] if previous else await tor_login()
        headers={'Host':host+':3006','Origin':'http://'+host+':3006','Cookie':'jv_tor_session='+token}
        async def explorer(path,expected=200):
            async with c.get('http://127.0.0.1:28445'+path,headers=headers) as r:
                assert r.status==expected,(path,r.status)
                return await r.text()
        assert await explorer('/api/blocks/tip/hash')==tip
        assert '<app-root' in await explorer('/ko/')
        env=await explorer('/resources/config.js');assert host in env and '"NGINX_PORT": "3006"' in env
        async with c.ws_connect('http://127.0.0.1:28445/api/v1/ws',headers=headers) as ws:
            await ws.send_json({'action':'init'});await ws.send_json({'action':'want','data':['blocks']})
            found=False
            async with asyncio.timeout(30):
                async for message in ws:
                    if message.type==aiohttp.WSMsgType.TEXT:
                        data=json.loads(message.data)
                        if any(block['id']==tip for block in data.get('blocks',[])):
                            found=True;break
            assert found
        REPORT['checks']+=['packaged version and Tor mapping','actual Core/electrs/LAN explorer tip','Tor login shared by authenticated packaged explorer and real WebSocket']
        if expected_version in ('0.1.0-beta10-test3','0.1.0-beta10-test4','0.1.0-beta10-test5','0.1.1','0.1.2'):
            for _ in range(18):await tor_login()
            assert await explorer('/api/blocks/tip/hash')==tip
            async with c.get('http://127.0.0.1/sessions',headers={'X-CSRF-Token':csrf}) as r:
                assert r.status==200;listed=(await r.json())['sessions']
            assert len(listed)>16 and sum(s['current'] for s in listed)==1
            assert all(set(s)=={'id','created_at','last_seen_at','expires_at','browser','platform','current','connection'} for s in listed)
            extra_token=await tor_login()
            auth={'Host':host,'Origin':'http://'+host,'Cookie':'jv_tor_session='+extra_token}
            async with c.get('http://127.0.0.1:28444/session',headers=auth) as r:
                assert r.status==200;extra_csrf=(await r.json())['csrf']
            async with c.get('http://127.0.0.1:28444/sessions',headers={**auth,'X-CSRF-Token':extra_csrf}) as r:
                assert r.status==200;extra_id=next(s['id'] for s in (await r.json())['sessions'] if s['current'])
            async with c.ws_connect('http://127.0.0.1:28445/api/v1/ws',headers={**headers,'Cookie':'jv_tor_session='+extra_token}) as ws:
                result=await post('/sessions',{'action':'revoke','id':extra_id})
                assert result=={'revoked_count':1,'revoked_current':False}
                async with asyncio.timeout(10):
                    while True:
                        message=await ws.receive()
                        if message.type in (aiohttp.WSMsgType.CLOSE,aiohttp.WSMsgType.CLOSED):break
            async with c.get('http://127.0.0.1:28444/session',headers=auth) as r:assert r.status==401
            assert await explorer('/api/blocks/tip/hash')==tip
            REPORT['checks'].append('over16 actual logins preserve earlier browser; private device list and selective revocation close real explorer WebSocket')
        if not previous:
            subprocess.run(['systemctl','restart','justverify-web'],check=True)
            async def restored():return await explorer('/api/blocks/tip/hash')==tip
            await wait(restored,30)
            if expected_version in ('0.1.0-beta10-test5','0.1.0','0.1.1','0.1.2'):
                assert (await post('/device-settings',{'action':'state'}))['preferences']['background']==saved_rain
                REPORT['checks'].append('Digital Rain preferences survive real web service restart')
            REPORT['checks'].append('web systemd restart preserves Tor explorer login')
            with os.fdopen(os.open(checkpoint,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as f:
                json.dump({'password':password,'token':token,'onion':host,'tip':tip,'boot_id':boot_id},f)
        else:
            REPORT['checks'].append('real reboot preserves Tor identity/login, opt-in setting and three matching node tips')
            import signal
            supervisor=int(subprocess.check_output(['systemctl','show','justverify-electrs','--property=MainPID','--value'],text=True))
            assert supervisor>1
            children=Path(f'/proc/{supervisor}/task/{supervisor}/children').read_text().split()
            upstream=[int(child) for child in children if Path(f'/proc/{child}/exe').resolve()==Path('/opt/justverify/bin/electrs')]
            assert len(upstream)==1, 'Expected the packaged supervisor to own one actual electrs process'
            pid=upstream[0]
            limits=Path(f'/proc/{pid}/limits').read_text()
            open_files=next(line.split() for line in limits.splitlines() if line.startswith('Max open files'))
            assert open_files[3:5]==['65536','65536']
            REPORT['checks'].append('packaged supervisor owns actual electrs with FD soft/hard limits65536')
            os.kill(pid,signal.SIGSTOP)
            try:
                async def stale_index():
                    value=await dashboard();index=value.get('host',{}).get('electrs',{})
                    return index if index.get('height_stale') and not index.get('wallet_ready') and index.get('height_updated',time.time())<=time.time()-15 else None
                stale=await wait(stale_index,45)
                assert stale['height']==height and stale['target_height']==height
                assert stale['height_updated']<=time.time()-15
                await asyncio.sleep(3)
                retained=(await dashboard())['host']['electrs']
                assert retained['height_updated']==stale['height_updated'] and retained['height']==height
                assert retained['height_stale'] and not retained['wallet_ready']
            finally:os.kill(pid,signal.SIGCONT)
            await wait(status_ready,60)
            REPORT['checks'].append('actual packaged electrs pause preserves timestamped height; resume restores readiness')
            # Fresh client confirms the authenticated boundary without any cookie.
            async with aiohttp.ClientSession() as anonymous:
                async with anonymous.get('http://127.0.0.1:28445/api/mempool',headers={'Host':host+':3006'}) as r:assert r.status==401
            await toggle(False)
            for port in (28444,28445):
                try:reader,writer=await asyncio.open_connection('127.0.0.1',port)
                except OSError:continue
                writer.close();await writer.wait_closed();raise AssertionError('Disabled listener remains open')
            assert await lan_ready()
            REPORT['checks'].append('disable closes both Tor listeners while LAN explorer remains ready; anonymous API denied')
            # Restore a genuine encrypted backup carrying the previous Tor
            # layout through the installed root data-volume/configuration guard.
            sys.path.insert(0,'/opt/justverify/scripts')
            from backup_bundle import production_bundle,MAGIC
            from backup_service import quiesce,resume,health
            bundle=production_bundle();bundle.state=STATE/'backup';bundle.destination=STATE/'legacy.jvb'
            bundle.prepare_state();values=bundle.snapshot()
            canonical=values['etc/torrc']
            electrs_config=values['etc/electrs.toml']
            values['etc/electrs.toml']=electrs_config.replace(b'127.0.0.1:50003',b'127.0.0.1:50001')
            ready=json.loads(values['etc/node-ready.json']);ready['configs']['electrs.toml']=hashlib.sha256(values['etc/electrs.toml']).hexdigest();values['etc/node-ready.json']=json.dumps(ready).encode()
            values['etc/torrc']=canonical.removesuffix(b'HiddenServicePort 3006 127.0.0.1:28445\n').replace(b'HiddenServicePort 50001 127.0.0.1:50001',b'HiddenServicePort 50001 127.0.0.1:50003')
            if expected_version in ('0.1.1','0.1.2'):
                current_launcher=values['systemd/core-profile.conf']
                # The selected Core storage path is registered, independent of its version.
                folder=Path(json.loads(values['etc/node-ready.json'])['instance']['core_data']).parent
                values['systemd/core-profile.conf']=current_launcher.replace(b'ExecStart=/usr/bin/python3 -I /opt/justverify/scripts/core_service.py\n',f"ExecStart={config['binary']} -datadir={folder}/core -conf=/etc/justverify/bitcoin.conf\n".encode())
                assert values['systemd/core-profile.conf']!=current_launcher
            assert values['etc/torrc']!=canonical
            plain=STATE/'legacy.tar';cipher=STATE/'legacy.gpg';passphrase=secrets.token_urlsafe(32)
            bundle._write_tar(plain,values)
            encrypted=bundle._gpg(['--symmetric','--cipher-algo','AES256','--force-mdc','--output',str(cipher),str(plain)],passphrase)
            assert encrypted.returncode==0
            bundle.destination.write_bytes(MAGIC+cipher.read_bytes());bundle.destination.chmod(0o600)
            reviewed=bundle.inspect(bundle.destination,passphrase)
            quiesce()
            def recovered():resume();health()
            try:assert bundle.restore(passphrase,reviewed['sha256'],health_check=recovered)['phase']=='committed'
            finally:resume()
            if expected_version in ('0.1.1','0.1.2'):
                assert Path('/etc/systemd/system/justverify-core.service.d/20-profile.conf').read_bytes()==current_launcher
                REPORT['checks'].append('actual encrypted legacy Core launcher upgraded to fixed registered launcher on restore')
            assert Path('/etc/justverify/torrc').read_bytes()==canonical
            assert Path('/etc/justverify/electrs.toml').read_bytes()==electrs_config
            # The restore restarts the web process. A pooled connection can
            # close while synchronous restore work has paused this event loop.
            # Require a successful authenticated response after restart.
            async def login_restored():
                async with c.post('http://127.0.0.1/login',headers={'Origin':'http://127.0.0.1'},json={'password':password}) as r:
                    assert r.status==200
                    return (await r.json())['csrf']
            csrf=await wait(login_restored,30)
            assert await wait(address,60)==host
            assert (await toggle(True))['running']
            headers['Cookie']='jv_tor_session='+await tor_login()
            await wait(lan_ready,120)
            await wait(status_ready,120)
            assert await explorer('/api/blocks/tip/hash')==tip
            REPORT['checks'].append('actual GPG legacy backup passes installed data-volume guard; restore upgrades fixed Tor and Electrum routes and preserves identity/tip; explorer recovers')
            if expected_version in ('0.1.0-beta10-test3','0.1.0-beta10-test4','0.1.1','0.1.2'):
                result=await post('/sessions',{'action':'revoke_others'})
                assert result['revoked_count']>0 and not result['revoked_current']
                await explorer('/api/blocks/tip/hash',401)
                async with c.get('http://127.0.0.1/session') as r:assert r.status==200
                REPORT['checks'].append('other-device logout revokes Tor explorer access while current LAN login remains usable')
        if expected_version=='0.1.2':
            router_log=subprocess.check_output(['journalctl','-b','-u','justverify-i2p','-o','cat','--no-pager'],text=True)
            assert not any(marker in router_log for marker in ("State 'stop-sigterm' timed out", "State 'stop-sigkill' timed out", "Failed with result 'timeout'", 'signal SIGKILL', 'status=9/KILL'))
            REPORT['checks'].append('router lifecycle journal contains no stop timeout or forced termination; intentional disabled condition is distinguished')
        REPORT.update(status='PASS',height=height,tip=tip)

try:asyncio.run(main())
except Exception as error:
    import traceback
    REPORT['error']=type(error).__name__
    try:
        observed=subprocess.check_output(['systemctl','show','justverify-electrum-tls','--property=ActiveState,SubState,Result,NRestarts'],text=True)
        REPORT['wallet_service']={k:v for k,v in (line.split('=',1) for line in observed.splitlines())}
        log=subprocess.check_output(['journalctl','-b','-u','justverify-electrum-tls','-o','cat','--no-pager'],text=True)
        REPORT['optional_tls_unavailable_events']=log.count('Optional Electrum TLS unavailable')
    except Exception:pass
    REPORT['frames']=[{'file':Path(frame.filename).name,'line':frame.lineno} for frame in traceback.extract_tb(error.__traceback__)]
finally:
    STATE.mkdir(mode=0o700,exist_ok=True)
    (STATE/('result-'+REPORT.get('boot','unknown')+'.json')).write_text(json.dumps(REPORT,indent=2)+'\n')
    print('JV_IMAGE_MEMPOOL '+json.dumps(REPORT),flush=True)
    subprocess.run(['systemctl','reboot' if REPORT['status']=='PASS' and REPORT['boot']=='first' else 'poweroff'],check=True)
