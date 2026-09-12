#!/usr/bin/env python3
"""Decode a Fully Noded QR fixture and validate every URI field."""
import hashlib,json,pathlib,sys,tempfile,urllib.parse
import zxingcpp
from PIL import Image
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'web'))
from rpc_qr import quick_connect

with tempfile.TemporaryDirectory(prefix='jv-rpc-qr-') as directory:
 hostname=pathlib.Path(directory)/'hostname';hostname.write_text('a'*56+'.onion\n')
 client={'id':'b'*32,'password':'c'*48,'label':'Phone test'}
 result=quick_connect(client,hostname);matrix=result['matrix'];size=len(matrix)
 assert all(not cell for row in matrix[:4] for cell in row)
 assert all(not row[column] for row in matrix for column in range(4))
 image=Image.new('L',(size,size),255);image.putdata([0 if cell else 255 for row in matrix for cell in row]);image=image.resize((size*10,size*10),Image.Resampling.NEAREST)
 decoded=zxingcpp.read_barcode(image);assert decoded and decoded.text==result['payload']
 parsed=urllib.parse.urlsplit(decoded.text);query=urllib.parse.parse_qs(parsed.query)
 assert (parsed.scheme,parsed.username,parsed.password,parsed.hostname,parsed.port)==('btcrpc',client['id'],client['password'],'a'*56+'.onion',8332)
 assert query=={'label':['Phone test']} and result['source_commit']=='d0d1502eef2840c0457aa321b88cf606ee8b4650'
 print(json.dumps({'status':'PASS','format':result['format'],'fully_noded_source_commit':result['source_commit'],'decoded_exact':True,'fields':['scheme','username','password','hostname','port','label'],'quiet_zone_modules':4,'matrix_size':size,'payload_sha256':hashlib.sha256(result['payload'].encode()).hexdigest(),'scope':'digital decoder and actual PTY module verification; phone camera/app import NOT RUN'},indent=2))
