#!/usr/bin/env python3
"""Narrow root API for reviewed encrypted backup creation and restore."""
import base64
import http.client
import ssl
import hashlib
import json
import os
import pathlib
import pwd
import secrets
import socket
import stat
import struct
import subprocess
import time

from backup_bundle import production_bundle

SOCKET = "/run/justverify-backup/control.sock"
OWNER = pathlib.Path("/var/lib/justverify/web/admin.json")
SERVICES = (
    "justverify-web",
    "justverify-storage",
    "justverify-electrum-tls",
    "justverify-electrs",
    "justverify-core",
    "justverify-manager",
    "justverify-policy",
    "justverify-versions",
    "justverify-tor",
    "justverify-i2p",
)


def system(action, *units, check=True):
    return subprocess.run(
        ["/usr/bin/systemctl", action, *units],
        check=check,
        capture_output=True,
        timeout=180,
    )


def quiesce():
    system("stop", *SERVICES)


def resume():
    system("daemon-reload")
    system("reset-failed", *SERVICES, check=False)
    system("start", "justverify-tor")
    system("start", "justverify-i2p")
    # Conditions and registration guards decide which node services may start.
    for unit in ("justverify-versions", "justverify-core", "justverify-electrs", "justverify-manager", "justverify-policy", "justverify-electrum-tls"):
        system("start", unit)

    system("start", "justverify-storage", "justverify-web")

def health():
    from wait_core_rpc import wait_ready
    wait_ready("/etc/justverify/profile.json",30)
    from node_ready import check
    check()
    system("is-active", "justverify-core", "justverify-electrs", "justverify-tor", "justverify-web", "justverify-electrum-tls")
    config=json.loads(pathlib.Path("/etc/justverify/profile.json").read_bytes())
    def rpc(method,params):
        connection=http.client.HTTPConnection("127.0.0.1",config["rpc_port"],timeout=3)
        try:
            cookie=pathlib.Path(config["cookie"]).read_bytes().strip()
            connection.request("POST","/",json.dumps({"id":1,"method":method,"params":params}),{"Authorization":"Basic "+base64.b64encode(cookie).decode()})
            response=connection.getresponse();value=json.loads(response.read(1024*1024))
            if response.status!=200 or value.get("error"):raise ValueError("restored Core RPC failed")
            return value["result"]
        finally:connection.close()
    context=ssl.create_default_context(cafile="/var/lib/justverify/web/certificate.pem")
    deadline=time.monotonic()+60
    while time.monotonic()<deadline:
        try:
            with socket.create_connection(("127.0.0.1",50002),timeout=3) as transport:
                with context.wrap_socket(transport,server_hostname="justverify.local") as client:
                    client.sendall(b'{"id":1,"method":"blockchain.headers.subscribe","params":[]}\n')
                    data=bytearray()
                    while b"\n" not in data and len(data)<65536:
                        chunk=client.recv(4096)
                        if not chunk:raise ValueError("restored Electrum disconnected")
                        data.extend(chunk)
                    result=json.loads(data.split(b"\n",1)[0])["result"]
                    header=bytes.fromhex(result["hex"]);height=result["height"]
                    if len(header)!=80 or type(height) is not int or height<0:raise ValueError("invalid restored Electrum header")
                    digest=hashlib.sha256(hashlib.sha256(header).digest()).digest()[::-1].hex()
                    if rpc("getblockhash",[height])!=digest:raise ValueError("restored Core and Electrum chain mismatch")
                    # Indexing may legitimately still be underway. Verify the real
                    # indexed block against Core without labeling this full sync.
                    return {"electrs_height":height,"core_height":rpc("getblockchaininfo",[])["blocks"],"indexed_hash":digest}
        except (OSError,ValueError,KeyError,http.client.HTTPException):time.sleep(.5)
    raise TimeoutError("restored Electrum TLS and Core header validation failed")

def schedule_web_restart():
    subprocess.run([
        "/usr/bin/systemd-run", "--quiet", "--collect", "--unit=justverify-backup-web-restart",
        "--on-active=2s", "/usr/bin/systemctl", "restart", "justverify-web",
    ], check=True, capture_output=True, timeout=15)


