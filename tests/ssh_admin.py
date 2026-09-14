#!/usr/bin/env python3
"""Exercise first boot, real SSH and sudo in a private Linux mount namespace.

Run as root in the isolated ARM builder. /etc, SSH identity, first-boot marker,
and sudo timestamps are disposable; the builder's accounts remain unchanged.
No production service helper is executed.
"""
import argparse
import fcntl
import hashlib
import json
import os
import pathlib
import pty
import select
import shutil
import socket
import subprocess
import tempfile
import termios
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]


def run(*args, **kwargs):
    return subprocess.run(args, check=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, **kwargs)


def ssh_check(work, port, password, command, admin_password=None, timeout=25):
    master, slave = pty.openpty()
    def controlling_terminal():
        os.setsid()
        fcntl.ioctl(0, termios.TIOCSCTTY, 0)
    proc = subprocess.Popen([
        'ssh', '-tt', '-p', str(port), '-o', 'PubkeyAuthentication=no',
        '-o', 'PreferredAuthentications=password', '-o', 'NumberOfPasswordPrompts=1',
        '-o', 'StrictHostKeyChecking=accept-new', '-o', 'LogLevel=ERROR',
        '-o', 'UserKnownHostsFile=' + str(work/'known_hosts'),
        'justverify@127.0.0.1', command,
    ], stdin=slave, stdout=slave, stderr=slave, preexec_fn=controlling_terminal)
    os.close(slave)
    output = b''
    pending = b''
    login_sent = False
    admin_count = 0
    deadline = time.monotonic() + timeout
    try:
        while proc.poll() is None:
            if time.monotonic() >= deadline:
                raise AssertionError('SSH authentication test timed out')
            if not select.select([master], [], [], .1)[0]:
                continue
            try:
                chunk = os.read(master, 65536)
            except OSError:
                break
            output += chunk
            pending += chunk
            if not login_sent and b'password:' in pending:
                os.write(master, (password+'\n').encode())
                login_sent = True
                pending = b''
            if b'ADMIN-PASSWORD:' in pending:
                assert admin_password is not None, 'unexpected administration prompt'
                os.write(master, (admin_password+'\n').encode())
                admin_count += 1
                pending = b''
        proc.wait(timeout=5)
        # The transcript is private and never emitted, even on an assertion failure.
        return proc.returncode, output, admin_count
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        os.close(master)


