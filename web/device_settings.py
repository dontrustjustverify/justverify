"""Owner preferences and narrow device controls; no shell or user paths."""
import asyncio, hmac, json, pathlib, secrets, time, unicodedata
from aiohttp import web
from node_admin import call

DEFAULTS = {'schema': 1, 'name': 'justverify', 'theme': 'teal', 'language': 'ko'}

def validate(value):
    if not isinstance(value, dict) or set(value) != set(DEFAULTS) or type(value['schema']) is not int or value['schema'] != 1:
        raise ValueError('잘못된 설정 형식입니다.')
    if value['theme'] not in ('teal', 'amber', 'green', 'ice') or value['language'] not in ('ko', 'en', 'ja'):
        raise ValueError('지원하지 않는 색상 또는 언어입니다.')
    name = value['name']
    if not isinstance(name, str) or not 1 <= len(name) <= 40 or name != name.strip() or any(unicodedata.category(c).startswith('C') for c in name):
        raise ValueError('계정명은 제어문자 없이 1~40자로 입력하세요.')
    return value

class DeviceSettings:
    def __init__(self, bridge, atomic, password_hash):
        self.bridge=bridge; self.atomic=atomic; self.password_hash=password_hash
        self.path=bridge.state/'preferences.json'; self.plans={}; self.lock=asyncio.Lock()
    def preferences(self):
        return validate(json.loads(self.path.read_text())) if self.path.exists() else dict(DEFAULTS)
    def verify_password(self, request, password):
        self.bridge.limited(request)
        if not isinstance(password, str) or not 12 <= len(password) <= 256: raise web.HTTPUnauthorized()
        record=json.loads((self.bridge.state/'admin.json').read_text())
        if not hmac.compare_digest(self.password_hash(password,record['salt']),record['hash']):
            raise web.HTTPUnauthorized(text='현재 암호가 맞지 않습니다.')
        self.bridge.attempts[request.remote].pop()
    async def request(self, request):
        self.bridge.same_origin(request); self.bridge.read_session(request)
        try:
            body=await request.json()
            if not isinstance(body,dict): raise ValueError('잘못된 요청입니다.')
            async with self.lock:
                result=await self.manage(request,body)
            return web.json_response(result)
        except web.HTTPException: raise
        except (ValueError, TypeError, KeyError): raise web.HTTPBadRequest(text='설정 값을 확인하고 다시 시도하세요.')
        except (OSError, asyncio.TimeoutError): raise web.HTTPServiceUnavailable(text='기기 관리 서비스에 연결하지 못했습니다.')
    async def manage(self, request, body):
        if body == {'action':'state'}:
            try: device=await call('device',{'action':'state'})
            except (OSError, ValueError, asyncio.TimeoutError): device={'unavailable':True}
            return {'preferences':self.preferences(),'device':device,'remote_web':self.bridge.remote_web.status()}
        if set(body)=={'action','theme','language'} and body['action']=='preferences':
            value=self.preferences(); value.update(theme=body['theme'],language=body['language']);validate(value)
            self.atomic(self.path,json.dumps(value,ensure_ascii=False));return {'preferences':self.preferences()}
        if set(body)=={'action','name'} and body['action']=='name':
            value=self.preferences();value['name']=body['name'];validate(value)
            self.atomic(self.path,json.dumps(value,ensure_ascii=False));return {'preferences':self.preferences()}
        if set(body)=={'action','current_password','password','password_confirm'} and body['action']=='password':
            password=body['password']
            if not isinstance(password,str) or not 12<=len(password)<=256 or password!=body['password_confirm']:raise ValueError('Password mismatch')
            self.verify_password(request,body['current_password'])
            salt=secrets.token_hex(16)
            self.atomic(self.bridge.state/'admin.json',json.dumps({'salt':salt,'hash':self.password_hash(password,salt)}))
            self.bridge.sessions.clear();self.bridge.save_sessions()
            for ws in list(self.bridge.active): await ws.close()
            return {'reauthenticate':True}
        if set(body)=={'action','enabled'} and body['action']=='tor_preview' and type(body['enabled']) is bool:
            result=await self.bridge.remote_web.manage({'action':'preview','enabled':body['enabled']})
            # Bind the review to the owner session, not merely a bearer token.
            self.plans[result['token']]={'session':self.bridge.session(request),'expires':time.monotonic()+120,'action':'tor'}
            return result
        if set(body)=={'action','operation'} and body['action']=='power_preview' and body['operation'] in ('reboot','shutdown'):
            self.plans={k:v for k,v in self.plans.items() if v['expires']>time.monotonic()}
            if len(self.plans)>=16:raise ValueError('Too many pending reviews')
            token=secrets.token_urlsafe(32)
            self.plans[token]={'session':self.bridge.session(request),'expires':time.monotonic()+120,'action':body['operation']}
            return {'token':token,'operation':body['operation']}
        if set(body)=={'action','token','password'} and body['action']=='apply' and isinstance(body['token'],str):
            plan=self.plans.pop(body['token'],None)
            if not plan or plan['expires']<=time.monotonic() or plan['session'] is not self.bridge.session(request):raise web.HTTPConflict(text='변경 확인이 만료되었습니다. 다시 선택하세요.')
            self.verify_password(request,body['password'])
            if plan['action']=='tor':return await self.bridge.remote_web.manage({'action':'apply','token':body['token']})
            return await call('device',{'action':plan['action']})
        raise ValueError('Unsupported device request')
