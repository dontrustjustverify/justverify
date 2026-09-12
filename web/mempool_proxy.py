#!/usr/bin/env python3
"""LAN-only static site and fixed upstream proxy for the bundled mempool app."""
import argparse
import asyncio
import contextlib
import ipaddress
import json
import mimetypes
from pathlib import Path
from aiohttp import ClientSession, ClientTimeout, WSMsgType, web

LAN = tuple(ipaddress.ip_network(n) for n in ('127.0.0.0/8','10.0.0.0/8','172.16.0.0/12','192.168.0.0/16','169.254.0.0/16','::1/128','fc00::/7','fe80::/10'))

@web.middleware
async def boundary(request, handler):
    try: address = ipaddress.ip_address(request.remote)
    except ValueError: raise web.HTTPForbidden()
    if not any(address in net for net in LAN): raise web.HTTPForbidden()
    hostname = request.host.rsplit(':',1)[0] if not request.host.startswith('[') else request.host.split(']')[0][1:]
    try: valid_host = any(ipaddress.ip_address(hostname) in net for net in LAN)
    except ValueError: valid_host = hostname in ('justverify.local', 'justverify', 'localhost')
    if not valid_host: raise web.HTTPForbidden()
    origin = request.headers.get('Origin')
    if origin and origin != 'http://' + request.host: raise web.HTTPForbidden()
    return await handler(request)


def make_app(bundle, runtime, profile, backend):
    app = web.Application(middlewares=[boundary], client_max_size=10*1024*1024)
    async def lifecycle(app):
        async with ClientSession(timeout=ClientTimeout(total=30), trust_env=False) as client:
            app['client'] = client
            yield
    app.cleanup_ctx.append(lifecycle)
    def state():
        try: return json.loads((runtime/'status.json').read_text())
        except (OSError, ValueError): return {'state':'waiting'}
    async def status(request): return web.json_response(state(), headers={'Cache-Control':'no-store'})
    async def config(request):
        value = json.loads((Path(__file__).parent/'mempool_frontend.json').read_text())
        try: network=json.loads(profile.read_text())['network']
        except (OSError,ValueError,KeyError): network='main'
        value['ROOT_NETWORK']={'main':'','test':'testnet'}.get(network,network)
        manifest=json.loads((bundle/'manifest.json').read_text())
        value['PACKAGE_JSON_VERSION']=manifest['version']
        value['GIT_COMMIT_HASH']=manifest['commit']
        value['NGINX_HOSTNAME']=request.host.split(':')[0]
        value['NGINX_PORT']=str(request.url.port)
        return web.Response(text='window.__env=Object.assign(window.__env||{},'+json.dumps(value)+');', content_type='application/javascript', headers={'Cache-Control':'no-store'})
    async def websocket(request):
        if state().get('state') != 'running': raise web.HTTPServiceUnavailable(text='Explorer is preparing the local node')
        async with app['client'].ws_connect(backend+'/', heartbeat=30, max_msg_size=16*1024*1024) as upstream:
            downstream=web.WebSocketResponse(heartbeat=30, max_msg_size=1024*1024)
            await downstream.prepare(request)
            async def copy(source,target):
                async for message in source:
                    if message.type==WSMsgType.TEXT: await target.send_str(message.data)
                    elif message.type==WSMsgType.BINARY: await target.send_bytes(message.data)
                    else: break
            tasks=[asyncio.create_task(copy(upstream,downstream)),asyncio.create_task(copy(downstream,upstream))]
            try: await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            finally:
                for task in tasks: task.cancel()
                await asyncio.gather(*tasks,return_exceptions=True)
                await downstream.close()
            return downstream
    async def api(request):
        if state().get('state') != 'running':
            return web.json_response({'error':'Local explorer is preparing','node':state()},status=503)
        path=request.path
        if not path.startswith('/api/v1/'): path='/api/v1/'+path[len('/api/'):]
        # No external fallback or arbitrary host/header forwarding.
        async with app['client'].request(request.method, backend+path, params=request.query, data=await request.read(), headers={'Content-Type':request.headers.get('Content-Type','application/json')}, allow_redirects=False) as response:
            headers={name:response.headers[name] for name in ('Content-Type','X-Total-Count','Cache-Control') if name in response.headers}
            return web.Response(body=await response.read(),status=response.status,headers=headers)
    async def source_index(request):
        names=('mempool-3.3.1.tar.gz','justverify.patch','build_mempool.sh','frontend-config.json','gbt-Cargo.lock','gbt-package-lock.json','BUILD.md','LICENSE','COPYING.md')
        return web.Response(text='<h1>Mempool 3.3.1 corresponding source</h1><p>Upstream source, JustVerify modifications and build instructions. Licensed under AGPL-3.0; upstream notices apply.</p><ul>'+''.join('<li><a href="/source/'+name+'">'+name+'</a></li>' for name in names)+'</ul>',content_type='text/html')
    async def source(request):
        files={'mempool-3.3.1.tar.gz','justverify.patch','build_mempool.sh','frontend-config.json','gbt-Cargo.lock','gbt-package-lock.json','BUILD.md','LICENSE','COPYING.md'}
        name=request.match_info['name']
        if name not in files: raise web.HTTPNotFound()
        return web.FileResponse(bundle/'source'/name)
    async def static(request):
        path=request.path.lstrip('/')
        if path=='justverify-integration.js': return web.FileResponse(Path(__file__).parent/'static/mempool-integration.js')
        root=(bundle/'web').resolve()
        lang=path.split('/')[0] if path.split('/')[0] in ('en-US','ko','ja') else 'en-US'
        for rel in (path,lang+'/'+path):
            file=(root/rel).resolve()
            if file.is_relative_to(root) and file.is_file():
                if file.name=='index.html': break
                return web.FileResponse(file)
        else:
            if Path(path).suffix: raise web.HTTPNotFound()
            file=root/lang/'index.html'
        if not file.is_file(): raise web.HTTPServiceUnavailable(text='Bundled explorer files unavailable')
        html=file.read_text().replace('</body>','<script src="/justverify-integration.js"></script></body>')
        return web.Response(text=html,content_type='text/html',headers={'Cache-Control':'no-cache'})
    app.router.add_get('/justverify/status',status)
    app.router.add_get('/resources/config.js',config)
    app.router.add_get('/source/',source_index)
    app.router.add_get('/source/{name}',source)
    for path in ('/ws','/api/v1/ws'): app.router.add_get(path,websocket)
    app.router.add_route('*','/api/{path:.*}',api)
    app.router.add_get('/{path:.*}',static)
    return app

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--bundle',type=Path,default=Path('/opt/justverify/mempool'))
    p.add_argument('--runtime',type=Path,default=Path('/run/justverify-mempool'))
    p.add_argument('--profile',type=Path,default=Path('/etc/justverify/profile.json'))
    p.add_argument('--port',type=int,default=3006)
    p.add_argument('--backend',default='http://127.0.0.1:8999')
    a=p.parse_args()
    web.run_app(make_app(a.bundle,a.runtime,a.profile,a.backend),host='0.0.0.0',port=a.port,access_log=None)
