#!/usr/bin/env python3
"""Accounting boundaries and malformed/rotated observation handling."""
import json
import pathlib
import sys
import tempfile
import types
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
from electrs_compaction import CompactionProgress, FAMILIES, MAX_READ, key_counts


def event(**value):
    return 'EVENT_LOG_v1 ' + json.dumps(value)


class ProgressTests(unittest.TestCase):
    def test_weighted_total_never_restarts_between_unequal_families(self):
        p = CompactionProgress('not-created', 0)
        p.counts = dict(zip(FAMILIES, (1, 9, 100, 300, 590)))
        self.assertEqual(p.estimate('txid')['percent_basis_points'], 100)
        p.observe(event(job=1, event='compaction_started', compaction_reason='ManualCompaction'))
        line = event(job=1, event='table_file_creation', cf_name='txid', file_number=20, table_properties={'num_entries':50})
        p.observe(line)
        self.assertEqual(p.estimate('txid')['percent_basis_points'], 600)
        p.observe(line)
        self.assertEqual(p.estimate('txid')['percent_basis_points'], 600)
        self.assertEqual(p.estimate('funding')['percent_basis_points'], 1100)
        self.assertEqual(p.estimate('spending')['percent_basis_points'], 4100)
        p.outputs['spending'] = 590
        self.assertEqual(p.estimate('spending')['percent_basis_points'], 9999)
        self.assertFalse(p.estimate('spending')['complete'])
        self.assertEqual(p.snapshot(types.SimpleNamespace(compacted=True))['percent_basis_points'],10000)

    def test_only_manual_compaction_outputs_count(self):
        p=CompactionProgress('not-created',0);p.counts=dict.fromkeys(FAMILIES,100)
        for reason in ('LevelL0FilesNum','Flush',None):
            p.observe(event(job=2,event='compaction_started',compaction_reason=reason))
            p.observe(event(job=2,event='table_file_creation',cf_name='txid',file_number=2,table_properties={'num_entries':100}))
        self.assertEqual(p.outputs['txid'],0)

    def test_invalid_counts_and_log_data_do_not_publish_a_percentage(self):
        good='\n'.join(f'electrs_index_db_properties{{name="rocksdb.estimate-num-keys:{cf}"}} 100' for cf in FAMILIES)
        self.assertEqual(sum(key_counts(good).values()),500)
        for bad in (good.replace(' 100',' NaN',1),good.replace(' 100',' -1',1),good.replace(' 100',' 0.5',1),good+'\n'+good.splitlines()[0],good.splitlines()[0]):
            with self.assertRaises(ValueError):key_counts(bad)
        for bad in ('EVENT_LOG_v1 []','EVENT_LOG_v1 broken',event(job=3,event='table_file_creation',cf_name='spending',file_number=1,table_properties=[])):
            p=CompactionProgress('not-created',0);p.counts=dict.fromkeys(FAMILIES,100)
            p.observe(event(job=3,event='compaction_started',compaction_reason='ManualCompaction'))
            p.observe(bad)
            self.assertIsNone(p.estimate('spending'))

    def test_bounded_incremental_reads_rotation_and_symlink(self):
        with tempfile.TemporaryDirectory(prefix='jv-progress-') as directory:
            path=pathlib.Path(directory)/'LOG';p=CompactionProgress(path,0)
            path.write_bytes(b'no event\n'*(MAX_READ//3))
            self.assertFalse(p.read_log());self.assertEqual(p.offset,MAX_READ)
            while not p.read_log():pass
            position=p.offset;self.assertTrue(p.read_log());self.assertEqual(p.offset,position)
            p.counts=dict.fromkeys(FAMILIES,100)
            path.rename(path.with_suffix('.old'));path.write_text('new log\n')
            p.read_log();self.assertIsNone(p.estimate('spending'))
            path.unlink();path.symlink_to(path.with_suffix('.old'))
            with self.assertRaises(OSError):p.read_log()


if __name__=='__main__':unittest.main()
