#!/usr/bin/env python3
import importlib.util,pathlib,unittest
spec=importlib.util.spec_from_file_location('inventory',pathlib.Path(__file__).resolve().parents[1]/'scripts/disk_inventory.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class Boundaries(unittest.TestCase):
 def test_separate_data_partition_on_system_nvme(self):
  result=module.classify({'blockdevices':[{'name':'/dev/nvme0n1','type':'disk','children':[
   {'name':'/dev/nvme0n1p1','type':'part','mountpoints':['/boot']},
   {'name':'/dev/nvme0n1p2','type':'part','mountpoints':['/']},
   {'name':'/dev/nvme0n1p3','type':'part','fstype':'ext4','uuid':'data-uuid','mountpoints':[]}]}]})
  rows={r['name']:r for r in result['devices']}
  self.assertEqual(rows['/dev/nvme0n1']['review_action'],'NONE')
  self.assertEqual(rows['/dev/nvme0n1p2']['reason'],'SYSTEM_DEVICE')
  self.assertEqual(rows['/dev/nvme0n1p3']['review_action'],'REVIEW_EXISTING')
 def test_duplicate_uuid_and_nested_usage(self):
  result=module.classify({'blockdevices':[{'name':'disk','type':'disk','fstype':'ext4','uuid':'x','children':[{'name':'part','type':'part','children':[{'name':'mapped','type':'crypt','mountpoints':['/mnt/other']}]}]},{'name':'other','type':'part','fstype':'ext4','uuid':'x'}]})
  rows={r['name']:r for r in result['devices']}
  self.assertEqual(rows['disk']['reason'],'CHILD_IN_USE')
  self.assertEqual(rows['other']['reason'],'AMBIGUOUS_FILESYSTEM_UUID')
 def test_untrusted_labels(self):
  result=module.classify({'blockdevices':[{'name':'disk','type':'disk','serial':'abc\x1b\u202etest'}]})
  self.assertNotIn('\x1b',result['devices'][0]['serial']);self.assertNotIn('\u202e',result['devices'][0]['serial'])
if __name__=='__main__':unittest.main()
