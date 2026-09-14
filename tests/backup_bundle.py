#!/usr/bin/env python3
"""Actual GPG backup/restore and crash-recovery test in an isolated directory."""
import hashlib
import json
import os
import pathlib
import secrets
import shutil
import subprocess
import sys
import tempfile

OWNER_PASSWORD = "temporary owner password for isolated tests"
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from backup_bundle import BackupBundle, FileSpec, _atomic, _tor_hostname, _tor_public_from_secret
from backup_service import BackupAPI


def write(path, data, mode):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    path.chmod(mode)


def fixture(folder, device=False):
    uid = os.geteuid()
    gid = os.getegid()
    layout = [
        ("etc/bitcoin.conf", "etc/bitcoin.conf", 0o644, True),
        ("etc/electrs.toml", "etc/electrs.toml", 0o644, True),
        ("etc/profile.json", "etc/profile.json", 0o644, True),
        ("etc/torrc", "etc/torrc", 0o644, True),
        ("etc/versions.json", "etc/versions.json", 0o644, True),
        ("etc/node-ready.json", "etc/node-ready.json", 0o644, True),
        ("config/managed.conf", "state/config/managed.conf", 0o600, True),
        ("versions/active.json", "state/versions/active.json", 0o600, True),
        ("web/admin.json", "state/web/admin.json", 0o600, True),
        ("web/certificate.pem", "state/web/certificate.pem", 0o600, True),
        ("web/private-key.pem", "state/web/private-key.pem", 0o600, True),
        ("web/rpc-clients.json", "state/web/rpc-clients.json", 0o600, False),
        ("web/remote-rpc.json", "state/web/remote-rpc.json", 0o600, False),
    ]
    for service in (("p2p", "electrum", "rpc", "web") if device else ("p2p", "electrum", "rpc")):
        for name in ("hostname", "hs_ed25519_public_key", "hs_ed25519_secret_key"):
            layout.append((f"tor/{service}/{name}", f"tor/{service}/{name}", 0o600, True))
    for service in ("core", "electrs", "manager", "policy"):
        layout.append((f"systemd/{service}-profile.conf", f"systemd/{service}.conf", 0o644, True))
    if device:
        layout.extend([(f"web/{name}", f"state/web/{name}", 0o600, False) for name in ("preferences.json", "remote-web.json")])
    specs = tuple(FileSpec(key, folder / relative, mode, uid, gid, required) for key, relative, mode, required in layout)

    binary = "/opt/justverify/versions/31.1/bitcoin-31.1/bin/bitcoind"
    instance = {"core_version": "31.1", "network": "regtest", "electrs_version": "0.11.1", "watch_only": True}
    profile = {"version": "31.1", "network": "regtest", "binary": binary, "watch_only": True}
    contents = {
        "etc/bitcoin.conf": b"server=1\nchain=regtest\n",
        "etc/electrs.toml": b'network = "regtest"\n',
        "etc/profile.json": (json.dumps(profile) + "\n").encode(),
        "etc/torrc": b"SocksPort 127.0.0.1:9050\n",
        "etc/versions.json": b'{"state":"/var/lib/justverify/versions"}\n',
        "config/managed.conf": b"maxmempool=300\n",
        "versions/active.json": (json.dumps({"instance": instance, "binary": binary, "binary_sha256": "11" * 32}) + "\n").encode(),
        "web/admin.json": (json.dumps({"salt": "22" * 16, "hash": hashlib.scrypt(OWNER_PASSWORD.encode(),salt=bytes.fromhex("22"*16),n=16384,r=8,p=1).hex()}) + "\n").encode(),
        "web/rpc-clients.json": b'{"schema":1,"clients":[]}\n',
        "web/remote-rpc.json": b'{"schema":1,"enabled":true,"phase":"committed"}\n',
    }
    contents["etc/node-ready.json"] = (json.dumps({
        "schema": 1,
        "uuid": "f50a480e-9325-4a5d-93a9-720f262f2fd0",
        "instance": instance,
        "binary_sha256": "11" * 32,
        "configs": {name: hashlib.sha256(contents[f"etc/{name}"]).hexdigest() for name in ("bitcoin.conf", "electrs.toml", "profile.json")},
    }) + "\n").encode()
    for service in ("core", "electrs", "manager", "policy"):
        contents[f"systemd/{service}-profile.conf"] = f"[Service]\n# {service} fixture\n".encode()

    tls = folder / "tls-generation"
    tls.mkdir()
    subprocess.run([
        shutil.which("openssl"), "req", "-x509", "-newkey", "rsa:2048", "-nodes",
        "-subj", "/CN=justverify.local", "-days", "2", "-keyout", str(tls / "key.pem"), "-out", str(tls / "cert.pem"),
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    contents["web/certificate.pem"] = (tls / "cert.pem").read_bytes()
    contents["web/private-key.pem"] = (tls / "key.pem").read_bytes()

    secret_header = b"== ed25519v1-secret: type0 ==\x00\x00\x00"
    public_header = b"== ed25519v1-public: type0 ==\x00\x00\x00"
    for service in (("p2p", "electrum", "rpc", "web") if device else ("p2p", "electrum", "rpc")):
        scalar = bytearray(secrets.token_bytes(32))
        scalar[0] &= 248
        scalar[31] &= 63
        scalar[31] |= 64
        secret = secret_header + bytes(scalar) + secrets.token_bytes(32)
        public = public_header + _tor_public_from_secret(secret)
        contents[f"tor/{service}/hostname"] = (_tor_hostname(public) + "\n").encode()
        contents[f"tor/{service}/hs_ed25519_public_key"] = public
        contents[f"tor/{service}/hs_ed25519_secret_key"] = secret

    if device:
        contents["web/preferences.json"] = b'{"schema":1,"name":"Test","theme":"amber","language":"ja"}'
        contents["web/remote-web.json"] = b'{"schema":1,"enabled":false,"phase":"committed"}'
    for spec in specs:
        if spec.key in contents:
            write(spec.path, contents[spec.key], spec.mode)
        elif spec.required:
            raise AssertionError(spec.key)
    shutil.rmtree(tls)
    cleanup = (folder / "state/web/setup-token", folder / "state/web/pending-owner.json", folder / "state/web/sessions.json")
    barriers = (folder / "state/config/managed.transaction.json", folder / "state/versions/transition.json")
    write(barriers[0], b'{"phase":"committed"}\n', 0o600)
    write(barriers[1], b'{"phase":"committed"}\n', 0o600)
    return specs, cleanup, barriers, contents


def main():
    if not shutil.which("gpg") or not shutil.which("openssl"):
        raise SystemExit("gpg and openssl required")
    with tempfile.TemporaryDirectory(prefix="jv-backup-test-") as temporary:
        root = pathlib.Path(temporary).resolve()
        specs, cleanup, barriers, expected = fixture(root, device=True)
        bundle = BackupBundle(
            specs,
            root / "backup-state",
            root / "boot/justverify-backup.jvb",
            gpg=shutil.which("gpg"),
            openssl=shutil.which("openssl"),
            cleanup=cleanup,
            barriers=barriers,
        )
        passphrase = "correct horse battery staple for backup"
        status = bundle.create(passphrase)
        assert status["exists"] and status["chain_data_included"] is False
        raw = bundle.destination.read_bytes()
        assert b"maxmempool=300" not in raw and b"BEGIN PRIVATE KEY" not in raw and len(raw) < 2 * 1024 * 1024
        review = bundle.inspect(bundle.destination, passphrase)
        assert review["sha256"] == status["sha256"] and review["files"] == len(expected)
        try:
            bundle.inspect(bundle.destination, "wrong passphrase is long enough")
            raise AssertionError("wrong passphrase accepted")
        except ValueError:
            pass
        corrupt = root / "boot/corrupt.jvb"
        damaged = bytearray(raw)
        damaged[-20] ^= 0x80
        corrupt.write_bytes(damaged)
        try:
            bundle.inspect(corrupt, passphrase)
            raise AssertionError("corrupt ciphertext accepted")
        except ValueError:
            pass

        # Digest and decryption must refer to the exact same bounded bytes,
        # even if removable media is replaced after reading the reviewed file.
        decoded = bundle._decode
        def replace_after_read(path, phrase, folder, **kwargs):
            assert kwargs.get("encrypted") == raw
            bundle.destination.write_bytes(b"replacement after reviewed read")
            return decoded(path, phrase, folder, **kwargs)
        bundle._decode = replace_after_read
        assert bundle.inspect(bundle.destination, passphrase)["sha256"] == hashlib.sha256(raw).hexdigest()
        bundle._decode = decoded
        bundle.destination.write_bytes(raw)
        # A linked ancestor must not redirect a root restore outside its target.
        safe = root / "safe"; safe.mkdir()
        alias = root / "alias"; alias.symlink_to(safe, target_is_directory=True)
        try:
            _atomic(alias / "must-not-exist", b"bad", 0o600, os.geteuid(), os.getegid())
            raise AssertionError("symlink ancestor accepted")
        except OSError: pass
        assert not (safe / "must-not-exist").exists()

        original = bundle.snapshot()
        for spec in specs:
            if spec.path.exists():
                write(spec.path, b"changed", spec.mode)
        # Recreate a coherent but different state by restoring once, then alter a single optional file.
        bundle.restore(passphrase, review["sha256"])
        assert bundle.snapshot() == original
        for path in cleanup: write(path, b"must be removed", 0o600)
        write(specs[11].path, b'{"schema":1,"clients":[{"changed":true}]}\n', specs[11].mode)
        restored = bundle.restore(passphrase, review["sha256"])
        assert restored["phase"] == "committed" and restored["chain_data_included"] is False
        assert bundle.snapshot() == original and all(not path.exists() for path in cleanup)

        before = bundle.snapshot(current=True)
        cleanup_before = bundle._read_cleanup()
        rollback = bundle._write_rollback(before, cleanup_before)
        bundle._journal({"schema": 1, "phase": "applying", "backup_sha256": review["sha256"], "rollback": str(rollback)})
        first = specs[0]
        _atomic(first.path, b"partial crash write", first.mode, first.uid, first.gid)
        assert bundle.recover()["phase"] == "rolled_back"
        assert bundle.snapshot() == before

        events = []
        api = BackupAPI(
            bundle,
            owner=specs[8].path,
            quiesce_callback=lambda: events.append("quiesce"),
            resume_callback=lambda: events.append("resume"),
            web_restart_callback=lambda: events.append("web-restart"),
            health_callback=lambda: events.append("health"),
        )
        assert api.dispatch({"action": "state"})["chain_data_included"] is False
        try:
            api.dispatch({"action":"restore_preview","passphrase":passphrase,"password":"wrong"})
            raise AssertionError("wrong owner password accepted")
        except ValueError:pass
        create_plan = api.dispatch({"action": "create_preview"})
        created = api.dispatch({"password": OWNER_PASSWORD, "action": "create_apply", "token": create_plan["token"], "passphrase": passphrase})
        assert created["exists"] and bundle.destination.read_bytes() != raw
        try:
            api.dispatch({"password": OWNER_PASSWORD, "action": "create_apply", "token": create_plan["token"], "passphrase": passphrase})
            raise AssertionError("one-use create review reused")
        except ValueError:
            pass
        current_backup = bundle.destination.read_bytes()
        current_review = bundle.inspect(bundle.destination, passphrase)
        write(specs[11].path, b'{"schema":1,"clients":[{"later":true}]}\n', specs[11].mode)
        restore_plan = api.dispatch({"password": OWNER_PASSWORD, "action": "restore_preview", "passphrase": passphrase})
        try:
            api.dispatch({"password": OWNER_PASSWORD, "action": "restore_apply", "token": restore_plan["token"], "passphrase": passphrase, "confirmation": "RESTORE"})
            raise AssertionError("wrong restore confirmation accepted")
        except ValueError:
            pass
        restore_plan = api.dispatch({"password": OWNER_PASSWORD, "action": "restore_preview", "passphrase": passphrase})
        events.clear()
        applied = api.dispatch({"password": OWNER_PASSWORD, "action": "restore_apply", "token": restore_plan["token"], "passphrase": passphrase, "confirmation": "RESTORE DEVICE IDENTITY"})
        assert applied["phase"] == "committed" and events == ["quiesce", "resume", "health", "resume"]
        assert bundle.snapshot() == before and current_review["sha256"] == hashlib.sha256(current_backup).hexdigest()

        write(barriers[1], b'{"phase":"starting"}\n', 0o600)
        try:
            bundle.create(passphrase)
            raise AssertionError("unfinished version transition accepted")
        except ValueError:
            pass
        assert bundle.destination.read_bytes() == current_backup
        link = specs[0].path
        link.unlink()
        link.symlink_to(specs[1].path)
        write(barriers[1], b'{"phase":"committed"}\n', 0o600)
        try:
            bundle.create(passphrase)
            raise AssertionError("symlink source accepted")
        except ValueError:
            pass
        print(json.dumps({
            "status": "PASS",
            "actual_gpg": subprocess.check_output([shutil.which("gpg"), "--version"], text=True).splitlines()[0],
            "checks": [
                "allowlisted snapshot and no chain data",
                "AES256 salted iterated-S2K encrypted bundle and immediate authenticated decrypt",
                "wrong passphrase and ciphertext corruption rejected",
                "TLS certificate/private-key and four Tor secret/public/hostname sets matched",
                "reviewed hash bound restore and enrollment-token cleanup",
                "durable local rollback recovered a simulated partial restore",
                "owner-gated one-use preview/apply API and exact restore confirmation",
                "unfinished transition and symlink source refused",
            ],
        }, sort_keys=True))


if __name__ == "__main__":
    main()
