#!/usr/bin/env python3
"""Digital QR decoding is separate from actual phone-camera/app acceptance."""
import json,pathlib,hashlib,qrcode,zxingcpp
from PIL import Image
R=pathlib.Path(__file__).resolve().parents[1];out=R/'.state/qr';out.mkdir(parents=True,exist_ok=True)
payloads=['192.168.1.123:50002']
host=R/'.state/tor-test/electrum/hostname'
if host.exists():payloads.append(host.read_text().strip()+':50001')
results=[]
for n,payload in enumerate(payloads):
    qr=qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M,box_size=10,border=4);qr.add_data(payload);qr.make(fit=True)
    path=out/f'endpoint-{n}.png';qr.make_image(fill_color='black',back_color='white').save(path)
    decoded=zxingcpp.read_barcode(Image.open(path));assert decoded and decoded.text==payload
    results.append({'kind':'onion endpoint' if '.onion' in payload else 'LAN endpoint example','payload_sha256':hashlib.sha256(payload.encode()).hexdigest(),'quiet_zone_modules':4,'decoded_exact':True,'dimensions':Image.open(path).size})
(R/'docs/evidence/qr-roundtrip.json').write_text(json.dumps({'status':'PASS','checks':results,'scope':'digital decoder only; NOT actual camera or app import','payload_format':'plain host:port; no claim of automatic wallet import'},indent=2)+'\n')
print('QR encode/decode exact PASS; actual phone camera NOT RUN')
