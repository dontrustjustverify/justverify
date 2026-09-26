#!/usr/bin/env python3
"""Public Tor Electrum endpoint as plain host:port, not an app-specific import URI."""
import hashlib,json,pathlib,re,socket,ssl,subprocess,sys,qrcode

def lan_endpoint(require_ready=True,tls=False):
 active=subprocess.run(['systemctl','is-active','--quiet','justverify-electrum-tls'],capture_output=True,timeout=3).returncode==0
 port=50002 if tls else 50001;fingerprint=''
 if tls:
  certificate=pathlib.Path('/var/lib/justverify/web/certificate.pem')
  fingerprint=hashlib.sha256(ssl.PEM_cert_to_DER_cert(certificate.read_text())).hexdigest()
 try:
  with socket.create_connection(('127.0.0.1',port),timeout=1) as transport:
   if tls:
    with ssl.create_default_context(cafile=str(certificate)).wrap_socket(transport,server_hostname='justverify.local'):pass
 except (OSError,ValueError):active=False
 if require_ready and not active:raise ValueError('Selected LAN service is not active')
 payload=f'justverify.local:{port}'
 qr=qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M,border=4);qr.add_data(payload);qr.make(fit=True)
 return {'payload':payload,'matrix':qr.get_matrix(),'protocol':'Electrum TLS over LAN' if tls else 'Electrum TCP over LAN','tls':tls,'service_active':active,'backend_active':subprocess.run(['systemctl','is-active','--quiet','justverify-electrs'],capture_output=True,timeout=3).returncode==0,'certificate_sha256':fingerprint,'format':'plain host:port; select SSL/TLS in wallet' if tls else 'plain host:port; disable SSL/TLS in wallet'}

def endpoint(path=pathlib.Path('/run/justverify-tor/electrum.hostname')):
 host=path.read_text().strip()
 if not re.fullmatch('[a-z2-7]{56}\\.onion',host):raise ValueError('valid generated v3 Electrum hostname required')
 payload=host+':50001'
 qr=qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M,border=4);qr.add_data(payload);qr.make(fit=True)
 return {'payload':payload,'matrix':qr.get_matrix(),'protocol':'Electrum TCP over Tor','tls':False,'service_active':subprocess.run(['systemctl','is-active','--quiet','justverify-tor'],capture_output=True,timeout=3).returncode==0,'backend_active':subprocess.run(['systemctl','is-active','--quiet','justverify-electrs'],capture_output=True,timeout=3).returncode==0,'proxy':'Tor SOCKS proxy on the wallet device','format':'plain host:port; app auto-import not asserted'}
if __name__=='__main__':
 try:
  if sys.argv[1:] not in ([],['--lan'],['--lan-tls']):raise ValueError('unsupported endpoint selection')
  print(json.dumps({'ok':True,'result':lan_endpoint(tls=sys.argv[1:]==['--lan-tls']) if sys.argv[1:] else endpoint()}))
 except Exception:print(json.dumps({'ok':False,'error':'Selected Electrum endpoint unavailable.'}));sys.exit(1)
