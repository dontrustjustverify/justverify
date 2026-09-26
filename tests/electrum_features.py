#!/usr/bin/env python3
"""Protocol framing boundaries; actual daemon integration is tested separately."""
import json,pathlib,random,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'web'))
from electrum_features import FeatureReplies

def feature(identifier=50003):
    return {'id':identifier,'jsonrpc':'2.0','result':{
        'genesis_hash':'0'*64,'hosts':{'tcp_port':50003},'protocol_min':'1.4',
        'protocol_max':'1.4','pruning':None,'server_version':'electrs/0.11.1',
        'hash_function':'sha256'}}
def encode(value):return json.dumps(value,ensure_ascii=True).encode()
def transform(data,sizes,backend=50003):
    parser=FeatureReplies(backend);out=[];offset=0
    for size in sizes:
        out.append(parser.feed(data[offset:offset+size]));offset+=size
        assert parser.record is None or len(parser.record)<=parser.limit
    out.append(parser.feed(data[offset:]));out.append(parser.finish())
    return b''.join(out)

small=feature('quoted" \\ } [ 한글 50003');raw=encode(small)+b'\n'
expected=feature(small['id']);expected['result']['hosts']['tcp_port']=50001
for cut in range(len(raw)+1):assert json.loads(transform(raw,[cut]))==expected
assert json.loads(transform(raw,[1]*len(raw)))==expected
assert transform(raw,[7,19],backend=12345)==raw
others=[{'id':50003,'result':{'tcp_port':50003}},
        {'id':3,'error':{'message':'50003 \\" {}[]','code':-1}},
        {'method':'blockchain.headers.subscribe','params':[{'height':50003}]},
        {'id':4,'result':['abc\\','foo"bar',{'nested':feature()}]}]
for value in others:
    data=encode(value)+b'\n';assert transform(data,[1]*len(data))==data
large=encode({'id':9,'result':'a'*8_000_000})
batch=b'['+large+b', '+raw.strip()+b', '+encode(others[1])+b']\n'
pieces=[65536]*(len(batch)//65536)
result=transform(batch,pieces);parsed=json.loads(result)
assert parsed==[json.loads(large),expected,others[1]]
assert result.startswith(b'['+large+b', ')
stream=raw+b'\n'+encode(others[0])+b'\n'+batch+raw
rng=random.Random(417);sizes=[];remaining=len(stream)
while remaining:
    size=min(remaining,rng.randrange(1,65537));sizes.append(size);remaining-=size
lines=transform(stream,sizes).splitlines()
assert json.loads(lines[0])==expected and not lines[1]
assert json.loads(lines[2])==others[0] and json.loads(lines[3])==parsed
assert json.loads(lines[4])==expected
for fragment in (b'{"id":2,"result":{"unfinished":',b'{"id":3,"result":"'+b'a'*100000):
    assert transform(fragment,[1,4,33,65536])==fragment
oversized=encode(feature('x'*70000))+b'\n'
assert transform(oversized,[65536])==oversized
print(json.dumps({'status':'PASS','checks':['all split points and bytewise escaped-string framing',
    'only exact pinned feature schema and backend port changed; identifiers untouched',
    '8MB response and mixed batch preserve unrelated bytes',
    'streamed replies and notifications, fragmented EOF, bounded 64KiB buffer',
    'oversized individual reply passes unchanged without transport-size restriction']}))
