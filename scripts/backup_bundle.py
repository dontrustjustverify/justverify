#!/usr/bin/env python3
"""Encrypted, allowlisted device-configuration backup with crash-safe restore."""
from __future__ import annotations

import base64
import contextlib
import dataclasses
import datetime
import fcntl
import hashlib
import io
import json
import os
import pathlib
import pwd
import grp
import secrets
import shutil
import ssl
import stat
import subprocess
import tarfile
import tempfile

MAGIC = b"JUSTVERIFY-BACKUP-V1\n"
MAX_FILE = 2 * 1024 * 1024
MAX_BUNDLE = 32 * 1024 * 1024


@dataclasses.dataclass(frozen=True)
class FileSpec:
    key: str
    path: pathlib.Path
    mode: int
    uid: int
    gid: int
    required: bool = True


def production_specs(policy_path: pathlib.Path) -> tuple[FileSpec, ...]:
    root = pwd.getpwnam("root")
    node = pwd.getpwnam("justverify")
    tor = pwd.getpwnam("debian-tor")

    def item(key, path, mode, owner, required=True):
        return FileSpec(key, pathlib.Path(path), mode, owner.pw_uid, owner.pw_gid, required)

    values = [
        item("etc/bitcoin.conf", "/etc/justverify/bitcoin.conf", 0o644, root),
        item("etc/electrs.toml", "/etc/justverify/electrs.toml", 0o644, root),
        item("etc/profile.json", "/etc/justverify/profile.json", 0o644, root),
        item("etc/torrc", "/etc/justverify/torrc", 0o644, root),
        item("etc/versions.json", "/etc/justverify/versions.json", 0o644, root),
        item("etc/node-ready.json", "/etc/justverify/node-ready.json", 0o644, root),
        item("config/managed.conf", policy_path, 0o600, node),
        item("versions/active.json", "/var/lib/justverify/versions/active.json", 0o600, node),
        item("web/admin.json", "/var/lib/justverify/web/admin.json", 0o600, node),
        item("web/certificate.pem", "/var/lib/justverify/web/certificate.pem", 0o600, node),
        item("web/private-key.pem", "/var/lib/justverify/web/private-key.pem", 0o600, node),
        item("web/rpc-clients.json", "/var/lib/justverify/web/rpc-clients.json", 0o600, node, False),
        item("web/preferences.json", "/var/lib/justverify/web/preferences.json", 0o600, node, False),
        item("web/remote-web.json", "/var/lib/justverify/web/remote-web.json", 0o600, node, False),
        item("web/remote-rpc.json", "/var/lib/justverify/web/remote-rpc.json", 0o600, node, False),
    ]
    for service in ("p2p", "electrum", "rpc", "web"):
        for name in ("hostname", "hs_ed25519_public_key", "hs_ed25519_secret_key"):
            values.append(item(f"tor/{service}/{name}", f"/var/lib/justverify-tor/{service}/{name}", 0o600, tor, service != "web"))
    for service in ("core", "electrs", "manager", "policy"):
        values.append(item(
            f"systemd/{service}-profile.conf",
            f"/etc/systemd/system/justverify-{service}.service.d/20-profile.conf",
            0o644,
            root,
        ))
    return tuple(values)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json(data: bytes):
    value = json.loads(data)
    if not isinstance(value, dict):
        raise ValueError("expected JSON object")
    return value


@contextlib.contextmanager
def _parent_fd(path):
    # Walk without following any attacker-controlled ancestor symlinks. A held
    # directory descriptor also binds rename/unlink to the directory we opened.
    path = pathlib.Path(path)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("absolute canonical restore path required")
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for component in path.parts[1:-1]:
            next_fd = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        yield fd
    finally:
        os.close(fd)


