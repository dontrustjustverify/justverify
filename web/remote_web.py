"""A separate, opt-in Tor browser listener sharing owner authentication only."""
import asyncio
from aiohttp import web
from remote_rpc import RemoteRPC

class RemoteWeb(RemoteRPC):
    def __init__(self,bridge,atomic):
        self.bridge=bridge
        super().__init__(bridge.state,atomic,self.application,service='web',port=28444)
    def status(self):
        result=super().status();result['transport']='Tor Browser · HTTP inside Tor'
        result['url']='http://'+result['onion_host']+'/' if result['onion_host'] else None
        return result
    async def manage(self,body):
        if isinstance(body,dict) and body.get('action')=='preview' and body.get('enabled') is True:
            if not self.status()['onion_host']:raise ValueError('Tor web address is not ready')
        result=await super().manage(body)
        if isinstance(result,dict) and 'warning' in result:
            result['warning']='Tor Browser에서 이 노드의 관리 화면에 접속합니다. 관리자 암호가 필요합니다. RPC 연결 설정은 별개입니다.'
        return result
    async def stop(self):
        # The disabling request may itself arrive over Tor. Revoke sessions and
        # close streams first, then drain this listener outside that request.
        self.enabled=False
        self.bridge.sessions={k:v for k,v in self.bridge.sessions.items() if not v.get('tor_web')}
        for stream in list(getattr(self.bridge,'tor_streams',set())):await stream.close()
        runner,self.runner=self.runner,None
        if runner is not None:
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