def child(work):
    run('mount', '--make-rprivate', '/')
    run('mount', '--bind', str(work/'etc'), '/etc')
    run('mount', '-t', 'tmpfs', 'tmpfs', '/run')
    pathlib.Path('/run/sshd').mkdir(mode=0o755)
    run('mount', '--bind', str(work/'identity'), '/var/lib')
    policy = pathlib.Path('/etc/sudoers.d/00-justverify-admin')
    shutil.copyfile(ROOT/'image/justverify-admin.sudoers', policy)
    policy.chmod(0o440)
    # Use the actual packaged rules, in their actual ordering.
    for name in ('core', 'profile', 'install-core'):
        dst = pathlib.Path('/etc/sudoers.d/justverify-'+name)
        shutil.copyfile(ROOT/f'image/justverify-{name}.sudoers', dst)
        dst.chmod(0o440)
    run('/usr/sbin/visudo', '-c')
    # A clean device starts with a locked account; use an isolated account database.
    run('usermod', '--lock', '--shell', '/usr/sbin/nologin', 'justverify')
    run('sh', str(ROOT/'image/ssh-firstboot.sh'))
    assert pathlib.Path('/var/lib/justverify-ssh/account-initialized').is_file()
    with socket.socket() as reserve:
        reserve.bind(('127.0.0.1', 0))
        port = reserve.getsockname()[1]
    config = work/'sshd.conf'
    config.write_text(f'''Port {port}
ListenAddress 127.0.0.1
HostKey /etc/ssh/ssh_host_ed25519_key
PidFile {work}/sshd.pid
UsePAM no
PrintMotd no
PrintLastLog no
Include {ROOT}/image/ssh/00-justverify.conf
''')
    run('/usr/sbin/sshd', '-t', '-f', str(config))
    server = subprocess.Popen(['/usr/sbin/sshd', '-D', '-e', '-f', str(config)],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=.1):
                    break
            except OSError:
                time.sleep(.1)
        rc, output, _ = ssh_check(work, port, 'justverify', 'id -un')
        assert rc == 0 and b'justverify' in output, 'initial SSH login failed'
        rc, _, _ = ssh_check(work, port, 'justverify', 'sudo -n /usr/bin/whoami')
        assert rc != 0, 'general sudo unexpectedly works without authentication'
        rc, output, count = ssh_check(work, port, 'justverify',
            "sudo -S -p ADMIN-PASSWORD: /usr/bin/whoami && "
            "if sudo -n /usr/bin/whoami; then exit 99; fi", 'justverify')
        assert rc == 0 and b'root' in output and count == 1, 'password sudo or no-cache isolation failed'
        rc, _, _ = ssh_check(work, port, 'justverify',
            'sudo -S -p ADMIN-PASSWORD: /usr/bin/whoami', 'incorrect-test-password')
        assert rc != 0, 'sudo accepted an incorrect password'
        rc, output, _ = ssh_check(work, port, 'justverify', 'sudo -n -l')
        assert rc == 0
        assert b'timestamp_timeout=0' in output and b'timestamp_type=tty' in output
        for name in ('restart-core', 'install-core', 'profile'):
            assert (f'NOPASSWD: /usr/libexec/justverify-{name} ""').encode() in output
            rc, _, _ = ssh_check(work, port, 'justverify',
                f'sudo -n /usr/libexec/justverify-{name} --unexpected')
            assert rc != 0, 'extra helper arguments unexpectedly bypass authentication'
        new_password = 'jv-test-' + os.urandom(18).hex()
        run('chpasswd', input=f'justverify:{new_password}\n'.encode())
        run('sh', str(ROOT/'image/ssh-firstboot.sh'))
        rc, _, _ = ssh_check(work, port, 'justverify', 'true')
        assert rc != 0, 'first boot reset the changed password'
        rc, output, _ = ssh_check(work, port, new_password,
            'sudo -S -p ADMIN-PASSWORD: /usr/bin/whoami', new_password)
        assert rc == 0 and b'root' in output, 'changed SSH password did not authenticate sudo'
        print(json.dumps({'status':'PASS', 'scope':'isolated ARM Linux mount namespace, real loopback SSH and sudo',
            'checks':['packaged sudoers validates in full configuration', 'initial justverify SSH login',
            'general sudo refuses noninteractive unauthenticated command', 'password sudo returns root',
            'wrong sudo password rejected', 'authentication is not cached after a successful command',
            'three narrow NOPASSWD entries preserved; extra arguments require password',
            'second first-boot run preserves changed password; old password rejected'],
            'not_run':['physical Pi administrator installation', 'production service helper invocation']}))
    finally:
        server.terminate()
        server.wait(timeout=5)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--private-child', type=pathlib.Path)
    args = parser.parse_args()
    assert os.geteuid() == 0 and pathlib.Path('/proc/self/ns/mnt').exists(), 'isolated Linux builder root required'
    if args.private_child:
        child(args.private_child)
        return
    protected = [pathlib.Path('/etc')/p for p in ('passwd','shadow','group','gshadow')]
    before = [hashlib.sha256(p.read_bytes()).digest() for p in protected]
    with tempfile.TemporaryDirectory(prefix='jv-ssh-admin-', dir='/var/tmp') as tmp:
        work = pathlib.Path(tmp)
        shutil.copytree('/etc', work/'etc', symlinks=True)
        (work/'identity').mkdir()
        (work/'identity/justverify').mkdir(mode=0o755)
        for key in (work/'etc/ssh').glob('ssh_host_*'):
            key.unlink()
        try:
            result = run('unshare', '--mount', '--pid', '--fork', '--kill-child',
                         'python3', str(pathlib.Path(__file__).resolve()), '--private-child', str(work))
        except subprocess.CalledProcessError as error:
            # Child assertions never include passwords or SSH transcripts.
            raise RuntimeError(error.stderr.decode()[-4000:]) from None
        assert before == [hashlib.sha256(p.read_bytes()).digest() for p in protected], 'builder account database changed'
        report = json.loads(result.stdout)
        report['checks'].append('builder account database unchanged after test')
        print(json.dumps(report))


if __name__ == '__main__':
    main()
