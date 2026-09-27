#!/usr/bin/env python3
"""Fresh real i2pd bootstrap under the packaged service sandbox, on a VM only."""
import hashlib, json, os, pathlib, shutil, socket, subprocess, sys, tempfile, time

assert os.geteuid() == 0
assert subprocess.check_output(['systemd-detect-virt', '--vm'], text=True).strip() == 'qemu'
source = pathlib.Path(__file__).resolve().parents[1]
bundle = pathlib.Path(sys.argv[1])
offline = sys.argv[2:] == ['--offline']
assert not sys.argv[2:] or offline
unit = 'jv-i2p-startup-test'
assert subprocess.run(['systemctl', 'is-active', '--quiet', unit]).returncode != 0
assert not pathlib.Path('/var/lib/' + unit).exists()
root = pathlib.Path(tempfile.mkdtemp(prefix='jv-i2p-startup-', dir='/opt'))
root.chmod(0o755)
report = {'status': 'FAIL', 'scope': 'fresh public I2P bootstrap in isolated ARM VM; no Bitcoin peer or transaction test'}
if offline:
    report['scope'] = 'fresh real router with external networking denied by systemd; orderly stop during reseed'
try:
    shutil.copytree(bundle, root / 'bundle')
    config = (source / 'image/i2pd.conf').read_text().replace('/opt/justverify/i2pd/certificates', str(root / 'bundle/certificates'))
    (root / 'i2pd.conf').write_text(config)
    original = (source / 'image/systemd/justverify-i2p.service').read_text()
    # Keep the complete production service sandbox and startup semantics.
    service = original.split('[Service]\n', 1)[1].split('[Install]', 1)[0]
    service = '\n'.join(line for line in service.splitlines() if not line.startswith('ExecCondition='))
    service = service.replace('justverify-i2p', unit).replace('/opt/justverify/i2pd/i2pd', str(root / 'bundle/i2pd')).replace('/etc/justverify/i2pd.conf', str(root / 'i2pd.conf'))
    if offline:
        service += '\nIPAddressDeny=any\nIPAddressAllow=localhost\n'
    assert 'Type=exec' in service and 'ExecStartPost=' not in service
    unit_file = pathlib.Path('/run/systemd/system/' + unit + '.service')
    unit_file.write_text('[Unit]\nDescription=Isolated router startup test\n[Service]\n' + service + '\n')
    subprocess.run(['systemctl', 'daemon-reload'], check=True)
    start = time.monotonic()
    subprocess.run(['systemctl', 'start', unit], check=True, timeout=15)
    report['service_start_seconds'] = round(time.monotonic() - start, 2)
    def prop(key):
        return subprocess.check_output(['systemctl', 'show', unit, '-p', key, '--value'], text=True).strip()
    pid = prop('MainPID')
    assert int(pid) > 0
    assert int(next(line for line in pathlib.Path('/proc/' + pid + '/status').read_text().splitlines() if line.startswith('Uid:')).split()[1]) != 0
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline:
        assert prop('MainPID') == pid and prop('NRestarts') == '0'
        if offline and time.monotonic()-start >= 12:
            with socket.socket() as stream:
                stream.settimeout(1)
                assert stream.connect_ex(('127.0.0.1',7656)) != 0
            break
        try:
            with socket.create_connection(('127.0.0.1', 7656), timeout=1) as stream:
                stream.sendall(b'HELLO VERSION MIN=3.1 MAX=3.1\n')
                reply = stream.makefile('rb').readline(512)
                if reply.startswith(b'HELLO REPLY ') and b'RESULT=OK' in reply and b'VERSION=3.1' in reply:
                    assert not offline, 'Fresh offline router unexpectedly completed reseed'
                    break
        except OSError:
            pass
        time.sleep(1)
    else:
        raise TimeoutError('Fresh router did not open SAM within bootstrap deadline')
    report.update(status='PASS', same_process=True, restarts=0, nonroot=True, binary_sha256=hashlib.sha256((root/'bundle/i2pd').read_bytes()).hexdigest())
    report['bootstrap_observed_seconds' if offline else 'sam_ready_seconds'] = round(time.monotonic()-start, 2)
finally:
    stopping = time.monotonic()
    subprocess.run(['systemctl', 'stop', unit], check=True, timeout=315)
    assert subprocess.check_output(['systemctl','show',unit,'-p','Result','--value'],text=True).strip()=='success'
    report['orderly_stop'] = True
    report['stop_seconds'] = round(time.monotonic()-stopping, 2)
    subprocess.run(['systemctl', 'clean', '--what=state', unit], check=True)
    (pathlib.Path('/run/systemd/system') / (unit+'.service')).unlink(missing_ok=True)
    subprocess.run(['systemctl', 'daemon-reload'], check=True)
    shutil.rmtree(root)
    print(json.dumps(report), flush=True)
