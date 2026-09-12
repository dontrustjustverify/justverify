#!/usr/bin/env python3
"""Resource controls from each actually executed Core help and official init source.
Bounds prevent native conversion overflow; device capacity still needs preflight.
"""
import hashlib,json,pathlib,re
ROOT=pathlib.Path(__file__).resolve().parents[1]
RULES={
 'bantime':(0,2147483647,'seconds'),
 'maxconnections':(12,2147482623,'connections; minimum12 retains inbound capacity for electrs'),
 'maxreceivebuffer':(1,9223372036854775,'kB (1000 bytes) per connection'),
 'maxsendbuffer':(1,9223372036854775,'kB (1000 bytes) per connection'),
 'peertimeout':(1,2147483647,'seconds'),
 'timeout':(1,2147483647,'milliseconds'),
 'maxuploadtarget':(0,8796093022207,'MiB per24h; 0 unlimited; recent blocks and download peers exempt'),
 'dbcache':(4,8796093022207,'MiB; unused mempool cache is additional'),
 'rpcworkqueue':(1,2147483647,'queued RPC requests'),
}
BOOLEANS={'txindex','txospenderindex','blockfilterindex','peerblockfilters','peerbloomfilters','rest','asmap'}
RULES.update({k:(0,1,'0 disabled / 1 enabled') for k in sorted(BOOLEANS)})
for release in json.loads((ROOT/'catalog/releases.json').read_text())['releases']:
 version=release['version'];folder=ROOT/'docs/evidence/core-matrix'/version
 if not (folder/'help-debug.txt').exists():continue
 text=(folder/'help-debug.txt').read_text();source=(ROOT/'.cache/core'/version/'init.cpp').read_bytes()
 rows=[]
 for key,(minimum,maximum,unit) in RULES.items():
  match=re.search(r'^  -'+key+r'(?:=\S+)?\n(.*?)(?=\n  -|\Z)',text,re.M|re.S)
  if not match:continue
  description=' '.join(line.strip() for line in match[1].splitlines() if line.startswith(' '))
  if key=='asmap' and 'embedded mapping' not in description:continue
  default=re.search(r'default: ([^),]+)',description)
  if key=='asmap':default=['','0']
  assert default and ('"-'+key).encode() in source,(version,key)
  if key=='dbcache':
   span=re.search(r'\((\d+) to (\d+),',description)
   if span:minimum,maximum=map(int,span.groups())
  rows.append({'core_version':version,'key':key,'type':'boolean' if key in BOOLEANS else 'integer','unit':unit,'default':default[1],
    'range':{'min':minimum,'max':maximum,'meaning':'JustVerify accepted range; native width/unit overflow excluded; available memory/file descriptors checked separately'},
    'network_scope':release['networks'],'source':f'https://github.com/bitcoin/bitcoin/blob/v{version}/src/init.cpp',
    'source_sha256':hashlib.sha256(source).hexdigest(),'help_sha256':hashlib.sha256(text.encode()).hexdigest(),
    'source_registration_present':True,'ignored_or_wallet_only':False,'restart_required':True,'editable':True,
    'advanced':key not in {'txindex','txospenderindex','blockfilterindex','peerblockfilters','peerbloomfilters','rest','asmap','dbcache','bantime','maxconnections','maxreceivebuffer','maxsendbuffer','maxuploadtarget','timeout'},'introduced_removed_changed':'actual availability/defaults in this executed Core release','dependencies':['blockfilterindex=1'] if key=='peerblockfilters' else [],'conflicts':['prune'] if key in {'txindex','txospenderindex'} else [],'description':description,'verification_method':'executed help and official registration; real startup, log and observable RPC acceptance required'})
 (ROOT/'catalog'/f'resources-{version}.json').write_text(json.dumps(rows,indent=2)+'\n')
 print(version,len(rows))
