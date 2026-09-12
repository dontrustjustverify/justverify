#!/usr/bin/env python3
"""Inventory official stable releases without silently claiming compatibility."""
import json,re,urllib.request,pathlib,datetime
R=pathlib.Path(__file__).resolve().parents[1]
def read(url):
    with urllib.request.urlopen(url,timeout=30) as r:return r.read().decode()
listing=read('https://bitcoincore.org/bin/')
versions=set(re.findall(r'href="bitcoin-core-(\d+\.\d+(?:\.\d+)?)/"',listing))
# Release pages also retain historical releases no longer at the top-level download directory.
pages=read('https://bitcoincore.org/en/releases/')
versions.update(re.findall(r'/en/releases/(\d+\.\d+(?:\.\d+)?)/',pages))
versions=sorted((v for v in versions if int(v.split('.')[0])>=22),key=lambda v:tuple(map(int,v.split('.'))))
rows=[]
for v in versions:
    rows.append(dict(version=v,source=f'https://bitcoincore.org/bin/bitcoin-core-{v}/',release_notes=f'https://bitcoincore.org/en/releases/{v}/',architectures=['aarch64-linux-gnu','x86_64-linux-gnu'],verification='NOT RUN',electrs='NOT RUN',data_reuse='DENY_UNVERIFIED',configuration_schema='NOT RUN',support_status='review upstream EOL notices'))
(R/'catalog/releases.json').write_text(json.dumps({'retrieved':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source':'https://bitcoincore.org/bin/','releases':rows},indent=2)+'\n')
print('Inventoried',len(rows),'stable versions:',', '.join(versions))
