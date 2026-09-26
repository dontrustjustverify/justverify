"""Read-only, bounded observation of the pinned indexer's initial DB work.

The fixed denominator is RocksDB's estimated key count across all column
families. Completed output tables advance the numerator; completed families
receive their full weight. This is a record-count estimate, never elapsed time
or five equally weighted stages. It does not participate in wallet readiness.
"""
import collections
import http.client
import json
import math
import os
import pathlib
import re
import stat

FAMILIES = ('config', 'headers', 'txid', 'funding', 'spending')
MAX_READ = 1024 * 1024
MAX_LINE = 65536
MAX_NUMBER = 2**53 - 1


def number(value):
    return type(value) is int and 0 <= value <= MAX_NUMBER


def key_counts(text):
    counts = {}
    pattern = r'electrs_index_db_properties\{name="rocksdb\.estimate-num-keys:(config|headers|txid|funding|spending)"\} ([^\n]+)'
    for family, raw in re.findall(pattern, text):
        value = float(raw)
        if family in counts or not math.isfinite(value) or not value.is_integer() or not 0 <= value <= MAX_NUMBER:
            raise ValueError('Invalid key estimate')
        counts[family] = int(value)
    if set(counts) != set(FAMILIES) or not 0 < sum(counts.values()) <= MAX_NUMBER:
        raise ValueError('Key estimates unavailable')
    return counts


class CompactionProgress:
    def __init__(self, log_path, metrics_port):
        self.path = pathlib.Path(log_path)
        self.port = metrics_port
        self.identity = None
        self.offset = 0
        self.partial = b''
        self.jobs = collections.OrderedDict()
        self.outputs = dict.fromkeys(FAMILIES, 0)
        self.counts = None
        self.points = 0
        self.valid = True
        # Ignore history from a previous process. RocksDB rotates LOG on open.
        try:
            info = self.path.lstat()
            self.identity = (info.st_dev, info.st_ino)
            self.offset = info.st_size
        except OSError:
            pass

    def observe(self, line):
        if 'EVENT_LOG_v1 ' not in line:
            return
        try:
            event = json.loads(line.split('EVENT_LOG_v1 ', 1)[1])
        except (ValueError, TypeError):
            self.valid = False
            return
        if not isinstance(event, dict):
            self.valid = False
            return
        job = event.get('job')
        if not number(job):
            return
        kind = event.get('event')
        if kind == 'compaction_started' and event.get('compaction_reason') == 'ManualCompaction':
            if job in self.jobs:
                self.valid = False
                return
            self.jobs[job] = set()
            if len(self.jobs) > 128:
                self.valid = False
                self.jobs.popitem(last=False)
        elif kind == 'table_file_creation' and job in self.jobs:
            family = event.get('cf_name')
            properties = event.get('table_properties')
            entries = properties.get('num_entries') if isinstance(properties, dict) else None
            file_id = event.get('file_number')
            if family not in FAMILIES or not number(entries) or not number(file_id):
                self.valid = False
                return
            seen = self.jobs[job]
            if file_id in seen:
                return
            if len(seen) >= 32768:
                self.valid = False
                return
            seen.add(file_id)
            self.outputs[family] += entries
        elif kind == 'compaction_finished':
            self.jobs.pop(job, None)

    def read_log(self):
        """Read at most 1 MiB of appended log metadata, never SST/index data."""
        fd = os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode):
                raise ValueError('Not a regular log')
            identity = (info.st_dev, info.st_ino)
            if identity != self.identity or info.st_size < self.offset:
                # A rotation after accounting starts cannot silently reuse a
                # percentage whose observations might have been lost.
                if self.counts is not None:
                    self.valid = False
                self.identity = identity
                self.offset = 0
                self.partial = b''
                self.jobs.clear()
                self.outputs = dict.fromkeys(FAMILIES, 0)
            stream.seek(self.offset)
            chunk = stream.read(MAX_READ)
            self.offset += len(chunk)
        lines = (self.partial + chunk).split(b'\n')
        self.partial = lines.pop()
        if len(self.partial) > MAX_LINE:
            self.valid = False
            self.partial = b''
        for line in lines:
            if len(line) > MAX_LINE:
                self.valid = False
            else:
                self.observe(line.decode('utf-8', 'replace'))
        return self.offset >= info.st_size

    def read_counts(self):
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=.5)
        try:
            connection.request('GET', '/metrics')
            response = connection.getresponse()
            data = response.read(262145)
            if response.status != 200 or len(data) > 262144:
                raise ValueError('Metrics unavailable')
            return key_counts(data.decode('utf-8'))
        finally:
            connection.close()

    def snapshot(self, phase):
        if phase.compacted:
            return {'basis': 'estimated_records', 'percent_basis_points': 10000, 'complete': True}
        if phase.stage != 'compacting' or phase.compaction not in FAMILIES:
            return None
        try:
            caught_up = self.read_log()
            if self.counts is None:
                self.counts = self.read_counts()
            if not self.valid or not caught_up:
                return None
            return self.estimate(phase.compaction)
        except (OSError, ValueError, http.client.HTTPException):
            return None

    def estimate(self, family):
        if not self.valid or self.counts is None or family not in FAMILIES:
            return None
        position = FAMILIES.index(family)
        done = sum(self.counts[c] for c in FAMILIES[:position])
        done += min(self.counts[family], self.outputs[family])
        total = sum(self.counts.values())
        self.points = max(self.points, min(9999, done * 10000 // total))
        return {'basis': 'estimated_records', 'percent_basis_points': self.points,
                'total_records': total, 'completed_records_estimate': done, 'complete': False}
