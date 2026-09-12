#!/usr/bin/env python3
"""Attach bounded behavioral evidence without claiming exhaustive policy coverage."""
import hashlib,json,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
CASES={
 'maxmempool':['5 MB pressure'], 'mempoolexpiry':['one-hour expiry'],
 'persistmempool':['persistmempool='], 'datacarrier':['datacarrier disabled'],
 'datacarriersize':['OP_RETURN script','multiple OP_RETURN'],
 'permitbaremultisig':['bare multisig'], 'dustrelayfee':['P2WPKH dust','dust fee zero'],
 'minrelaytxfee':['5 sat/vB minimum'], 'blockmintxfee':['blockmintxfee'],
 'acceptnonstdtxn':['regtest standardness disabled'],
}
TOPOLOGY={
 'limitancestorcount':['limitancestorcount'], 'limitancestorsize':['limitancestorsize'],
 'limitdescendantcount':['descendant parent','first descendant','second descendant'],
 'limitdescendantsize':['descendant-size parent','descendant aggregate','same descendant accepted'],
 'limitclustercount':['limitclustercount'], 'limitclustersize':['limitclustersize'],
 'incrementalrelayfee':['incremental fee'], 'mempoolfullrbf':['non-signaling'],
}
def annotate(rows,version):
 path=ROOT/'docs/evidence/policy-semantics'/(version+'.json')
 report=json.loads(path.read_text()) if path.exists() else {}
 release=next(r for r in json.loads((ROOT/'catalog/releases.json').read_text())['releases'] if r['version']==version)
 if report and (report.get('status')!='PASS' or report.get('binary_sha256')!=release['arm64_binary_sha256']):raise ValueError('policy evidence differs from verified release')
 topology_path=ROOT/'docs/evidence/policy-topology'/(version+'.json')
 topology=json.loads(topology_path.read_text()) if topology_path.exists() else {}
 if topology and (topology.get('status')!='PASS' or topology.get('binary_sha256')!=release['arm64_binary_sha256']):raise ValueError('topology evidence differs from verified release')
 for row in rows:
  row['editable']=row['source_registration_present'] and not row['ignored_or_wallet_only']
  row['editability_basis']='src/policy.rs version/network/conflict validation; editability is independent of exhaustive behavioral verification'
  selected,selected_path,mapping=(topology,topology_path,TOPOLOGY) if row['key'] in TOPOLOGY else (report,path,CASES)
  if selected and row['key'] in mapping and not row['ignored_or_wallet_only']:
   cases=[c for c in selected['cases'] if any(text in c['case'] for text in mapping[row['key']])]
   if not cases:raise ValueError('missing stated policy behavior case')
   row['behavior_evidence']={'network':'regtest','report':str(selected_path.relative_to(ROOT)),'report_sha256':hashlib.sha256(selected_path.read_bytes()).hexdigest(),'test_sha256':selected['test_sha256'],'cases':[c['case'] for c in cases],'full_range_verified':False}
   row['review']='SELECTED_BEHAVIOR_VERIFIED; FULL_RANGE_REVIEW_PENDING'
   row['verification_method']='executed version help/source registration and listed signed-transaction regtest cases; entire range and all networks NOT RUN'
 return rows
if __name__=='__main__':
 for path in sorted((ROOT/'catalog').glob('policy-*.json')):
  if path.name=='policy-diff.json':continue
  version=path.stem.removeprefix('policy-')
  if not version[0].isdigit():continue
  rows=annotate(json.loads(path.read_text()),version)
  path.write_text(json.dumps(rows,indent=2)+'\n')