def _atomic(path: pathlib.Path, data: bytes, mode: int, uid: int, gid: int) -> None:
    with _parent_fd(path) as directory:
        temporary = ".jv-restore-" + secrets.token_hex(16)
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
        try:
            with os.fdopen(fd, "wb") as file:
                file.write(data)
                file.flush()
                os.fchmod(file.fileno(), mode)
                os.fchown(file.fileno(), uid, gid)
                os.fsync(file.fileno())
            try:
                existing = os.stat(path.name, dir_fd=directory, follow_symlinks=False)
            except FileNotFoundError:
                existing = None
            if existing is not None and not stat.S_ISREG(existing.st_mode):
                raise ValueError("restore target is not a regular file")
            os.replace(temporary, path.name, src_dir_fd=directory, dst_dir_fd=directory)
            os.fsync(directory)
        finally:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(temporary, dir_fd=directory)


def _remove_regular(path: pathlib.Path) -> None:
    with _parent_fd(path) as directory:
        try:
            metadata = os.stat(path.name, dir_fd=directory, follow_symlinks=False)
        except FileNotFoundError:
            return
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError("refusing to remove non-regular restore target")
        os.unlink(path.name, dir_fd=directory)
        os.fsync(directory)


def _tor_hostname(public: bytes) -> str:
    header = b"== ed25519v1-public: type0 ==\x00\x00\x00"
    if len(public) != 64 or public[:32] != header:
        raise ValueError("invalid Tor public identity")
    key = public[32:]
    version = b"\x03"
    checksum = hashlib.sha3_256(b".onion checksum" + key + version).digest()[:2]
    return base64.b32encode(key + checksum + version).decode("ascii").lower() + ".onion"


