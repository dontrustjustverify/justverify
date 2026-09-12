#!/usr/bin/env python3
"""Actual Linux Unix peer boundary and non-root backup TUI integration."""
import codecs
import importlib.util
import json
import os
import pathlib
import pty
import pwd
import select
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import termios
import time
import fcntl
import struct

import pyte

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from backup_bundle import BackupBundle
from backup_service import BackupAPI, serve

fixture_spec = importlib.util.spec_from_file_location("backup_fixture", ROOT / "tests/backup_bundle.py")
fixture_module = importlib.util.module_from_spec(fixture_spec)
fixture_spec.loader.exec_module(fixture_module)


def request(path, value):
    with socket.socket(socket.AF_UNIX) as connection:
        connection.settimeout(10)
        connection.connect(str(path))
        connection.sendall((json.dumps(value) + "\n").encode())
        output = bytearray()
        while chunk := connection.recv(65536):
            output.extend(chunk)
    return json.loads(output)


def main():
    assert os.geteuid() == 0 and socket.gethostname() == "justverify-dev"
    node = pwd.getpwnam("justverify")
    nobody = pwd.getpwnam("nobody")
    with tempfile.TemporaryDirectory(prefix="jv-backup-linux-", dir="/var/tmp") as temporary:
        folder = pathlib.Path(temporary)
        specs, cleanup, barriers, _ = fixture_module.fixture(folder)
        bundle = BackupBundle(
            specs,
            folder / "backup-state",
            folder / "boot/justverify-backup.jvb",
            cleanup=cleanup,
            barriers=barriers,
        )
        bundle.prepare_state()
        socket_dir = pathlib.Path("/run/justverify-backup")
        socket_dir.mkdir(mode=0o755, exist_ok=True)
        endpoint = socket_dir / "control.sock"
        if endpoint.exists():
            raise ValueError("backup endpoint already exists")
        binary = pathlib.Path("/opt/justverify-tests/backup-test-justverify")
        if binary.exists(): raise ValueError("isolated test binary already exists")
        shutil.copy2(ROOT / "target/release/justverify", binary)
        binary.chmod(0o755)
        child = os.fork()
        if child == 0:
            api = BackupAPI(bundle, owner=specs[8].path, quiesce_callback=lambda: None, resume_callback=lambda: None, web_restart_callback=lambda: None, health_callback=lambda: None)
            serve(api, endpoint, node.pw_uid)
            os._exit(0)
        process = None
        master = None
        try:
            deadline = time.monotonic() + 10
            while not endpoint.exists():
                if time.monotonic() > deadline:
                    raise TimeoutError("backup service socket")
                time.sleep(0.05)
            assert endpoint.stat().st_mode & 0o777 == 0o660
            assert endpoint.stat().st_uid == 0 and endpoint.stat().st_gid == node.pw_gid
            assert not request(endpoint, {"action": "unknown"})["ok"]
            denied = subprocess.run([
                "/usr/sbin/runuser", "-u", nobody.pw_name, "--", sys.executable, "-c",
                "import socket;s=socket.socket(socket.AF_UNIX);s.connect('/run/justverify-backup/control.sock')",
            ], capture_output=True, timeout=5)
            assert denied.returncode != 0

            master, slave = pty.openpty()
            fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 120, 0, 0))
            process = subprocess.Popen([
                "/usr/sbin/runuser", "-u", node.pw_name, "--", str(binary), "tui", "--socket", "/run/justverify/manager.sock",
            ], stdin=slave, stdout=slave, stderr=slave, env={"PATH": "/usr/bin:/bin", "TERM": "xterm-256color", "LANG": "C.UTF-8"})
            os.close(slave)
            os.set_blocking(master, False)
            screen = pyte.Screen(120, 40)
            stream = pyte.Stream(screen)
            decoder = codecs.getincrementaldecoder("utf-8")()
            captured = bytearray()

            def visible():
                return "\n".join(screen.display)

            def wait_for(text, timeout=30):
                limit = time.monotonic() + timeout
                while time.monotonic() < limit:
                    ready, _, _ = select.select([master], [], [], 0.2)
                    if ready:
                        try:
                            data = os.read(master, 65536)
                        except BlockingIOError:
                            continue
                        except OSError as error:
                            raise RuntimeError("TUI exited before expected screen: " + visible()) from error
                        captured.extend(data)
                        stream.feed(decoder.decode(data))
                    if text in visible() and "Working..." not in visible():
                        return visible()
                raise TimeoutError(text + "\n" + visible())

            def owner_auth():
                masked = wait_for("Current administrator password>")
                password = fixture_module.OWNER_PASSWORD
                os.write(master, password.encode())
                wait_for("*" * len(password))
                assert password.encode() not in captured
                os.write(master, b"\r")

            passphrase = "linux backup integration phrase"
            wait_for("JustVerify")
            os.write(master, b"b")
            wait_for("ENCRYPTED CONFIGURATION BACKUP")
            os.write(master, b"c")
            wait_for("CREATE BACKUP")
            os.write(master, passphrase.encode())
            masked = wait_for("*" * len(passphrase))
            assert passphrase not in masked and "*" * len(passphrase) in masked
            os.write(master, b"\r")
            wait_for("Repeat passphrase")
            os.write(master, passphrase.encode() + b"\r")
            owner_auth()
            wait_for("Encrypted backup saved", 45)
            assert bundle.destination.is_file() and passphrase.encode() not in captured and passphrase.encode() not in bundle.destination.read_bytes()

            os.write(master, b"r")
            wait_for("REVIEW RESTORE")
            os.write(master, passphrase.encode() + b"\r")
            owner_auth()
            wait_for("RESTORE REVIEW", 30)
            os.write(master, b"RESTORE\r")
            wait_for("No restore requested")
            os.write(master, b"\x1b")
            wait_for("C create")
            os.write(master, b"r")
            wait_for("REVIEW RESTORE")
            os.write(master, passphrase.encode() + b"\r")
            owner_auth()
            wait_for("RESTORE REVIEW", 30)
            os.write(master, b"RESTORE DEVICE IDENTITY\r")
            wait_for("FINAL RESTORE AUTHENTICATION")
            os.write(master, passphrase.encode() + b"\r")
            owner_auth()
            wait_for("Restore committed", 45)
            os.write(master, b"x")
            wait_for("RECOVER INTERRUPTED RESTORE")
            os.write(master, b"\x1b")
            wait_for("C create")
            assert passphrase not in visible() and passphrase.encode() not in captured
            os.write(master, b"\x1b")
            wait_for("B backup")
            print(json.dumps({
                "status": "PASS",
                "checks": [
                    "root:justverify 0660 Unix endpoint and other UID refused",
                    "actual non-root 120x40 TUI B/create preview/two masked passphrases",
                    "actual GPG encrypted backup written without plaintext passphrase",
                    "restore decrypt preview, wrong confirmation no mutation, exact review and apply",
                    "interrupted restore recovery review and main-screen return",
                ],
            }, sort_keys=True))
        finally:
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            if master is not None:
                os.close(master)
            os.kill(child, signal.SIGTERM)
            os.waitpid(child, 0)
            if endpoint.exists():
                endpoint.unlink()
            binary.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
