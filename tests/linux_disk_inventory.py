#!/usr/bin/env python3
"""Inspect actual Linux block topology and prove system devices are excluded without writes."""
import hashlib,importlib.util,json,pathlib,socket,subprocess
assert socket.gethostname()=='justverify-dev'
root=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('inventory',root/'scripts/disk_inventory.py');inventory=importlib.util.module_from_spec(spec);spec.loader.exec_module(inventory)
fstab=pathlib.Path('/etc/fstab').read_bytes()
mounts=pathlib.Path('/proc/self/mountinfo').read_bytes()
result=inventory.inventory();rows={r['name']:r for r in result['devices']}
system=next(r for r in result['devices'] if '/' in r['mountpoints'])
assert system['reason']=='SYSTEM_DEVICE' and system['review_action']=='NONE'
assert any(r['type']=='disk' and r['reason']=='SYSTEM_DEVICE' for r in result['devices'])
assert all(r['reason']=='SYSTEM_DEVICE' for r in result['devices'] if any(m.startswith('/boot') for m in r['mountpoints']))
assert any(r['fstype']=='iso9660' and r['reason']=='READ_ONLY' for r in result['devices'])
current=next(r for r in result['devices'] if '/srv/justverify/data' in r['mountpoints'])
assert current['reason']=='CURRENT_DATA_MOUNT' and current['review_action']=='NONE'
assert pathlib.Path('/etc/fstab').read_bytes()==fstab
assert pathlib.Path('/proc/self/mountinfo').read_bytes()==mounts
assert not result['mutations_performed']
print(json.dumps({'status':'PASS','checks':['actual lsblk topology read','root backing disk and mounted boot partition protected','read-only seed disk protected','current data mount distinguished','fstab and mount table unchanged'],'inventory':result},indent=2))