class BackupAPI:
    def __init__(self, bundle, owner=OWNER, quiesce_callback=quiesce, resume_callback=resume, web_restart_callback=schedule_web_restart, health_callback=health):
        self.bundle_source = bundle
        self.health_callback = health_callback
        self.auth_failures = []
        self.owner = pathlib.Path(owner)
        self.quiesce_callback = quiesce_callback
        self.resume_callback = resume_callback
        self.web_restart_callback = web_restart_callback
        self.reviews = {}

    @property
    def bundle(self):
        return self.bundle_source() if callable(self.bundle_source) else self.bundle_source

    def authenticate(self, password):
        now=time.monotonic();self.auth_failures=[t for t in self.auth_failures if now-t<300]
        if len(self.auth_failures)>=5:raise ValueError("owner authentication rate limited")
        try:
            if not isinstance(password,str) or not 1<=len(password)<=256:raise ValueError("owner password required")
            record=json.loads(self.owner.read_bytes())
            computed=hashlib.scrypt(password.encode(),salt=bytes.fromhex(record["salt"]),n=16384,r=8,p=1).hex()
            if not secrets.compare_digest(computed,record["hash"]):raise ValueError("owner authentication failed")
        except Exception:
            self.auth_failures.append(now);raise ValueError("owner authentication failed")

    def enrolled(self):
        if not self.owner.exists() or self.owner.is_symlink():
            return False
        metadata = self.owner.lstat()
        return stat.S_ISREG(metadata.st_mode) and metadata.st_mode & 0o077 == 0

    def revision(self):
        digest = hashlib.sha256()
        values = self.bundle.snapshot()
        for key in sorted(values):
            digest.update(key.encode() + b"\0")
            digest.update(values[key] if values[key] is not None else b"ABSENT")
        return digest.hexdigest()

    def review(self, kind, binding):
        now = time.monotonic()
        self.reviews = {key: value for key, value in self.reviews.items() if value["expires"] > now}
        if len(self.reviews) >= 8:
            raise ValueError("too many pending backup reviews")
        token = secrets.token_hex(24)
        self.reviews[token] = {"kind": kind, "binding": binding, "expires": now + 120}
        return token

    def consume(self, token, kind):
        if not isinstance(token, str):
            raise ValueError("review token required")
        value = self.reviews.pop(token, None)
        if not value or value["kind"] != kind or value["expires"] < time.monotonic():
            raise ValueError("backup review expired")
        return value["binding"]

    def state(self):
        result = self.bundle.status()
        journal = self.bundle.state / "restore.json"
        result["restore_phase"] = json.loads(journal.read_text()).get("phase") if journal.exists() else "none"
        result["scope"] = "settings, device TLS identity, client authorization records and three Tor identities; blockchain data excluded"
        return result

    def dispatch(self, request):
        if not self.enrolled():
            raise ValueError("owner enrollment required")
        if not isinstance(request, dict) or not isinstance(request.get("action"), str):
            raise ValueError("object action required")
        action = request["action"]
        schemas = {
            "state": {"action"},
            "create_preview": {"action"},
            "create_apply": {"action", "token", "passphrase", "password"},
            "restore_preview": {"action", "passphrase", "password"},
            "restore_apply": {"action", "token", "passphrase", "confirmation", "password"},
            "recover": {"action", "password"},
        }
        if action not in schemas or set(request) != schemas[action] or any(not isinstance(value, str) for key, value in request.items() if key != "action"):
            raise ValueError("unsupported backup request")
        if action in ("create_apply","restore_preview","restore_apply","recover"):
            self.authenticate(request["password"])
        if action == "state":
            return self.state()
        if action == "create_preview":
            revision = self.revision()
            token = self.review("create", revision)
            return {
                "token": token,
                "expires_seconds": 120,
                "destination": str(self.bundle.destination),
                "scope": self.state()["scope"],
                "chain_data_included": False,
                "warning": "Keep the passphrase separately. Losing it makes this backup unusable.",
            }
        if action == "create_apply":
            revision = self.consume(request["token"], "create")
            if not secrets.compare_digest(revision, self.revision()):
                raise ValueError("device configuration changed after review")
            self.quiesce_callback()
            try:
                if not secrets.compare_digest(revision,self.revision()):raise ValueError("configuration changed while stopping services")
                result=self.bundle.create(request["passphrase"])
            finally:
                self.resume_callback()
            self.health_callback()
            return result
        if action == "restore_preview":
            result = self.bundle.inspect(self.bundle.destination, request["passphrase"])
            token = self.review("restore", result["sha256"])
            return {
                "token": token,
                "expires_seconds": 120,
                "sha256": result["sha256"],
                "created_utc": result["manifest"]["created_utc"],
                "files": result["files"],
                "chain_data_included": False,
                "preserved": ["device TLS identity", "P2P onion", "Electrum onion", "RPC onion", "web onion", "account preferences"],
                "confirmation": "RESTORE DEVICE IDENTITY",
                "warning": "Current settings and identities will be replaced. Blockchain data is not restored or downgraded.",
            }
        if action == "restore_apply":
            digest = self.consume(request["token"], "restore")
            if request["confirmation"] != "RESTORE DEVICE IDENTITY":
                raise ValueError("exact restore confirmation required")
            self.quiesce_callback()
            try:
                bundle=self.bundle
                def restored_health():
                    try:
                        self.resume_callback()
                        self.health_callback()
                    except BaseException:
                        self.quiesce_callback()
                        raise
                result = bundle.restore(request["passphrase"], digest, health_check=restored_health)
            finally:
                self.resume_callback()
            return result
        self.quiesce_callback()
        try:
            result = self.bundle.recover()
        finally:
            self.resume_callback()
        if result["phase"] == "rolled_back":
            self.web_restart_callback()
        return result


