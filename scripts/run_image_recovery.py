#!/usr/bin/env python3
"""Run an already prepared, disposable post-failure image through two boots.

The original cold-boot result is preserved. PARTIAL never becomes PASS merely
because the independent recovery checks succeeded.
"""
import argparse
import hashlib
import json
import pathlib
import re
import subprocess
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser()
p.add_argument('--image', type=pathlib.Path, required=True)
p.add_argument('--root-partuuid', required=True)
p.add_argument('--log', type=pathlib.Path, required=True)
p.add_argument('--report', type=pathlib.Path, required=True)
a = p.parse_args()
assert a.image.resolve().parent == (ROOT / '.state/vm').resolve()
assert not a.image.is_symlink() and a.image.is_file()
assert re.fullmatch(r'[a-f0-9-]{11,36}', a.root_partuuid)
assert not a.log.exists() and not a.report.exists()
command = ['qemu-system-aarch64', '-machine', 'virt', '-accel', 'hvf',
    '-cpu', 'host', '-smp', '2', '-m', '4096',
    '-kernel', str(ROOT / '.state/vm/probe-kernel'),
    '-initrd', str(ROOT / '.state/vm/probe-initrd'),
    '-append', f'root=PARTUUID={a.root_partuuid} rw console=ttyAMA0',
    '-drive', f'file={a.image},if=virtio,format=raw',
    '-netdev', 'user,id=net0', '-device', 'virtio-net-pci,netdev=net0', '-nographic']
started = time.monotonic()
timed_out = False
with a.log.open('xb') as log:
    process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
    try:
        code = process.wait(timeout=1000)
    except subprocess.TimeoutExpired:
        timed_out = True
        process.terminate()
        try:
            code = process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            process.kill()
            code = process.wait()
records = []
for line in a.log.read_text(errors='replace').splitlines():
    match = re.search(r'JV_IMAGE_RECOVERY (\{.*\})$', line)
    if match:
        records.append(json.loads(match.group(1)))
complete = (code == 0 and not timed_out and len(records) == 2
    and records[1].get('checks', {}).get('actual_reboot_same_identity_tip_wallet_uuid'))
status = ('PASS' if all(x['status'] == 'PASS' for x in records) else 'PARTIAL') if complete else 'FAIL'
result = {'status': status, 'environment': 'QEMU virt, external Debian kernel; NOT Pi firmware or hardware',
    'scope': 'Separate recovery after a preserved cold-boot failure', 'boots': records,
    'exit_code': code, 'timed_out': timed_out, 'elapsed_seconds': time.monotonic() - started,
    'observer_sha256': hashlib.sha256((ROOT / 'tests/image_recovery_probe.py').read_bytes()).hexdigest(),
    'console_log': str(a.log)}
a.report.write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({'status': status, 'boots': len(records), 'report': str(a.report)}))
if status != 'PASS':
    raise SystemExit(1)
