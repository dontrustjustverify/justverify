#!/usr/bin/python3 -I
"""Fixed, read-only I2P startup condition and local SAM readiness check."""
import json, os, pathlib, socket, stat, subprocess, sys, time

def enabled():
    profile = pathlib.Path('/etc/justverify/profile.json')
    metadata = profile.lstat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != 0 or metadata.st_mode & 0o022:
        raise ValueError('untrusted node profile')
    policy = pathlib.Path(json.loads(profile.read_bytes())['managed_config'])
    data = pathlib.Path('/srv/justverify/data')
    if policy != pathlib.Path('/var/lib/justverify/config/managed.conf'):
        policy.relative_to(data)
    for ancestor in [policy, *policy.parents]:
        if ancestor.is_symlink():
            raise ValueError('linked policy path')
    fd = os.open(policy, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as file:
        if not stat.S_ISREG(os.fstat(file.fileno()).st_mode):
            raise ValueError('nonregular policy')
        content = file.read(65537)
    if len(content) > 65536:
        raise ValueError('policy too large')
    lines = content.decode().splitlines()
    outgoing = any(line == 'onlynet=i2p' for line in lines)
    incoming = any('i2p' in line.removeprefix('# JustVerify incoming=').split(',')
                   for line in lines if line.startswith('# JustVerify incoming='))
    sam = [line for line in lines if line.startswith('i2psam=')]
    accept = [line for line in lines if line.startswith('i2pacceptincoming=')]
    if incoming or outgoing:
        if sam != ['i2psam=127.0.0.1:7656'] or accept != ['i2pacceptincoming='+str(int(incoming))]:
            raise ValueError('I2P policy mismatch')
    elif sam or accept:
        raise ValueError('unrequested I2P configuration')
    return incoming or outgoing

def ready():
    deadline = time.monotonic()+10
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(('127.0.0.1',7656),timeout=.5) as stream:
                stream.sendall(b'HELLO VERSION MIN=3.1 MAX=3.1\n')
                answer = stream.makefile('rb').readline(512)
                if answer.startswith(b'HELLO REPLY ') and b'RESULT=OK' in answer and b'VERSION=3.1' in answer:
                    return
        except OSError:
            pass
        time.sleep(.2)
    raise RuntimeError('local SAM did not become ready; tunnel reachability is a separate check')

if __name__ == '__main__':
    try:
        if sys.argv[1:] == ['--enabled']:
            sys.exit(0 if enabled() else 1)
        elif sys.argv[1:] == ['--ready']:
            ready()
        elif sys.argv[1:] == ['--sync'] and os.geteuid() == 0:
            run = enabled()
            if run:
                subprocess.run(['/usr/bin/systemctl','reset-failed','justverify-i2p.service'],check=True)
            subprocess.run(['/usr/bin/systemctl','start' if run else 'stop','justverify-i2p.service'],check=True)
        else:
            raise ValueError('unsupported action')
    except Exception as error:
        print('I2P startup check failed: '+type(error).__name__,file=sys.stderr)
        sys.exit(255)