def _tor_public_from_secret(secret: bytes) -> bytes:
    header = b"== ed25519v1-secret: type0 ==\x00\x00\x00"
    if len(secret) != 96 or secret[:32] != header:
        raise ValueError("invalid Tor secret identity")
    scalar = int.from_bytes(secret[32:64], "little")
    prime = 2**255 - 19
    d = -121665 * pow(121666, prime - 2, prime) % prime
    base_y = 4 * pow(5, prime - 2, prime) % prime
    base_x = pow((base_y * base_y - 1) * pow(d * base_y * base_y + 1, prime - 2, prime) % prime, (prime + 3) // 8, prime)
    if (base_x * base_x - (base_y * base_y - 1) * pow(d * base_y * base_y + 1, prime - 2, prime)) % prime:
        base_x = base_x * pow(2, (prime - 1) // 4, prime) % prime
    if base_x & 1:
        base_x = prime - base_x

    def add(left, right):
        x1, y1 = left
        x2, y2 = right
        product = d * x1 * x2 * y1 * y2 % prime
        x3 = (x1 * y2 + x2 * y1) * pow(1 + product, prime - 2, prime) % prime
        y3 = (y1 * y2 + x1 * x2) * pow(1 - product, prime - 2, prime) % prime
        return x3, y3

    point = (0, 1)
    addend = (base_x, base_y)
    while scalar:
        if scalar & 1:
            point = add(point, addend)
        addend = add(addend, addend)
        scalar >>= 1
    x, y = point
    encoded = bytearray(y.to_bytes(32, "little"))
    encoded[31] |= (x & 1) << 7
    return bytes(encoded)


class BackupBundle:
    def __init__(
        self,
        specs: tuple[FileSpec, ...],
        state: pathlib.Path,
        destination: pathlib.Path,
        *,
        gpg: str = "/usr/bin/gpg",
        openssl: str = "/usr/bin/openssl",
        cleanup: tuple[pathlib.Path, ...] = (),
        barriers: tuple[pathlib.Path, ...] = (),
        validate_context=None,
        context: dict | None = None,
    ):
        self.validate_context = validate_context
        self.context = context
        self.specs = specs
        self.by_key = {item.key: item for item in specs}
        if len(self.by_key) != len(specs) or any(".." in pathlib.PurePosixPath(item.key).parts for item in specs):
            raise ValueError("invalid backup catalog")
        self.state = pathlib.Path(state)
        self.destination = pathlib.Path(destination)
        self.gpg = gpg
        self.openssl = openssl
        self.cleanup = tuple(pathlib.Path(path) for path in cleanup)
        self.barriers = tuple(pathlib.Path(path) for path in barriers)

    def prepare_state(self) -> None:
        self.state.mkdir(parents=True, exist_ok=True, mode=0o700)
        metadata = self.state.lstat()
        if not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode) or metadata.st_mode & 0o077:
            raise ValueError("backup state must be a private real directory")

    def lock(self):
        self.prepare_state()
        file = (self.state / "operation.lock").open("a")
        os.chmod(file.name, 0o600)
        fcntl.flock(file, fcntl.LOCK_EX)
        return file

    @staticmethod
    def validate_passphrase(passphrase: str) -> bytes:
        if not isinstance(passphrase, str) or not 16 <= len(passphrase) <= 256 or "\n" in passphrase or "\r" in passphrase or not passphrase.strip():
            raise ValueError("backup passphrase must contain 16 to 256 non-newline characters")
        return (passphrase + "\n").encode("utf-8")

    def _read_file(self, spec: FileSpec, required: bool | None = None) -> bytes | None:
        must_exist = spec.required if required is None else required
        if not spec.path.exists() and not spec.path.is_symlink():
            if must_exist:
                raise ValueError("required backup source is missing")
            return None
        metadata = spec.path.lstat()
        if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
            raise ValueError("backup source is not a regular file")
        if stat.S_IMODE(metadata.st_mode) != spec.mode or metadata.st_uid != spec.uid or metadata.st_gid != spec.gid or metadata.st_size > MAX_FILE:
            raise ValueError("backup source ownership, mode or size is invalid")
        descriptor = os.open(spec.path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            opened = os.fstat(descriptor)
            if (opened.st_dev, opened.st_ino) != (metadata.st_dev, metadata.st_ino):
                raise ValueError("backup source changed while opening")
            chunks = bytearray()
            while len(chunks) <= MAX_FILE:
                part = os.read(descriptor, min(65536, MAX_FILE + 1 - len(chunks)))
                if not part:
                    break
                chunks.extend(part)
            if len(chunks) > MAX_FILE:
                raise ValueError("backup source is too large")
            final = os.fstat(descriptor)
            if (final.st_size, final.st_mtime_ns, final.st_ctime_ns) != (opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns):
                raise ValueError("backup source changed during snapshot")
            return bytes(chunks)
        finally:
            os.close(descriptor)

    def _check_barriers(self) -> None:
        terminal = {"committed", "rolled_back"}
        for path in self.barriers:
            if not path.exists():
                continue
            value = _json(path.read_bytes())
            if value.get("phase") not in terminal:
                raise ValueError("finish interrupted configuration changes before backup")

    def snapshot(self, *, current: bool = False) -> dict[str, bytes | None]:
        self._check_barriers()
        values = {item.key: self._read_file(item, False if current else None) for item in self.specs}
        if not current:
            self._validate_snapshot(values)
        return values

    def _validate_snapshot(self, values: dict[str, bytes | None]) -> None:
        if set(values) != set(self.by_key):
            raise ValueError("backup catalog mismatch")
        required = {item.key for item in self.specs if item.required}
        if any(values[key] is None for key in required):
            raise ValueError("required backup content missing")
        profile = _json(values["etc/profile.json"])
        ready = _json(values["etc/node-ready.json"])
        active = _json(values["versions/active.json"])
        if ready.get("schema") != 1 or active.get("instance") != ready.get("instance"):
            raise ValueError("registered profile and active selection differ")
        instance = ready["instance"]
        if profile.get("version") != instance.get("core_version") or profile.get("network") != instance.get("network") or profile.get("watch_only", False) != instance.get("watch_only", False):
            raise ValueError("profile does not match registered instance")
        if active.get("binary") != profile.get("binary") or active.get("binary_sha256") != ready.get("binary_sha256"):
            raise ValueError("active binary does not match registration")
        hashes = ready.get("configs")
        if not isinstance(hashes, dict) or any(hashes.get(name) != _sha(values[f"etc/{name}"]) for name in ("bitcoin.conf", "electrs.toml", "profile.json")):
            raise ValueError("registered configuration hash mismatch")
        admin = _json(values["web/admin.json"])
        if set(admin) != {"salt", "hash"} or not all(isinstance(admin[key], str) and len(admin[key]) >= 32 for key in admin):
            raise ValueError("invalid owner authentication record")
        preferences = values.get("web/preferences.json")
        if preferences is not None:
            # Backup service uses system Python without aiohttp: validate data here.
            value = _json(preferences)
            import unicodedata
            if set(value) != {"schema", "name", "theme", "language"} or value["schema"] != 1 or value["theme"] not in ("teal", "amber", "green", "ice") or value["language"] not in ("ko", "en", "ja") or not isinstance(value["name"], str) or not 1 <= len(value["name"]) <= 40 or value["name"] != value["name"].strip() or any(unicodedata.category(c).startswith("C") for c in value["name"]):
                raise ValueError("invalid owner preferences")
        remote_web = values.get("web/remote-web.json")
        if remote_web is not None:
            value = _json(remote_web)
            if set(value) != {"schema", "enabled", "phase"} or value["schema"] != 1 or type(value["enabled"]) is not bool or value["phase"] != "committed":
                raise ValueError("remote web setting requires recovery")
            if value["enabled"] and (not values.get("tor/web/hostname") or b"HiddenServiceDir /var/lib/justverify-tor/web\n" not in values["etc/torrc"]):
                raise ValueError("enabled web onion identity missing")
        remote = values["web/remote-rpc.json"]
        if remote is not None:
            value = _json(remote)
            if value.get("schema") != 1 or type(value.get("enabled")) is not bool or value.get("phase") != "committed":
                raise ValueError("remote RPC setting requires recovery before backup")
        if self.validate_context is not None:
            self.validate_context(values)
        self._validate_tls(values["web/certificate.pem"], values["web/private-key.pem"])
        for service in ("p2p", "electrum", "rpc", "web"):
            if service == "web":
                keys = [values.get(f"tor/web/{name}") for name in ("hostname", "hs_ed25519_public_key", "hs_ed25519_secret_key")]
                if all(v is None for v in keys): continue
                if any(v is None for v in keys): raise ValueError("incomplete web onion identity")
            hostname = values[f"tor/{service}/hostname"].decode("ascii").strip()
            public = values[f"tor/{service}/hs_ed25519_public_key"]
            secret = values[f"tor/{service}/hs_ed25519_secret_key"]
            if hostname != _tor_hostname(public) or _tor_public_from_secret(secret) != public[32:]:
                raise ValueError("Tor identity files do not match")

    def _validate_tls(self, certificate: bytes, private_key: bytes) -> None:
        with tempfile.TemporaryDirectory(prefix="tls-check-", dir=self.state) as folder:
            folder = pathlib.Path(folder)
            cert = folder / "certificate.pem"
            key = folder / "private-key.pem"
            cert.write_bytes(certificate)
            key.write_bytes(private_key)
            cert.chmod(0o600)
            key.chmod(0o600)
            certificate_public = subprocess.run(
                [self.openssl, "x509", "-in", str(cert), "-pubkey", "-noout"],
                check=True,
                capture_output=True,
                timeout=10,
            ).stdout
            key_public = subprocess.run(
                [self.openssl, "pkey", "-in", str(key), "-pubout"],
                check=True,
                capture_output=True,
                timeout=10,
            ).stdout
            if not secrets.compare_digest(certificate_public, key_public):
                raise ValueError("TLS certificate and key do not match")
            ssl.PEM_cert_to_DER_cert(certificate.decode("ascii"))

    def _manifest(self, values: dict[str, bytes | None]) -> dict:
        entries = []
        for spec in self.specs:
            data = values[spec.key]
            entries.append({
                "key": spec.key,
                "present": data is not None,
                "sha256": _sha(data) if data is not None else None,
                "bytes": len(data) if data is not None else 0,
                "mode": f"{spec.mode:04o}",
            })
        return {
            "schema": 1,
            "created_utc": datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat(),
            "entries": entries,
            "chain_data_included": False,
            "preserves_device_tls_identity": True,
            "preserves_tor_identities": ["p2p", "electrum", "rpc"],
        }

    def _write_tar(self, path: pathlib.Path, values: dict[str, bytes | None]) -> dict:
        manifest = self._manifest(values)
        with tarfile.open(path, "w", format=tarfile.USTAR_FORMAT) as archive:
            items = [("manifest.json", json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode())]
            items.extend((f"files/{key}", data) for key, data in values.items() if data is not None)
            for name, data in items:
                info = tarfile.TarInfo(name)
                info.size = len(data)
                info.mode = 0o600
                info.uid = 0
                info.gid = 0
                info.mtime = 0
                archive.addfile(info, io.BytesIO(data))
        os.chmod(path, 0o600)
        return manifest

    def _gpg(self, arguments: list[str], passphrase: str) -> subprocess.CompletedProcess:
        home = self.state / "gpg"
        home.mkdir(mode=0o700, exist_ok=True)
        os.chmod(home, 0o700)
        return subprocess.run(
            [self.gpg, "--no-options", "--homedir", str(home), "--batch", "--yes", "--pinentry-mode", "loopback", "--passphrase-fd", "0", "--status-fd", "2", *arguments],
            input=self.validate_passphrase(passphrase),
            capture_output=True,
            timeout=60,
        )

    def create(self, passphrase: str) -> dict:
        with self.lock():
            values = self.snapshot()
            self.destination.parent.mkdir(parents=True, exist_ok=True)
            if self.destination.exists() or self.destination.is_symlink():
                metadata = self.destination.lstat()
                if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
                    raise ValueError("backup destination is not a regular file")
            with tempfile.TemporaryDirectory(prefix="create-", dir=self.state) as folder:
                folder = pathlib.Path(folder)
                plain = folder / "payload.tar"
                cipher = folder / "payload.gpg"
                manifest = self._write_tar(plain, values)
                result = self._gpg([
                    "--symmetric", "--cipher-algo", "AES256", "--s2k-cipher-algo", "AES256",
                    "--s2k-digest-algo", "SHA512", "--s2k-mode", "3", "--s2k-count", "65011712",
                    "--force-mdc", "--compress-algo", "none", "--output", str(cipher), str(plain),
                ], passphrase)
                if result.returncode != 0 or not cipher.is_file():
                    raise ValueError("backup encryption failed")
                descriptor, temporary = tempfile.mkstemp(prefix=".jv-backup-", dir=self.destination.parent)
                try:
                    with os.fdopen(descriptor, "wb") as output:
                        output.write(MAGIC)
                        with cipher.open("rb") as source:
                            shutil.copyfileobj(source, output, 1024 * 1024)
                        output.flush()
                        os.fchmod(output.fileno(), 0o600)
                        os.fsync(output.fileno())
                    verified = self.inspect(pathlib.Path(temporary), passphrase)
                    if verified["manifest"] != manifest:
                        raise ValueError("encrypted backup verification mismatch")
                    os.replace(temporary, self.destination)
                    directory = os.open(self.destination.parent, os.O_RDONLY | os.O_DIRECTORY)
                    try:
                        os.fsync(directory)
                    finally:
                        os.close(directory)
                finally:
                    with contextlib.suppress(FileNotFoundError):
                        os.unlink(temporary)
            return self.status(manifest)

    def _encrypted_bytes(self, path):
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as source:
            before = os.fstat(source.fileno())
            if not stat.S_ISREG(before.st_mode) or not len(MAGIC) < before.st_size <= MAX_BUNDLE:
                raise ValueError("invalid encrypted backup file")
            data = source.read(MAX_BUNDLE + 1)
            after = os.fstat(source.fileno())
            if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns) or len(data) != before.st_size:
                raise ValueError("backup changed while reading")
        if not data.startswith(MAGIC):
            raise ValueError("unknown backup format")
        return data

    def _decode(self, path: pathlib.Path, passphrase: str, folder: pathlib.Path, *, encrypted=None) -> tuple[dict, dict[str, bytes | None]]:
        data = self._encrypted_bytes(path) if encrypted is None else encrypted
        cipher = folder / "payload.gpg"
        plain = folder / "payload.tar"
        cipher.write_bytes(data[len(MAGIC):])
        cipher.chmod(0o600)
        result = self._gpg(["--max-output", str(MAX_BUNDLE), "--decrypt", "--output", str(plain), str(cipher)], passphrase)
        if result.returncode != 0 or b"[GNUPG:] DECRYPTION_OKAY" not in result.stderr or not plain.is_file() or plain.stat().st_size > MAX_BUNDLE:
            raise ValueError("backup authentication failed")
        with tarfile.open(plain, "r:") as archive:
            members = archive.getmembers()
            names = [member.name for member in members]
            if len(names) != len(set(names)) or "manifest.json" not in names:
                raise ValueError("invalid backup archive members")
            for member in members:
                if not member.isfile() or member.size > MAX_FILE or member.name.startswith("/") or ".." in pathlib.PurePosixPath(member.name).parts:
                    raise ValueError("unsafe backup archive member")
            manifest_member = archive.getmember("manifest.json")
            manifest = _json(archive.extractfile(manifest_member).read(MAX_FILE + 1))
            if manifest.get("schema") != 1 or manifest.get("chain_data_included") is not False:
                raise ValueError("unsupported backup schema")
            entries = manifest.get("entries")
            if not isinstance(entries, list) or len(entries) > len(self.specs):
                raise ValueError("backup catalog is incomplete")
            records = {entry.get("key"): entry for entry in entries if isinstance(entry, dict)}
            # Only the newly introduced optional device settings may be absent
            # from legacy v1 manifests; reject every other catalog mismatch.
            added = {"web/preferences.json", "web/remote-web.json", "tor/web/hostname", "tor/web/hs_ed25519_public_key", "tor/web/hs_ed25519_secret_key"}
            missing = set(self.by_key) - set(records)
            if len(records) != len(entries) or set(records) - set(self.by_key) or missing - added:
                raise ValueError("backup catalog differs from installed version")
            values = {}
            expected_names = {"manifest.json"}
            for spec in self.specs:
                if spec.key in missing:
                    if spec.required: raise ValueError("required legacy entry missing")
                    values[spec.key] = None
                    continue
                record = records[spec.key]
                if set(record) != {"key", "present", "sha256", "bytes", "mode"} or record["mode"] != f"{spec.mode:04o}" or type(record["present"]) is not bool:
                    raise ValueError("invalid backup entry metadata")
                if not record["present"]:
                    if record["sha256"] is not None or record["bytes"] != 0 or spec.required:
                        raise ValueError("required or absent backup entry mismatch")
                    values[spec.key] = None
                    continue
                name = f"files/{spec.key}"
                expected_names.add(name)
                try:
                    member = archive.getmember(name)
                except KeyError as error:
                    raise ValueError("backup content is missing") from error
                data = archive.extractfile(member).read(MAX_FILE + 1)
                if len(data) > MAX_FILE or len(data) != record["bytes"] or _sha(data) != record["sha256"]:
                    raise ValueError("backup content hash mismatch")
                values[spec.key] = data
            if set(names) != expected_names:
                raise ValueError("unexpected backup archive content")
        self._validate_snapshot(values)
        return manifest, values

    def inspect(self, path: pathlib.Path | None, passphrase: str) -> dict:
        self.prepare_state()
        path = pathlib.Path(path or self.destination)
        encrypted = self._encrypted_bytes(path)
        digest = _sha(encrypted)
        with tempfile.TemporaryDirectory(prefix="inspect-", dir=self.state) as folder:
            manifest, _ = self._decode(path, passphrase, pathlib.Path(folder), encrypted=encrypted)
        return {
            "sha256": digest,
            "bytes": len(encrypted),
            "manifest": manifest,
            "files": sum(1 for entry in manifest["entries"] if entry["present"]),
            "chain_data_included": False,
            "preserves_device_tls_identity": True,
            "preserves_tor_identities": ["p2p", "electrum", "rpc"],
        }

    def status(self, manifest: dict | None = None) -> dict:
        exists = self.destination.exists() and not self.destination.is_symlink() and self.destination.is_file()
        result = {
            "destination": str(self.destination),
            "exists": exists,
            "chain_data_included": False,
        }
        if exists:
            result.update(bytes=self.destination.stat().st_size, sha256=_sha(self.destination.read_bytes()))
        if manifest:
            result.update(created_utc=manifest["created_utc"], files=sum(1 for entry in manifest["entries"] if entry["present"]))
        return result

    def _write_rollback(self, values: dict[str, bytes | None], cleanup: dict[str, bytes | None]) -> pathlib.Path:
        folder = pathlib.Path(tempfile.mkdtemp(prefix="rollback-", dir=self.state))
        folder.chmod(0o700)
        metadata = {"schema": 1, "entries": [], "cleanup": []}
        for index, spec in enumerate(self.specs):
            data = values[spec.key]
            record = {"key": spec.key, "present": data is not None, "sha256": _sha(data) if data is not None else None}
            metadata["entries"].append(record)
            if data is not None:
                path = folder / f"file-{index}"
                _atomic(path, data, 0o600, os.geteuid(), os.getegid())
        for index, path in enumerate(self.cleanup):
            data = cleanup[str(path)]
            record = {"path": str(path), "present": data is not None, "sha256": _sha(data) if data is not None else None}
            metadata["cleanup"].append(record)
            if data is not None:
                target = folder / f"cleanup-{index}"
                _atomic(target, data, 0o600, os.geteuid(), os.getegid())
        _atomic(folder / "manifest.json", json.dumps(metadata, sort_keys=True).encode(), 0o600, os.geteuid(), os.getegid())
        return folder

    def _read_cleanup(self) -> dict[str, bytes | None]:
        values = {}
        for path in self.cleanup:
            if not path.exists() and not path.is_symlink():
                values[str(path)] = None
                continue
            metadata = path.lstat()
            if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode) or metadata.st_size > MAX_FILE:
                raise ValueError("unsafe enrollment cleanup file")
            values[str(path)] = path.read_bytes()
        return values

    def _journal(self, value: dict) -> None:
        _atomic(self.state / "restore.json", (json.dumps(value, sort_keys=True) + "\n").encode(), 0o600, os.geteuid(), os.getegid())

    def _apply_values(self, values: dict[str, bytes | None]) -> None:
        for spec in self.specs:
            data = values[spec.key]
            if data is None:
                _remove_regular(spec.path)
            else:
                _atomic(spec.path, data, spec.mode, spec.uid, spec.gid)

    def _load_rollback(self, folder: pathlib.Path) -> tuple[dict[str, bytes | None], dict[str, bytes | None]]:
        root = self.state.resolve()
        if folder.parent.resolve() != root or not folder.name.startswith("rollback-") or folder.is_symlink():
            raise ValueError("invalid rollback path")
        metadata = _json((folder / "manifest.json").read_bytes())
        if metadata.get("schema") != 1 or len(metadata.get("entries", [])) != len(self.specs) or len(metadata.get("cleanup", [])) != len(self.cleanup):
            raise ValueError("invalid rollback manifest")
        values = {}
        for index, spec in enumerate(self.specs):
            record = metadata["entries"][index]
            if record.get("key") != spec.key or type(record.get("present")) is not bool:
                raise ValueError("rollback catalog mismatch")
            if record["present"]:
                data = (folder / f"file-{index}").read_bytes()
                if _sha(data) != record.get("sha256"):
                    raise ValueError("rollback hash mismatch")
                values[spec.key] = data
            else:
                values[spec.key] = None
        cleanup = {}
        for index, path in enumerate(self.cleanup):
            record = metadata["cleanup"][index]
            if record.get("path") != str(path) or type(record.get("present")) is not bool:
                raise ValueError("rollback cleanup mismatch")
            if record["present"]:
                data = (folder / f"cleanup-{index}").read_bytes()
                if _sha(data) != record.get("sha256"):
                    raise ValueError("rollback cleanup hash mismatch")
                cleanup[str(path)] = data
            else:
                cleanup[str(path)] = None
        return values, cleanup

    def _apply_cleanup(self, values: dict[str, bytes | None], *, restoring: bool) -> None:
        for path in self.cleanup:
            data = values[str(path)]
            if data is None or restoring:
                _remove_regular(path)
            else:
                metadata = path.parent.stat()
                _atomic(path, data, 0o600, metadata.st_uid, metadata.st_gid)

    def _finish_rollback(self, folder: pathlib.Path) -> None:
        shutil.rmtree(folder)
        directory = os.open(self.state, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)

    def restore(self, passphrase: str, expected_sha256: str, health_check=None) -> dict:
        if not isinstance(expected_sha256, str) or len(expected_sha256) != 64:
            raise ValueError("reviewed backup hash required")
        with self.lock():
            encrypted = self._encrypted_bytes(self.destination)
            digest = _sha(encrypted)
            if not secrets.compare_digest(digest, expected_sha256):
                raise ValueError("backup changed after review")
            journal_path = self.state / "restore.json"
            if journal_path.exists() and _json(journal_path.read_bytes()).get("phase") in ("prepared", "applying", "rolling_back"):
                raise ValueError("interrupted restore requires recovery")
            with tempfile.TemporaryDirectory(prefix="restore-", dir=self.state) as folder:
                manifest, incoming = self._decode(self.destination, passphrase, pathlib.Path(folder), encrypted=encrypted)
            current = self.snapshot(current=True)
            cleanup = self._read_cleanup()
            rollback = self._write_rollback(current, cleanup)
            journal = {"schema": 1, "phase": "prepared", "backup_sha256": digest, "rollback": str(rollback), "context": self.context}
            self._journal(journal)
            try:
                journal["phase"] = "applying"
                self._journal(journal)
                self._apply_values(incoming)
                self._apply_cleanup(cleanup, restoring=True)
                self._validate_snapshot(self.snapshot(current=True))
                if health_check is not None:
                    health_check()
                journal["phase"] = "committed"
                self._journal(journal)
                self._finish_rollback(rollback)
            except BaseException:
                journal["phase"] = "rolling_back"
                self._journal(journal)
                self._apply_values(current)
                self._apply_cleanup(cleanup, restoring=False)
                journal["phase"] = "rolled_back"
                self._journal(journal)
                self._finish_rollback(rollback)
                raise
            return {
                "phase": "committed",
                "backup_sha256": digest,
                "created_utc": manifest["created_utc"],
                "files": sum(1 for value in incoming.values() if value is not None),
                "chain_data_included": False,
                "preserved": ["device TLS identity", "P2P onion", "Electrum onion", "RPC onion"],
            }

    def recover(self) -> dict:
        with self.lock():
            journal_path = self.state / "restore.json"
            if not journal_path.exists():
                return {"phase": "none"}
            journal = _json(journal_path.read_bytes())
            if journal.get("schema") != 1:
                raise ValueError("invalid restore journal")
            if journal.get("phase") not in ("prepared", "applying", "rolling_back"):
                return {"phase": journal.get("phase")}
            folder = pathlib.Path(journal.get("rollback", ""))
            values, cleanup = self._load_rollback(folder)
            self._apply_values(values)
            self._apply_cleanup(cleanup, restoring=False)
            journal["phase"] = "rolled_back"
            self._journal(journal)
            self._finish_rollback(folder)
            return {"phase": "rolled_back"}


def production_bundle() -> BackupBundle:
    from backup_guard import Guard
    guard = Guard.load()
    return BackupBundle(
        production_specs(guard.checked[4]),
        pathlib.Path("/var/lib/justverify-backup"),
        pathlib.Path("/boot/firmware/justverify-backup.jvb"),
        cleanup=(pathlib.Path("/var/lib/justverify/web/setup-token"), pathlib.Path("/var/lib/justverify/web/pending-owner.json")),
        barriers=(guard.checked[4].with_suffix(".transaction.json"), pathlib.Path("/var/lib/justverify/versions/transition.json")),
        validate_context=guard.validate,
        context=guard.context,
    )
