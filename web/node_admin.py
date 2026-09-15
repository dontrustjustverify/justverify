"""Authenticated web controls reuse the existing validated local transactions."""
import asyncio
import contextlib
import json
import pathlib

SOCKETS = {'device': '/run/justverify-device/control.sock','versions': '/run/justverify-versions/control.sock',
           'policy': '/run/justverify-policy/control.sock',
           'storage': '/run/justverify-storage/api.sock'}


async def call(service, body):
    writer = None
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_unix_connection(SOCKETS[service]), 3)
        writer.write(json.dumps(body).encode() + b'\n')
        await writer.drain()
        async def read():
            data = bytearray()
            while len(data) <= 2 * 1024 * 1024:
                chunk = await reader.read(65536)
                if not chunk:
                    return json.loads(data)
                data.extend(chunk)
            raise ValueError('service response too large')
        response = await asyncio.wait_for(read(), 300)
        if not response.get('ok'):
            raise ValueError(response.get('error', '설정을 적용하지 못했습니다.'))
        return response['result']
    finally:
        if writer:
            writer.close()
            with contextlib.suppress(OSError):
                await writer.wait_closed()


def validate(service, body):
    schemas = {'state': {'method'}, 'recover': {'method'}, 'apply': {'method', 'token'}}
    schemas.update({'preview': {'method', 'values'}, 'preview_config': {'method', 'config'}} if service == 'policy' else {
        'preview': {'method', 'version', 'network', 'watch_only'}, 'download': {'method', 'version'}})
    if not isinstance(body, dict) or not isinstance(body.get('method'), str) or set(body) != schemas.get(body['method']):
        raise ValueError('지원하지 않는 설정 요청입니다.')
    for key, value in body.items():
        if key == 'values':
            if not isinstance(value, dict) or len(value) > 128 or any(not isinstance(k, str) or not isinstance(v, str) or len(v) > 256 for k, v in value.items()):
                raise ValueError('설정 값은 문자열이어야 합니다.')
        elif key == 'config':
            if not isinstance(value, str) or len(value.encode()) > 8192:
                raise ValueError('설정 파일은 8192 bytes 이하의 텍스트여야 합니다.')
        elif key == 'watch_only':
            if not isinstance(value, bool):
                raise ValueError('잘못된 지갑 모드입니다.')
        elif not isinstance(value, str) or len(value) > 256:
            raise ValueError('잘못된 설정 값입니다.')


class Startup:
    def __init__(self):
        self.lock = asyncio.Lock()

    async def start(self):
        # Idempotent: never switch an existing selection or recover a failed
        # transaction automatically. Privileged helper verifies owner, empty
        # provisioned volume, identity and binary hashes before initial commit.
        async with self.lock:
            try:
                state = await call('versions', {'method': 'state'})
            except (FileNotFoundError, ConnectionRefusedError):
                await call('storage', {'action': 'prepare_profile'})
                state = await call('versions', {'method': 'state'})
            if state.get('active_error') or state.get('transition', {}).get('needs_recovery'):
                raise ValueError('이전 변경의 복구가 필요합니다. 버전 변경 화면에서 상태를 확인하세요.')
            if state.get('active'):
                return {'started': False, 'active': state['active']}
            await call('storage', {'action': 'prepare_profile'})
            profile = json.loads(pathlib.Path('/etc/justverify/profile.json').read_text())
            preview = await call('versions', {'method': 'preview', 'version': profile['version'],
                                             'network': profile['network'], 'watch_only': False})
            active = await call('versions', {'method': 'apply', 'token': preview['token']})
            return {'started': True, 'active': active}
