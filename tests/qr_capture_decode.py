#!/usr/bin/env python3
"""Decode captured terminal QR cells; never substitute freshly encoded modules."""
import hashlib,json,pathlib,sys
import zxingcpp
from PIL import Image
capture=json.loads(pathlib.Path(sys.argv[1]).read_text())
matrix=capture['matrix'];size=len(matrix)
assert 21<=size<=200 and all(len(row)==size and all(type(bit) is bool for bit in row) for row in matrix)
image=Image.new('L',(size,size),255)
image.putdata([0 if bit else 255 for row in matrix for bit in row])
image=image.resize((size*10,size*10),Image.Resampling.NEAREST)
decoded=zxingcpp.read_barcode(image)
assert decoded and decoded.text==capture['payload']
result={'status':'PASS','source':'actual PTY module capture','decoded_exact':True,'payload_sha256':hashlib.sha256(capture['payload'].encode()).hexdigest(),'scope':'digital decoder only; not phone camera or app import'}
pathlib.Path(sys.argv[2]).write_text(json.dumps(result,indent=2)+'\n')
print('PASS captured terminal QR decodes to exact endpoint; phone camera NOT RUN')
