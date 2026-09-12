#!/usr/bin/env python3
"""Read-only storage inventory. Eligibility is a review aid, never permission to erase."""
import hashlib,json,pathlib,subprocess,unicodedata
DATA_MOUNT='/srv/justverify/data'
def clean(value):
 return ''.join(c for c in str(value or '') if unicodedata.category(c)[0]!='C')
def classify(tree):
 nodes={};parents={}
 def visit(node,parent=None):
  name=node['name'];nodes[name]=node
  if parent:parents.setdefault(name,set()).add(parent)
  for child in node.get('children',[]):visit(child,name)
 for node in tree['blockdevices']:visit(node)
 protected=set()
 for name,node in nodes.items():
  mounts=node.get('mountpoints') or []
  if any(m=='/' or (m and (m=='/boot' or m.startswith('/boot/'))) for m in mounts):
   stack=[name]
   while stack:
    current=stack.pop()
    if current in protected:continue
    protected.add(current);stack.extend(parents.get(current,()))
 in_use=set()
 for name,node in nodes.items():
  if any(node.get('mountpoints') or []):
   stack=list(parents.get(name,()))
   while stack:
    parent=stack.pop()
    if parent in in_use:continue
    in_use.add(parent);stack.extend(parents.get(parent,()))
 uuid_counts={}
 for node in nodes.values():
  if node.get('uuid'):uuid_counts[node['uuid']]=uuid_counts.get(node['uuid'],0)+1
 rows=[]
 for name,node in nodes.items():
  mounts=[clean(m) for m in node.get('mountpoints') or [] if m]
  children=node.get('children',[])
  reason='';action='NONE'
  if name in protected:reason='SYSTEM_DEVICE'
  elif node.get('ro'):reason='READ_ONLY'
  elif DATA_MOUNT in mounts:reason='CURRENT_DATA_MOUNT'
  elif mounts:reason='ALREADY_MOUNTED'
  elif node.get('type') not in ('disk','part'):reason='UNSUPPORTED_DEVICE_TYPE'
  elif name in in_use:reason='CHILD_IN_USE'
  elif node.get('uuid') and uuid_counts[node['uuid']]!=1:reason='AMBIGUOUS_FILESYSTEM_UUID'
  elif node.get('fstype')=='ext4' and node.get('uuid'):reason='EXISTING_FILESYSTEM_REQUIRES_CONTENT_REVIEW';action='REVIEW_EXISTING'
  elif children:reason='EXISTING_PARTITIONS_PRESERVED'
  elif node.get('fstype'):reason='UNSUPPORTED_FILESYSTEM_PRESERVED'
  elif (node.get('type')=='disk' and (node.get('serial') or node.get('wwn'))) or (node.get('type')=='part' and node.get('partuuid')):reason='SIGNATURE_SCAN_AND_EXPLICIT_CONFIRMATION_REQUIRED';action='REVIEW_NEW'
  else:reason='NO_STABLE_DEVICE_ID'
  row={key:clean(node.get(key)) for key in ('name','type','fstype','uuid','model','serial','wwn','tran','partuuid','maj:min')}
  row.update(size_bytes=int(node.get('size') or 0),read_only=bool(node.get('ro')),mountpoints=mounts,reason=reason,review_action=action)
  row['identity_digest']=hashlib.sha256(json.dumps(row,sort_keys=True,separators=(',',':')).encode()).hexdigest()
  rows.append(row)
 return {'devices':rows,'mutations_performed':False,'notice':'No disk is formatted or mounted by inventory. Revalidate identity and contents before any operation.'}
def inventory():
 result=subprocess.run(['lsblk','--json','--bytes','--paths','-o','NAME,TYPE,SIZE,FSTYPE,UUID,MOUNTPOINTS,PKNAME,MODEL,SERIAL,WWN,TRAN,PARTUUID,MAJ:MIN,RO'],check=True,capture_output=True,text=True,timeout=10)
 if len(result.stdout)>4*1024*1024:raise ValueError('storage topology too large')
 return classify(json.loads(result.stdout))
if __name__=='__main__':print(json.dumps(inventory(),ensure_ascii=False,indent=2))
