"""A separate, opt-in Tor browser listener sharing owner authentication only."""
import asyncio
import ipaddress
from pathlib import Path
from aiohttp import web
from remote_rpc import RemoteRPC

class RemoteWeb(RemoteRPC):
    def __init__(self,bridge,atomic):
        self.bridge=bridge
        super().__init__(bridge.state,atomic,self.application,service='web',port=28444)
        self.mempool_port=28445
        self.mempool_runner=None
        self.mempool_bundle=Path('/opt/justverify/mempool')
        self.mempool_runtime=Path('/run/justverify-mempool')
        self.mempool_profile=Path('/etc/justverify/profile.json')
        self.mempool_backend='http://127.0.0.1:8999'
    def status(self):
        result=super().status();result['transport']='Tor Browser · HTTP inside Tor'
        result['url']='http://'+result['onion_host']+'/' if result['onion_host'] else None
        return result
    async def start(self):
        if self.runner is not None and self.mempool_runner is not None:return
        try:
            await super().start()
            runner=web.AppRunner(self.mempool_application(),access_log=None,shutdown_timeout=5)
            self.mempool_runner=runner
            await runner.setup()
            await web.TCPSite(runner,'127.0.0.1',self.mempool_port).start()
        except BaseException:
            await self.stop(revoke=False)
            raise
    def authorize_mempool(self,request):
        if not self.enabled or not (self.bridge.state/'admin.json').is_file():raise web.HTTPServiceUnavailable()
        try: loopback=ipaddress.ip_address(request.remote).is_loopback
        except (ValueError,TypeError):loopback=False
        host=self.status()['onion_host']
        if not loopback or not host or request.host!=host+':3006':raise web.HTTPForbidden()
        request['tor_web']=True
        origin=request.headers.get('Origin')
        if origin or request.method not in ('GET','HEAD') or request.headers.get('Upgrade','').lower()=='websocket':
            if origin!='http://'+request.host:raise web.HTTPForbidden()
        if request.headers.get('Sec-Fetch-Site')=='cross-site':raise web.HTTPForbidden()
        self.bridge.session(request)
    def mempool_application(self):
        from mempool_proxy import make_app
        @web.middleware
        async def guard(request,handler):
            try:self.authorize_mempool(request)
            except web.HTTPUnauthorized:
                if request.method=='GET' and request.headers.get('Upgrade','').lower()!='websocket' and 'text/html' in request.headers.get('Accept',''):
                    raise web.HTTPSeeOther('http://'+self.status()['onion_host']+'/')
                raise
            response=await handler(request)
            self.bridge.renew_session(request,response)
            response.headers.update({'Referrer-Policy':'no-referrer','X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY'})
            return response
        return make_app(self.mempool_bundle,self.mempool_runtime,self.mempool_profile,self.mempool_backend,
                        middleware=guard,authorize=self.authorize_mempool,streams=self.bridge.tor_streams)
    async def manage(self,body):
        if isinstance(body,dict) and body.get('action')=='preview' and body.get('enabled') is True:
            if not self.status()['onion_host']:raise ValueError('Tor web address is not ready')
        result=await super().manage(body)
        if isinstance(result,dict) and 'warning' in result:
            result['warning']='Tor Browser에서 이 노드의 관리 화면에 접속합니다. 관리자 암호가 필요합니다. RPC 연결 설정은 별개입니다.'
        return result
    async def stop(self, *, revoke=True):
        # The disabling request may itself arrive over Tor. Revoke sessions and
        # close streams first, then drain this listener outside that request.
        self.enabled=False
        if revoke:
            self.bridge.sessions={k:v for k,v in self.bridge.sessions.items() if not v.get('tor_web')}
            self.bridge.save_sessions()
        for stream in list(getattr(self.bridge,'tor_streams',set())):await stream.close()
        runners=(self.runner,self.mempool_runner)
        self.runner=self.mempool_runner=None
        for runner in runners:
            if runner is None:continue
            for site in list(runner.sites):await site.stop()
            task=asyncio.create_task(runner.cleanup())
            self.bridge.remote_cleanups.add(task);task.add_done_callback(self.bridge.remote_cleanups.discard)
    def application(self):
        from server import app_for
        @web.middleware
        async def guard(request,handler):
            if not self.enabled or not (self.bridge.state/'admin.json').is_file():raise web.HTTPServiceUnavailable()
            host=self.status()['onion_host']
            if not host or request.host not in (host,host+':80'):raise web.HTTPForbidden()
            if request.path in ('/setup','/pairing-proof'):raise web.HTTPNotFound()
            request['tor_web']=True
            return await handler(request)
        app=app_for(self.bridge,lan_http=True,remote_web=True)
        app.middlewares.insert(0,guard)
        return app
