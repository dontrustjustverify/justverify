#!/usr/bin/python3 -I
"""Dedicated physical console: ownership information never goes to journal/stdout pipes."""
import hashlib,os,pathlib,select,ssl,sys,time
STATE=pathlib.Path('/var/lib/justverify/web')
if not sys.stdin.isatty() or not sys.stdout.isatty():raise SystemExit('physical terminal required')
while not (STATE/'admin.json').exists():
 print('\033[2J\033[HJustVerify setup\nhttp://justverify.local\nOpen the address above and choose a new administrator password.',flush=True)
 while not (STATE/'admin.json').exists():
  if select.select([sys.stdin],[],[],1)[0]:
   sys.stdin.readline()
   token=STATE/'setup-token'
   if token.exists():
    cert=ssl.PEM_cert_to_DER_cert((STATE/'certificate.pem').read_text())
    print('Certificate SHA256: '+hashlib.sha256(cert).hexdigest(),flush=True)
    print('One-time code: '+token.read_text().strip(),flush=True)
    print('Complete owner setup in the browser to open the node TUI.',flush=True)
  time.sleep(.2)
print('\033[2J\033[H',end='',flush=True)
os.execv('/opt/justverify/bin/justverify',['justverify','tui','--socket','/run/justverify/manager.sock'])
