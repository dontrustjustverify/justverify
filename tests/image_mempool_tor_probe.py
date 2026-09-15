#!/usr/bin/env python3
"""Packaged Tor explorer listeners across two disposable generic ARM boots.

Checks actual loopback routing, not public Tor transport; mempool_tor_live.py
tests that transport separately. Never run on a physical node.
"""
import asyncio,base64,hashlib,json,os,secrets,subprocess,sys,time
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
    assert json.loads(Path('/etc/justverify/os-release.json').read_text())['version']=='0.1.0-beta7'
    assert '0.1.0-beta7' in subprocess.check_output(['/opt/justverify/bin/justverify','--version'],text=True)
    assert 'HiddenServicePort 3006 127.0.0.1:28445' in Path('/etc/justverify/torrc').read_text()
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
        preferences=(await post('/device-settings',{'action':'state'}))['preferences']
        assert preferences['language']=='auto'
        for language in ('ja','ko','en','auto'):
            saved=await post('/device-settings',{'action':'preferences','theme':preferences['theme'],'language':language})
            assert saved['preferences']['language']==language
        async with c.get('http://127.0.0.1/device.js') as r:
            assert r.status==200 and 'Language/언어설정/言語設定' in await r.text()
        async with c.get('http://127.0.0.1/i18n.js') as r:
            assert r.status==200 and "resolve('auto')" in await r.text()
        REPORT['checks'].append('automatic language factory default and reboot retention; all explicit language choices and fixed selector label packaged')
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
        assert not current['height_stale'] and not current['target_stale']
        async with c.get('http://127.0.0.1/electrs_status.js') as r:
            assert r.status==200 and 'progress' in await r.text()
        REPORT['checks'].append('packaged live Electrs metrics, exact progress heights, fresh matching tip and wallet readiness')
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
                assert r.status==200;return r.cookies['jv_tor_session'].value
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
        if not previous:
            subprocess.run(['systemctl','restart','justverify-web'],check=True)
            async def restored():return await explorer('/api/blocks/tip/hash')==tip
            await wait(restored,30)
            REPORT['checks'].append('web systemd restart preserves Tor explorer login')
            with os.fdopen(os.open(checkpoint,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as f:
                json.dump({'password':password,'token':token,'onion':host,'tip':tip,'boot_id':boot_id},f)
        else:
            REPORT['checks'].append('real reboot preserves Tor identity/login, opt-in setting and three matching node tips')
            import signal
            pid=int(subprocess.check_output(['systemctl','show','justverify-electrs','--property=MainPID','--value'],text=True))
            assert pid>1
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
            values['etc/torrc']=canonical.removesuffix(b'HiddenServicePort 3006 127.0.0.1:28445\n')
            assert values['etc/torrc']!=canonical
            plain=STATE/'legacy.tar';cipher=STATE/'legacy.gpg';passphrase=secrets.token_urlsafe(32)
            bundle._write_tar(plain,values)
            encrypted=bundle._gpg(['--symmetric','--cipher-algo','AES256','--force-mdc','--output',str(cipher),str(plain)],passphrase)
            assert encrypted.returncode==0
            bundle.destination.write_bytes(MAGIC+cipher.read_bytes());bundle.destination.chmod(0o600)
            reviewed=bundle.inspect(bundle.destination,passphrase)
            await post('/device-settings',{'action':'preferences','theme':preferences['theme'],'language':'en'})
            quiesce()
            def recovered():resume();health()
            try:assert bundle.restore(passphrase,reviewed['sha256'],health_check=recovered)['phase']=='committed'
            finally:resume()
            assert Path('/etc/justverify/torrc').read_bytes()==canonical
            # The restore restarts the web process. A pooled connection can
            # close while synchronous restore work has paused this event loop.
            # Require a successful authenticated response after restart.
            async def login_restored():
                async with c.post('http://127.0.0.1/login',headers={'Origin':'http://127.0.0.1'},json={'password':password}) as r:
                    assert r.status==200
                    return (await r.json())['csrf']
            csrf=await wait(login_restored,30)
            assert (await post('/device-settings',{'action':'state'}))['preferences']['language']=='auto'
            REPORT['checks'].append('actual encrypted backup restores automatic language after manual English change')
            assert await wait(address,60)==host
            assert (await toggle(True))['running']
            headers['Cookie']='jv_tor_session='+await tor_login()
            await wait(lan_ready,120)
            await wait(status_ready,120)
            assert await explorer('/api/blocks/tip/hash')==tip
            REPORT['checks'].append('actual GPG legacy backup passes installed data-volume guard; restore upgrades fixed Tor route and preserves identity/tip; explorer recovers')
        REPORT.update(status='PASS',height=height,tip=tip)

try:asyncio.run(main())
except Exception as error:
    import traceback
    REPORT['error']=type(error).__name__
    REPORT['frames']=[{'file':Path(frame.filename).name,'line':frame.lineno} for frame in traceback.extract_tb(error.__traceback__)]
finally:
    STATE.mkdir(mode=0o700,exist_ok=True)
    (STATE/('result-'+REPORT.get('boot','unknown')+'.json')).write_text(json.dumps(REPORT,indent=2)+'\n')
    print('JV_IMAGE_MEMPOOL '+json.dumps(REPORT),flush=True)
    subprocess.run(['systemctl','reboot' if REPORT['status']=='PASS' and REPORT['boot']=='first' else 'poweroff'],check=True)
