#!/usr/bin/env python3
"""Root bridge rejects bypasses; actual switching uses the reviewed native API."""
from version_reset_native import *

before=okay('state')['active'];height=rpc('getblockcount')
for request in ({'action':'stop','command':'id'},{'action':'activate','version':'../31.1','network':'regtest'},
                {'action':'activate','version':'30.0','network':'regtest'},
                {'action':'activate','version':'22.0' if before['instance']['core_version']=='31.1' else '31.1','network':'regtest'},
                {'action':'activate','version':'22.0','network':'testnet4'},
                {'action':'reset','path':'/'}):
 result=subprocess.run(['runuser','-u','justverify','--','sudo','-n','/usr/libexec/justverify-profile'],input=json.dumps(request),capture_output=True,text=True)
 assert result.returncode!=0,'unsafe bridge input accepted'
assert okay('state')['active']==before and rpc('getblockcount')==height
print('PASS fixed root bridge rejects paths, unregistered activation, unknown actions and unsupported combinations before stopping services')
