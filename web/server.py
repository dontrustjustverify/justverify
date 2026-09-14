#!/usr/bin/env python3
"""TLS authenticated bridge to one fixed, nonprivileged JustVerify executable."""
import argparse, ipaddress, asyncio, base64, contextlib, fcntl, hashlib, hmac, json, os, pathlib, pty, secrets, socket as sockets, ssl, stat, struct, termios, time, signal
from aiohttp import web, WSMsgType
from rpc_gateway import Clients, Gateway
ROOT=pathlib.Path(__file__).resolve().parents[1]
SESSION_SECONDS=7*24*60*60
SESSION_RENEW_AFTER=60*60

def atomic(path, data):
    temp=path.with_name(path.name+'.'+secrets.token_hex(8))
    fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f:f.write(data);f.flush();os.fsync(f.fileno())
    os.replace(temp,path)
    directory=os.open(path.parent,os.O_RDONLY);os.fsync(directory);os.close(directory)

def password_hash(password,salt):
    return hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()

class Bridge:
    def __init__(self,state,binary,socket,origin):
        self.state=state;self.binary=str(binary.resolve());self.socket=str(socket.resolve());self.origin=origin
        self.sessions={};self.attempts={};self.active=set();self.load_sessions()
        self.clients=Clients(state/'rpc-clients.json',atomic);self.gateway=Gateway(self.clients,origin=self.origin)
        from node_admin import Startup
        self.startup=Startup()
        from device_settings import DeviceSettings
        from remote_web import RemoteWeb
        self.tor_streams=set();self.remote_cleanups=set()
        self.remote_web=RemoteWeb(self,atomic)
        self.device_settings=DeviceSettings(self,atomic,password_hash)
    def cookie_name(self,r):return 'jv_tor_session' if r.get('tor_web') else 'jv_lan_session' if r.scheme=='http' else 'jv_session'
    @staticmethod
    def session_key(token):return hashlib.sha256(token.encode()).hexdigest()
    def admin_digest(self):
        try:return hashlib.sha256((self.state/'admin.json').read_bytes()).hexdigest()
        except OSError:return None
    def load_sessions(self):
        path=self.state/'sessions.json'
        try:
            info=path.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_mode&0o077 or info.st_uid!=os.geteuid() or info.st_size>131072:return
            saved=json.loads(path.read_text());now=time.time()
            if saved.get('schema')!=1 or saved.get('admin_digest')!=self.admin_digest() or not self.admin_digest():return
            rows=saved['sessions']
            if not isinstance(rows,dict) or len(rows)>16:return
            for key,value in rows.items():
                if not isinstance(key,str) or len(key)!=64 or any(c not in '0123456789abcdef' for c in key):continue
                if not isinstance(value,dict) or set(value)!={'expires','renewed','csrf','audience','tor_web'}:continue
                if not isinstance(value['expires'],(int,float)) or not now<value['expires']<=now+SESSION_SECONDS+300:continue
                if not isinstance(value['renewed'],(int,float)) or not now-SESSION_SECONDS<=value['renewed']<=now+300:continue
                if not isinstance(value['csrf'],str) or not 32<=len(value['csrf'])<=128:continue
                if value['audience'] not in ('jv_session','jv_lan_session','jv_tor_session') or value['tor_web']!=(value['audience']=='jv_tor_session'):continue
                self.sessions[key]=value
        except (OSError,ValueError,TypeError,KeyError):self.sessions={}
    def save_sessions(self):
        self.sessions={k:v for k,v in self.sessions.items() if v['expires']>time.time()}
        atomic(self.state/'sessions.json',json.dumps({'schema':1,'admin_digest':self.admin_digest(),'sessions':self.sessions}))
    def session(self,r):
        token=r.cookies.get(self.cookie_name(r),'');key=self.session_key(token);s=self.sessions.get(key)
        if not s or s['expires']<=time.time() or s['audience']!=self.cookie_name(r):
            if s and s['expires']<=time.time():self.sessions.pop(key,None)
            raise web.HTTPUnauthorized(text='인증이 필요합니다.')
        r['authenticated_bridge']=self;r['authenticated_session']=s;r['session_token']=token
        return s
    def set_session_cookie(self,response,r,token):
        response.set_cookie(self.cookie_name(r),token,secure=r.scheme=='https',httponly=True,samesite='Strict',max_age=SESSION_SECONDS,path='/')
    def renew_session(self,r,response):
        s=r.get('authenticated_session');token=r.get('session_token','')
        if response.prepared or response.status>=400 or not s or self.sessions.get(self.session_key(token)) is not s:return
        now=time.time()
        if now-s['renewed']>=SESSION_RENEW_AFTER and s['expires']>now:
            s['expires']=now+SESSION_SECONDS;s['renewed']=now;self.save_sessions();self.set_session_cookie(response,r,token)
    def same_origin(self,r):
        origin=r.headers.get('Origin')
        if r.get('tor_web'):
            if origin=='http://'+r.host:return
            raise web.HTTPForbidden(text='Origin rejected')
        if origin==self.origin and r.scheme=='https':return
        if getattr(self,'lan_http',False) and r.scheme=='http':
            host=r.host
            local=r.transport.get_extra_info('sockname')[0]
            allowed={'justverify.local','localhost',local,'['+local+']'}
            if host in allowed or host in {h+':'+str(r.transport.get_extra_info('sockname')[1]) for h in allowed}:
                if origin=='http://'+host:return
        raise web.HTTPForbidden(text='Origin rejected')
    def limited(self,r):
        now=time.monotonic();key=r.remote
        self.attempts={k:[v for v in vals if now-v<300] for k,vals in self.attempts.items() if any(now-v<300 for v in vals)}
        vals=self.attempts.setdefault(key,[])
        if len(vals)>=5 or len(self.attempts)>1024:raise web.HTTPTooManyRequests(text='시도가 너무 많습니다. 5분 후 다시 시도하세요.',headers={'Retry-After':str(max(1,int(300-(now-vals[0])))) if vals else '300'})
        vals.append(now)
    async def pairing_proof(self,r):
        token=self.state/'setup-token'
        if (self.state/'admin.json').exists() or not token.exists():raise web.HTTPNotFound()
        der=ssl.PEM_cert_to_DER_cert((self.state/'certificate.pem').read_text())
        proof=hmac.new(token.read_text().strip().encode(),b'JustVerify TLS pairing v1\0'+hashlib.sha256(der).digest(),hashlib.sha256).hexdigest()
        return web.json_response({'algorithm':'hmac-sha256-cert-der-v1','proof':proof})
    async def index(self,r):return web.FileResponse(ROOT/'web/static/index.html')
    async def auth_status(self,r):
        return web.json_response({'setup_required':not (self.state/'admin.json').exists(),'requires_code':not (getattr(self,'lan_onboarding',False) and r.scheme=='http')})
    async def resume_session(self,r):
        if r.headers.get('Origin'):self.same_origin(r)
        if r.headers.get('Sec-Fetch-Site')=='cross-site':raise web.HTTPForbidden()
        session=self.session(r)
        return web.json_response({'csrf':session['csrf']})
    async def node_admin(self,r):
        self.same_origin(r);self.read_session(r)
        from node_admin import call,validate
        try:
            body=await r.json()
            if r.path=='/node-start':
                if body!={}:raise ValueError('잘못된 시작 요청입니다.')
                result=await self.startup.start()
            else:
                service=r.path[1:];validate(service,body)
                result=await call(service,body)
                if service=='policy' and body['method']=='state':
                    for entry in result.get('entries',[]):
                        if isinstance(entry.get('range'),dict):
                            entry['range']={k:str(v) if isinstance(v,int) else v for k,v in entry['range'].items()}
            return web.json_response(result)
        except (ValueError,TypeError) as error:raise web.HTTPConflict(text=str(error))
        except (OSError,asyncio.TimeoutError):raise web.HTTPServiceUnavailable(text='서비스 응답을 확인하지 못했습니다. 변경을 반복하기 전에 저장된 상태를 확인하세요.')
    async def setup(self,r):
        self.same_origin(r)
        if (self.state/'admin.json').exists():raise web.HTTPConflict(text='이미 등록된 기기입니다. 로그인 화면을 이용하세요.')
        try:body=await r.json()
        except ValueError:raise web.HTTPBadRequest(text='입력 형식을 확인하세요.')
        if not isinstance(body,dict) or not isinstance(body.get('password'),str) or not 12<=len(body['password'])<=256:raise web.HTTPBadRequest(text='새 관리자 암호는 12~256자로 입력하세요.')
        if body.get('password')!=body.get('password_confirm'):raise web.HTTPBadRequest(text='새 암호와 확인 입력이 일치하지 않습니다.')
        return await self.login(r)
    async def login(self,r):
        self.same_origin(r);self.limited(r)
        try:body=await r.json();password=body.get('password','')
        except (ValueError,AttributeError):raise web.HTTPBadRequest()
        if not isinstance(password,str) or not 12<=len(password)<=256:raise web.HTTPUnauthorized()
        record=self.state/'admin.json'
        if not record.exists():
            tokenfile=self.state/'setup-token'
            lan_setup=getattr(self,'lan_onboarding',False) and r.scheme=='http' and r.path=='/setup'
            if not lan_setup and (not tokenfile.exists() or not hmac.compare_digest(str(body.get('setup_token','')).strip(),tokenfile.read_text().strip())):raise web.HTTPUnauthorized(text='기기 확인 코드가 맞지 않습니다. Pi 화면에서 Enter를 눌러 표시되는 일회성 코드를 입력하세요. 새 암호와는 다른 값입니다.')
            salt=secrets.token_hex(16)
            # First setup is serialized on the event loop; never yields between check and commit.
            atomic(record,json.dumps({'salt':salt,'hash':password_hash(password,salt)}))
            tokenfile.unlink(missing_ok=True)
            directory=os.open(self.state,os.O_RDONLY);os.fsync(directory);os.close(directory)
        else:
            p=json.loads(record.read_text())
            if not hmac.compare_digest(password_hash(password,p['salt']),p['hash']):raise web.HTTPUnauthorized(text='관리자 암호가 맞지 않습니다.')
        self.attempts[r.remote].pop()  # Successful authentication is not a failed attempt.
        self.sessions={k:v for k,v in self.sessions.items() if v['expires']>time.time()}
        if len(self.sessions)>=16:raise web.HTTPTooManyRequests()
        token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32)
        self.sessions[self.session_key(token)]={'expires':time.time()+SESSION_SECONDS,'renewed':time.time(),'csrf':csrf,'audience':self.cookie_name(r),'tor_web':bool(r.get('tor_web'))};self.save_sessions()
        response=web.json_response({'csrf':csrf});self.set_session_cookie(response,r,token)
        return response
    async def logout(self,r):
        self.same_origin(r);s=self.session(r)
        if not hmac.compare_digest(r.headers.get('X-CSRF-Token',''),s['csrf']):raise web.HTTPForbidden()
        self.sessions.pop(self.session_key(r.cookies.get(self.cookie_name(r),'')),None);self.save_sessions()
        response=web.json_response({'ok':True});response.del_cookie(self.cookie_name(r));return response
    async def remote_rpc(self,r):
        self.same_origin(r);session=self.session(r)
        if not hmac.compare_digest(r.headers.get('X-CSRF-Token',''),session['csrf']):raise web.HTTPForbidden()
        return await self.remote_request(r)
    async def remote_local(self,r):
        peer=r.transport.get_extra_info('socket')
        if peer is None or struct.unpack('3i',peer.getsockopt(sockets.SOL_SOCKET,sockets.SO_PEERCRED,12))[1]!=os.geteuid():raise web.HTTPForbidden()
        if not (self.state/'admin.json').is_file():raise web.HTTPUnauthorized()
        return await self.remote_request(r)
    async def remote_request(self,r):
        if not getattr(self,'remote',None):raise web.HTTPServiceUnavailable()
        try:
            body=await r.json()
            if isinstance(body,dict) and body.get('action')=='apply':
                self.limited(r)
                if set(body)!={'action','token','password'} or not isinstance(body['password'],str) or not 12<=len(body['password'])<=256:raise web.HTTPUnauthorized()
                record=json.loads((self.state/'admin.json').read_text())
                if not hmac.compare_digest(password_hash(body['password'],record['salt']),record['hash']):raise web.HTTPUnauthorized()
                self.attempts[r.remote].pop()
                body={key:body[key] for key in ('action','token')}
            result=await self.remote.manage(body)
        except ValueError:raise web.HTTPConflict(text='Remote RPC review refused; refresh its state.')
        except web.HTTPException:raise
        except Exception:raise web.HTTPServiceUnavailable(text='Remote RPC change failed; inspect saved and running state before retrying.')
        return web.json_response(result)
    async def rpc_clients(self,r):
        self.same_origin(r);session=self.session(r)
        if not hmac.compare_digest(r.headers.get('X-CSRF-Token',''),session['csrf']):raise web.HTTPForbidden()
        try:
            body=await r.json()
            if not isinstance(body,dict):raise ValueError()
            if body.get('action')=='list' and set(body)=={'action'}:result=self.clients.list()
            elif body.get('action')=='create' and set(body)=={'action','label'}:result=self.clients.create(body['label'])
            elif body.get('action')=='revoke' and set(body)=={'action','id'} and isinstance(body['id'],str):self.clients.revoke(body['id']);result={'revoked':True}
            elif body.get('action')=='grant_transactions' and set(body)=={'action','id'} and isinstance(body['id'],str):
                from wallet_gateway import WalletAccess
                try:result=await WalletAccess(self.clients,self.gateway.profile,body['id']).enable_transactions()
                except web.HTTPException:raise
                except Exception:raise web.HTTPBadGateway(text='Transaction grant failed.')
            elif body.get('action')=='grant_watch_only' and set(body)=={'action','id'} and isinstance(body['id'],str):
                from wallet_gateway import WalletAccess
                try:result=await WalletAccess(self.clients,self.gateway.profile,body['id'],grant=True).grant()
                except web.HTTPException:raise
                except Exception:raise web.HTTPBadGateway(text='Wallet grant failed; existing data preserved.')
            else:raise ValueError()
        except ValueError:raise web.HTTPBadRequest()
        return web.json_response(result)
    async def storage(self,r):
        self.same_origin(r);session=self.session(r)
        if not hmac.compare_digest(r.headers.get('X-CSRF-Token',''),session['csrf']):raise web.HTTPForbidden()
        try:
            body=await r.json()
            schemas={'inventory':{'action'},'prepare_profile':{'action'},'preview':{'action','name','identity_digest'},'apply':{'action','id','confirmation'},'recover':{'action','id'}}
            if not isinstance(body,dict) or body.get('action') not in schemas or set(body)!=schemas[body['action']] or any(not isinstance(v,str) for v in body.values()):raise ValueError()
        except (ValueError,TypeError):raise web.HTTPBadRequest()
        writer=None
        try:
            reader,writer=await asyncio.wait_for(asyncio.open_unix_connection('/run/justverify-storage/api.sock',limit=1024*1024),3)
            writer.write(json.dumps(body).encode()+b'\n');await writer.drain()
            result=json.loads(await asyncio.wait_for(reader.readline(),240))
            return web.json_response(result,status=200 if result.get('ok') else 409)
        except (OSError,ValueError,asyncio.TimeoutError):
            raise web.HTTPServiceUnavailable(text='저장장치 작업 결과를 확인하지 못했습니다. 계획 ID를 보존하고 복구 상태를 확인하세요.')
        finally:
            if writer:
                writer.close()
                with contextlib.suppress(OSError):await writer.wait_closed()
    def read_session(self,r):
        session=self.session(r)
        if not hmac.compare_digest(r.headers.get('X-CSRF-Token',''),session['csrf']):raise web.HTTPForbidden()
        if r.headers.get('Origin'):self.same_origin(r)
    async def dashboard(self,r):
        self.read_session(r)
        return web.json_response(await self.snapshot())
    async def snapshot(self):
        writer=None
        try:
            reader,writer=await asyncio.wait_for(asyncio.open_unix_connection(self.socket,limit=2*1024*1024),3)
            writer.write(b'snapshot\n');await writer.drain()
            async def bounded_read():
                raw=b''
                while len(raw)<=2*1024*1024:
                    chunk=await reader.read(65536)
                    if not chunk:break
                    raw+=chunk
                return raw
            raw=await asyncio.wait_for(bounded_read(),4)
            if len(raw)>2*1024*1024:raise ValueError('snapshot too large')
            return json.loads(raw)
        except (OSError,ValueError,asyncio.TimeoutError):raise web.HTTPServiceUnavailable(text='노드 수집기에 연결할 수 없습니다.')
        finally:
            if writer:writer.close();await writer.wait_closed()
    async def electrum(self,r):
        self.read_session(r)
        mode=r.query.get('network','lan')
        if mode not in ('lan','tor'):raise web.HTTPBadRequest()
        from electrum_qr import lan_endpoint, endpoint
        try:result=await (asyncio.to_thread(lan_endpoint,False) if mode=='lan' else asyncio.to_thread(endpoint))
        except Exception:raise web.HTTPServiceUnavailable(text='선택한 Electrum 연결이 아직 준비되지 않았습니다. Core·electrs 초기 설정과 서비스 상태를 확인하세요.')
        try:
            snapshot=await self.snapshot()
            result['index_state']=snapshot.get('host',{}).get('electrs',{}).get('state','UNAVAILABLE')
            result['ibd']=(snapshot.get('rpc',{}).get('getblockchaininfo',{}).get('value') or {}).get('initialblockdownload')
        except web.HTTPException:
            result['index_state']='UNAVAILABLE';result['ibd']=None
        return web.json_response(result)
    async def terminal(self,r):
        self.same_origin(r);session=self.session(r)
        if len(self.active)>=4:raise web.HTTPTooManyRequests()
        ws=web.WebSocketResponse(max_msg_size=8192,heartbeat=20);self.active.add(ws)
        await ws.prepare(r)
        if r.get('tor_web'):self.tor_streams.add(ws)
        master,slave=pty.openpty();os.set_blocking(master,False)
        fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',40,120,0,0))
        process=await asyncio.create_subprocess_exec(self.binary,'tui','--socket',self.socket,stdin=slave,stdout=slave,stderr=slave,env={'PATH':'/usr/bin:/bin','TERM':'xterm-256color','LANG':'C.UTF-8'})
        os.close(slave)
        async def output():
            while process.returncode is None and not ws.closed:
                try:self.session(r)
                except web.HTTPUnauthorized:await ws.close();return
                try:
                    data=os.read(master,65536)
                    if data:await ws.send_bytes(data)
                except BlockingIOError:pass
                except OSError:break
                await asyncio.sleep(.03)
            await ws.close()
        reader=asyncio.create_task(output())
        try:
            async for msg in ws:
                self.session(r)
                if msg.type==WSMsgType.TEXT:
                    try:
                        data=json.loads(msg.data)
                        if set(data)=={'input'} and isinstance(data['input'],str):os.write(master,data['input'].encode()[:4096])
                        elif set(data)=={'cols','rows'}:
                            cols=max(30,min(240,int(data['cols'])));rows=max(12,min(100,int(data['rows'])))
                            fcntl.ioctl(master,termios.TIOCSWINSZ,struct.pack('HHHH',rows,cols,0,0));process.send_signal(signal.SIGWINCH)
                        else:await ws.close(code=1008)
                    except (ValueError,TypeError,OSError):await ws.close(code=1008)
        finally:
            reader.cancel()
            with contextlib.suppress(asyncio.CancelledError):await reader
            if process.returncode is None:
                process.terminate()
                try:await asyncio.wait_for(process.wait(),3)
                except asyncio.TimeoutError:process.kill();await process.wait()
            os.close(master);self.active.discard(ws);self.tor_streams.discard(ws)
        return ws

