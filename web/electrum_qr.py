#!/usr/bin/env python3
"""Public Tor Electrum endpoint as plain host:port, not an app-specific import URI."""
import hashlib,json,pathlib,re,ssl,subprocess,sys,qrcode

def lan_endpoint(require_ready=True):
 active=subprocess.run(['systemctl','is-active','--quiet','justverify-electrum-tls'],capture_output=True,timeout=3).returncode==0
 if require_ready and not active:raise ValueError('LAN TLS service is not active')
 certificate=pathlib.Path('/var/lib/justverify/web/certificate.pem').read_text()
 fingerprint=hashlib.sha256(ssl.PEM_cert_to_DER_cert(certificate)).hexdigest()
 payload='justverify.local:50002'
 qr=qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M,border=4);qr.add_data(payload);qr.make(fit=True)
 return {'payload':payload,'matrix':qr.get_matrix(),'protocol':'Electrum TLS over LAN','tls':True,'service_active':active,'backend_active':subprocess.run(['systemctl','is-active','--quiet','justverify-electrs'],capture_output=True,timeout=3).returncode==0,'certificate_sha256':fingerprint,'format':'plain host:port; select SSL/TLS in wallet; app auto-import not asserted'}

def endpoint(path=pathlib.Path('/run/justverify-tor/electrum.hostname')):
 host=path.read_text().strip()
 if not re.fullmatch('[a-z2-7]{56}\\.onion',host):raise ValueError('valid generated v3 Electrum hostname required')
 payload=host+':50001'
 qr=qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M,border=4);qr.add_data(payload);qr.make(fit=True)
 return {'payload':payload,'matrix':qr.get_matrix(),'protocol':'Electrum TCP over Tor','tls':False,'service_active':subprocess.run(['systemctl','is-active','--quiet','justverify-tor'],capture_output=True,timeout=3).returncode==0,'backend_active':subprocess.run(['systemctl','is-active','--quiet','justverify-electrs'],capture_output=True,timeout=3).returncode==0,'proxy':'Tor SOCKS proxy on the wallet device','format':'plain host:port; app auto-import not asserted'}
if __name__=='__main__':
 try:
  if sys.argv[1:] not in ([],['--lan']):raise ValueError('unsupported endpoint selection')
  print(json.dumps({'ok':True,'result':lan_endpoint() if sys.argv[1:] else endpoint()}))
 except Exception:print(json.dumps({'ok':False,'error':'Selected Electrum endpoint unavailable.'}));sys.exit(1)
