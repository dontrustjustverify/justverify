#!/usr/bin/env python3
"""Authenticate a first-boot certificate using an off-device ownership secret; sends no secret."""
import argparse,hashlib,hmac,http.client,json,pathlib,ssl

def verify(host,port,owner_file):
 owner=json.loads(pathlib.Path(owner_file).read_text())
 if owner.get('format')!='justverify-owner-v1':raise ValueError('wrong owner file format')
 # The fetched certificate is untrusted until the secret-bound proof succeeds below.
 context=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT);context.check_hostname=False;context.verify_mode=ssl.CERT_NONE
 connection=http.client.HTTPSConnection(host,port,context=context,timeout=10)
 try:
  connection.connect();der=connection.sock.getpeercert(binary_form=True)
  connection.request('GET','/pairing-proof');response=connection.getresponse()
  if response.status!=200:raise ValueError('pairing not available or device already claimed')
  proof=json.loads(response.read(4097))
  expected=hmac.new(owner['setup_token'].encode(),b'JustVerify TLS pairing v1\0'+hashlib.sha256(der).digest(),hashlib.sha256).hexdigest()
  if proof.get('algorithm')!='hmac-sha256-cert-der-v1' or not hmac.compare_digest(expected,str(proof.get('proof',''))):raise ValueError('certificate ownership proof failed')
  return der
 finally:connection.close()

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('host');parser.add_argument('--port',type=int,default=443);parser.add_argument('--owner-file',type=pathlib.Path,required=True);parser.add_argument('--certificate-out',type=pathlib.Path,required=True);args=parser.parse_args()
 der=verify(args.host,args.port,args.owner_file)
 with args.certificate_out.open('x') as file:file.write(ssl.DER_cert_to_PEM_cert(der))
 print('Ownership proof PASS. Certificate SHA256: '+hashlib.sha256(der).hexdigest())