@web.middleware
async def headers(request,handler):
    try:response=await handler(request)
    except web.HTTPException as exc:response=exc
    if request.get('authenticated_bridge'):request['authenticated_bridge'].renew_session(request,response)
    response.headers.update({'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY','Referrer-Policy':'no-referrer','Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"})
    return response

def rpc_app(bridge,controller=None):
    # Tor can reach only these routes, never enrollment, terminal or client grants.
    app=web.Application(client_max_size=4096,middlewares=[headers])
    async def request(r):
        return await controller.guarded(bridge.gateway.rpc,r) if controller else await bridge.gateway.rpc(r)
    for path in ('/','/rpc','/wallet/{wallet}'):
        app.router.add_post(path,request)
    return app

@web.middleware
async def private_lan(request,handler):
    try:address=ipaddress.ip_address(request.remote)
    except ValueError:raise web.HTTPForbidden()
    networks=('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16','127.0.0.0/8','::1/128','fc00::/7','fe80::/10')
    if not any(address in ipaddress.ip_network(n) for n in networks):raise web.HTTPForbidden()
    return await handler(request)

def app_for(bridge,tor_rpc=False,lan_http=False,remote_web=False):
    app=web.Application(client_max_size=4096,middlewares=[headers,*([private_lan] if lan_http else [])])
    if not tor_rpc and not lan_http:
        async def persistent_web(app):
            try:
                try:await bridge.remote_web.restore()
                except Exception:await bridge.remote_web.stop()
                yield
            finally:
                await bridge.remote_web.stop(revoke=False)
                if bridge.remote_cleanups:await asyncio.gather(*bridge.remote_cleanups,return_exceptions=True)
        app.cleanup_ctx.append(persistent_web)
        from remote_rpc import RemoteRPC
        bridge.remote=RemoteRPC(bridge.state,atomic,lambda:rpc_app(bridge,bridge.remote))
        async def persistent_rpc(app):
            local=web.Application(client_max_size=4096,middlewares=[headers])
            local.router.add_post('/remote-rpc',bridge.remote_local)
            control=web.AppRunner(local,access_log=None,shutdown_timeout=5)
            path=bridge.state/'remote-control.sock';bound=None
            try:
                if path.exists() or path.is_symlink():
                    if path.is_symlink() or not stat.S_ISSOCK(path.lstat().st_mode):raise ValueError('Control socket path occupied')
                    with sockets.socket(sockets.AF_UNIX) as probe:
                        probe.settimeout(.2)
                        try:probe.connect(str(path))
                        except ConnectionRefusedError:path.unlink()
                        else:raise ValueError('Remote control service already running')
                await control.setup()
                await web.UnixSite(control,str(path)).start()
                bound=path.stat().st_ino;path.chmod(0o600)
                try:await bridge.remote.restore()
                except Exception:await bridge.remote.stop()
                yield
            finally:
                await bridge.remote.stop();await control.cleanup()
                if bound is not None and path.exists() and path.lstat().st_ino==bound:path.unlink()
        app.cleanup_ctx.append(persistent_rpc)
    app.router.add_post('/device-settings',bridge.device_settings.request)
    app.router.add_post('/remote-rpc',bridge.remote_rpc)
    app.router.add_get('/session',bridge.resume_session)
    for path in ('/versions','/policy','/node-start'):app.router.add_post(path,bridge.node_admin)
    if tor_rpc:
        async def rpc_listener(app):
            # Reuse the exact Gateway: credentials, quotas and in-flight count
            # remain shared with HTTPS. The unencrypted socket is loopback only.
            runner=web.AppRunner(rpc_app(bridge),access_log=None)
            await runner.setup()
            try:
                await web.TCPSite(runner,'127.0.0.1',28443).start()
                yield
            finally:await runner.cleanup()
        app.cleanup_ctx.append(rpc_listener)
    app.router.add_get('/auth-status',bridge.auth_status);app.router.add_post('/setup',bridge.setup);app.router.add_get('/',bridge.index);app.router.add_get('/pairing-proof',bridge.pairing_proof);app.router.add_post('/login',bridge.login);app.router.add_post('/logout',bridge.logout);app.router.add_get('/terminal',bridge.terminal);app.router.add_get('/dashboard',bridge.dashboard);app.router.add_get('/electrum',bridge.electrum);app.router.add_post('/storage',bridge.storage);app.router.add_post('/rpc-clients',bridge.rpc_clients)
    if not lan_http:
        app.router.add_post('/rpc',bridge.gateway.rpc);app.router.add_post('/',bridge.gateway.rpc);app.router.add_post('/wallet/{wallet}',bridge.gateway.rpc)
    # Explicit static allowlist; state files cannot be routed.
    for name in ['xterm.js','xterm.css','app.js','app.css','copy.js','dashboard.js','settings.js','device.js','i18n.js','favicon.svg','favicon.ico','apple-touch-icon.png']:
        async def serve(r,name=name):return web.FileResponse(ROOT/'web/static'/name)
        app.router.add_get('/'+name,serve)
    return app
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--state',type=pathlib.Path,required=True);p.add_argument('--binary',type=pathlib.Path,required=True);p.add_argument('--socket',type=pathlib.Path,required=True);p.add_argument('--origin',required=True);p.add_argument('--listen',default='127.0.0.1');p.add_argument('--port',type=int,default=8443);p.add_argument('--tor-rpc',action='store_true');p.add_argument('--http-lan-port',type=int);p.add_argument('--lan-onboarding',action='store_true');a=p.parse_args()
    if os.geteuid()==0:raise SystemExit('Web TUI must run as a non-root user')
    if not a.origin.startswith('https://'):raise SystemExit('HTTPS origin required')
    if a.state.stat().st_mode & 0o077:raise SystemExit('Private state directory required')
    tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);tls.minimum_version=ssl.TLSVersion.TLSv1_2;tls.load_cert_chain(a.state/'certificate.pem',a.state/'private-key.pem')
    bridge=Bridge(a.state,a.binary,a.socket,a.origin);bridge.lan_http=bool(a.http_lan_port);bridge.lan_onboarding=a.lan_onboarding
    if a.lan_onboarding and not a.http_lan_port:raise SystemExit('LAN onboarding requires explicit LAN HTTP listener')
    app=app_for(bridge,tor_rpc=a.tor_rpc)
    if a.http_lan_port:
        async def lan_listener(app):
            runner=web.AppRunner(app_for(bridge,lan_http=True),access_log=None)
            await runner.setup()
            try:
                await web.TCPSite(runner,'0.0.0.0',a.http_lan_port).start()
                yield
            finally:await runner.cleanup()
        app.cleanup_ctx.append(lan_listener)
    web.run_app(app,host=a.listen,port=a.port,ssl_context=tls,access_log=None,print=None)
