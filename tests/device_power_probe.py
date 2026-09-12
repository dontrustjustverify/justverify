#!/usr/bin/env python3
"""Invoke reviewed power API only on the disposable justverify-dev VM."""
import asyncio,json,pathlib,subprocess,sys
import aiohttp
ROOT=pathlib.Path(__file__).resolve().parents[1]
ORIGIN='http://127.0.0.1:28646'
async def main():
 host=subprocess.run([str(ROOT/'scripts/vm_ssh.sh'),'hostname'],capture_output=True,text=True,check=True).stdout.strip();assert host=='justverify-dev'
 before=subprocess.run([str(ROOT/'scripts/vm_ssh.sh'),'cat /proc/sys/kernel/random/boot_id; sudo sha256sum /var/lib/justverify-device-test/preferences.json /var/lib/justverify-device-test/admin.json /var/lib/justverify-device-test/remote-web.json; systemctl is-active justverify-core justverify-electrs'],capture_output=True,text=True,check=True).stdout
 (ROOT/'.state/device-settings'/('before-'+sys.argv[1]+'.txt')).write_text(before)
 async with aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True)) as c:
  h={'Origin':ORIGIN}
  async with c.post(ORIGIN+'/login',headers=h,json={'password':'Device-Test-2026!'}) as r:assert r.status==200;h['X-CSRF-Token']=(await r.json())['csrf']
  async with c.post(ORIGIN+'/device-settings',headers=h,json={'action':'power_preview','operation':sys.argv[1]}) as r:assert r.status==200;token=(await r.json())['token']
  async with c.post(ORIGIN+'/device-settings',headers=h,json={'action':'apply','token':token,'password':'Device-Test-2026!'}) as r:assert r.status==200;result=await r.json();assert result['queued']==sys.argv[1]
 print('POWER QUEUED: '+sys.argv[1]+'; verify actual boot/shutdown separately')
asyncio.run(main())