def serve(api, address, allowed_uid):
    address = pathlib.Path(address)
    if address.exists() or address.is_symlink():
        if address.is_symlink() or not stat.S_ISSOCK(address.lstat().st_mode):
            raise ValueError("backup socket path is occupied")
        with socket.socket(socket.AF_UNIX) as probe:
            try:
                probe.connect(str(address))
            except ConnectionRefusedError:
                address.unlink()
            else:
                raise ValueError("backup service already running")
    with socket.socket(socket.AF_UNIX) as server:
        server.bind(str(address))
        os.chown(address, 0, pwd.getpwuid(allowed_uid).pw_gid)
        os.chmod(address, 0o660)
        server.listen(8)
        while True:
            connection, _ = server.accept()
            with connection:
                try:
                    _, uid, _ = struct.unpack("3i", connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                    if uid not in (0, allowed_uid):
                        raise ValueError("unauthorized peer")
                    connection.settimeout(3)
                    data = bytearray()
                    while b"\n" not in data:
                        chunk = connection.recv(4097 - len(data))
                        if not chunk:
                            raise ValueError("incomplete request")
                        data.extend(chunk)
                        if len(data) > 4096:
                            raise ValueError("request too large")
                    line, extra = data.split(b"\n", 1)
                    if extra:
                        raise ValueError("one request per connection required")
                    result = {"ok": True, "result": api.dispatch(json.loads(line))}
                except (ValueError, UnicodeError, json.JSONDecodeError):
                    result = {"ok": False, "error": "Backup request refused; verify owner access, review, passphrase and saved state."}
                except Exception:
                    result = {"ok": False, "error": "Backup operation failed. Preserve the backup and use recovery before retrying restore."}
                try:
                    connection.sendall(json.dumps(result).encode() + b"\n")
                except OSError:
                    pass


def notify_ready():
    address=os.environ.get("NOTIFY_SOCKET")
    if address:
        if address.startswith("@"):address="\0"+address[1:]
        with socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM) as notification:
            notification.connect(address);notification.sendall(b"READY=1")


if __name__ == "__main__":
    if len(os.sys.argv) != 1 or os.geteuid() != 0:
        raise SystemExit("root backup service takes no arguments")
    state=pathlib.Path("/var/lib/justverify-backup");state.mkdir(mode=0o700,exist_ok=True)
    journal=state/"restore.json"
    if journal.exists() and json.loads(journal.read_text()).get("phase") in ("prepared", "applying", "rolling_back"):
        quiesce()
        production_bundle().recover()
        # Complete durable file recovery before dependent services are released.
        # Mark ready before starting dependencies to avoid a systemd ordering deadlock.
        notify_ready()
        resume()
        health()
    else:
        notify_ready()
    serve(BackupAPI(production_bundle), SOCKET, pwd.getpwnam("justverify").pw_uid)
