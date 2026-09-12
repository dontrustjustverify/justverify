"""Fully Noded Quick Connect payload for one newly issued RPC client."""
import pathlib,re,urllib.parse
import qrcode

def quick_connect(client,hostname_path=pathlib.Path('/run/justverify-tor/rpc.hostname')):
 host=hostname_path.read_text().strip()
 if not re.fullmatch(r'[a-z2-7]{56}\.onion',host):raise ValueError('valid generated v3 RPC hostname required')
 if not isinstance(client,dict) or not re.fullmatch(r'[a-f0-9]{32}',client.get('id','')) or not re.fullmatch(r'[a-f0-9]{48}',client.get('password','')):raise ValueError('fresh RPC client required')
 label=client.get('label')
 if not isinstance(label,str) or not 1<=len(label)<=64:raise ValueError('valid label required')
 payload='btcrpc://{}:{}@{}:8332?label={}'.format(urllib.parse.quote(client['id'],safe=''),urllib.parse.quote(client['password'],safe=''),host,urllib.parse.quote(label,safe=''))
 qr=qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M,border=4);qr.add_data(payload);qr.make(fit=True)
 return {'payload':payload,'matrix':qr.get_matrix(),'format':'Fully Noded btcrpc Quick Connect','source_commit':'d0d1502eef2840c0457aa321b88cf606ee8b4650'}
