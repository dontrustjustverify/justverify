#!/usr/bin/env python3
"""Private filesystem worker embedded in the version daemon; never a client API.

Only the daemon supplies a registered instance. No shell, recursive rmtree, or
caller-selected delete list. All deletion is fd-relative, no-follow, same mount.
"""
import contextlib
import fcntl
import hashlib
import json
import os
import pathlib
import re
import stat
import sys
import subprocess

class ResetError(ValueError):
    pass


NETWORKS = {'main': ('', 'bitcoin'), 'test': ('testnet3', 'testnet'),
            'testnet4': ('testnet4', 'testnet4'), 'signet': ('signet', 'signet'),
            'regtest': ('regtest', 'regtest')}
CORE_DIRS = ('blocks', 'chainstate', 'chainstate_snapshot', 'indexes')
CORE_FILES = ('mempool.dat', 'mempool.dat.new', 'fee_estimates.dat')
DB_FILE = re.compile(r'(?:[0-9]+\.(?:log|ldb|sst|dbtmp)|MANIFEST-[0-9]+|OPTIONS-[0-9]+|CURRENT|LOCK|LOG(?:\.old(?:\.[0-9]+)?)?|IDENTITY|[0-9]+\.blob)')


def identity(fd):
    info = os.fstat(fd)
    return [info.st_dev, info.st_ino]


def mount_id(fd):
    # Bind mounts may have the same st_dev. Linux fdinfo distinguishes them.
    path = pathlib.Path('/proc/self/fdinfo') / str(fd)
    if path.exists():
        for line in path.read_text().splitlines():
            if line.startswith('mnt_id:'):
                return int(line.split(':')[1])
    return os.fstat(fd).st_dev


def parts(path):
    value = pathlib.PurePosixPath(path)
    if value.is_absolute() or not value.parts or any(p in ('.', '..') for p in value.parts):
        raise ResetError('unregistered relative path')
    return value.parts


def open_absolute(path):
    path=pathlib.Path(path)
    if not path.is_absolute():raise ResetError('absolute private root required')
    fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY)
    try:
        for name in path.parts[1:]:
            next_fd=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
            os.close(fd);fd=next_fd
        return fd
    except BaseException:os.close(fd);raise


class Scope:
    def __init__(self, root, instance):
        self.stack = contextlib.ExitStack()
        self.root_path=root
        self.root = self.own(open_absolute(root))
        self.mount = mount_id(self.root)
        self.instance = instance
        self.boot = pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip() if sys.platform=='linux' else 'local'
        self.uuid = subprocess.run(['/usr/bin/findmnt','-n','-o','UUID','--target',str(root)],check=True,capture_output=True,text=True).stdout.strip() if sys.platform=='linux' else ''
        if sys.platform=='linux' and not self.uuid:raise ResetError('data filesystem identity unavailable')
        self.core = str(pathlib.Path(instance['core_data']).relative_to(root))
        self.index = str(pathlib.Path(instance['electrs_data']).relative_to(root))
        core_parts, index_parts = parts(self.core), parts(self.index)
        if len(core_parts) != 3 or core_parts[:2] != index_parts[:2] or core_parts[-1] != 'core' or index_parts[-1] != 'electrs-0.11.1':
            raise ResetError('invalid registered data layout')
        if core_parts[0] != instance['network'] or not re.fullmatch(r'[0-9]+\.[0-9]+(?:\.[0-9]+)?(?:-watch-only)?', core_parts[1]):
            raise ResetError('invalid registered profile identity')
        self.folder = '/'.join(core_parts[:2])
        self.core_sub, self.index_sub = NETWORKS[instance['network']]
        self.anchors = {'.': identity(self.root)}
        for path in (core_parts[0], self.folder, self.core, self.index):
            self.anchors[path] = identity(self.directory(path))
        self.core_scope = self.core + ('/' + self.core_sub if self.core_sub else '')
        # A registered, running Core has created this directory. Never create it
        # as a substitute for missing active storage.
        self.anchors[self.core_scope] = identity(self.directory(self.core_scope))

    def __enter__(self): return self
    def __exit__(self, *args): self.stack.close()

    def own(self, fd):
        self.stack.callback(os.close, fd)
        return fd

    def reachable(self,parent,path):
        current=open_absolute(self.root_path)
        try:
            if identity(current)!=identity(self.root) or mount_id(current)!=self.mount:raise ResetError('data root moved during reset')
            for name in parts(path):
                next_fd=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=current)
                os.close(current);current=next_fd
                if mount_id(current)!=self.mount:raise ResetError('data mount changed during reset')
            if identity(current)!=identity(parent):raise ResetError('chain ancestor moved during reset')
        finally:os.close(current)

    def directory(self, path):
        fd = self.root
        for name in parts(path):
            fd = self.own(os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd))
            if mount_id(fd) != self.mount: raise ResetError('unexpected nested mount')
        return fd

    def allowlist(self):
        return [self.core_scope+'/'+name for name in (*CORE_DIRS, *CORE_FILES)] + [self.index+'/'+self.index_sub]

    def wallet_guard(self):
        if self.instance.get('watch_only', False):
            raise ResetError('watch-only version transition requires verified wallet migration; data preserved')
        # Preserve every wallet; never attempt to open it in the target binary.
        for base in {self.core, self.core_scope}:
            fd = self.directory(base)
            for name in ('wallet.dat', 'wallets'):
                try:
                    metadata=os.stat(name, dir_fd=fd, follow_symlinks=False)
                except FileNotFoundError: continue
                if name=='wallets' and stat.S_ISDIR(metadata.st_mode):
                    empty=self.directory(base+'/wallets')
                    if not os.listdir(empty):continue
                raise ResetError('wallet data present; version transition blocked before deletion')
            try:
                config = os.open('settings.json', os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
            except FileNotFoundError: continue
            with os.fdopen(config, 'rb') as file:
                saved = json.load(file)
            if set(saved) - {'_warning_'}:
                raise ResetError('persistent Core settings require review before version transition')

    def visit(self, parent, name, relative, delete=False, parent_path=None):
        try: before = os.stat(name, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError: return
        directory = stat.S_ISDIR(before.st_mode)
        if not directory and not stat.S_ISREG(before.st_mode):
            raise ResetError('linked or special chain entry refused')
        fd = os.open(name, (os.O_RDWR if delete and not directory and name in ('.lock','LOCK') else os.O_RDONLY) | os.O_NOFOLLOW | os.O_NONBLOCK | (os.O_DIRECTORY if directory else 0), dir_fd=parent)
        try:
            if identity(fd) != [before.st_dev, before.st_ino] or mount_id(fd) != self.mount:
                raise ResetError('chain entry or mount changed')
            if delete and not directory and name in ('.lock','LOCK'): fcntl.lockf(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            if not directory and os.fstat(fd).st_nlink != 1:
                raise ResetError('hard-linked chain entry refused')
            if directory:
                for child in sorted(os.listdir(fd)):
                    suffix = relative+'/'+child
                    # Database directories must not become a vehicle for deleting
                    # unrelated user files. Unknown formats stop before deletion.
                    sub = suffix.split('/')
                    is_dir = stat.S_ISDIR(os.stat(child, dir_fd=fd, follow_symlinks=False).st_mode)
                    if is_dir:
                        allowed = (relative == 'blocks' and child == 'index') or (relative == 'indexes' and child in ('txindex','txospenderindex','coinstats','blockfilter')) or (relative == 'indexes/blockfilter' and child == 'basic')
                        if not allowed: raise ResetError('unknown chain database directory')
                    elif not (DB_FILE.fullmatch(child) or (relative == 'blocks' and (re.fullmatch(r'(?:blk|rev)[0-9]{5}\.dat', child) or child in ('.lock','xor.dat'))) or (relative == 'chainstate_snapshot' and child == 'base_blockhash')):
                        raise ResetError('unknown chain database file; manual review required')
                    self.visit(fd, child, suffix, delete, parent_path+'/'+name if parent_path else None)
                if delete: os.fsync(fd)
            if delete:
                self.reachable(parent,parent_path)
                after = os.stat(name, dir_fd=parent, follow_symlinks=False)
                if [after.st_dev, after.st_ino] != identity(fd): raise ResetError('chain entry moved')
                if directory: os.rmdir(name, dir_fd=parent)
                else: os.unlink(name, dir_fd=parent)
                os.fsync(parent)
        finally: os.close(fd)

    def scan(self, delete=False):
        for path in self.allowlist():
            parent, name = path.rsplit('/', 1)
            fd = self.directory(parent)
            try: metadata=os.stat(name,dir_fd=fd,follow_symlinks=False)
            except FileNotFoundError: continue
            expected_dir=name in CORE_DIRS or path==self.index+'/'+self.index_sub
            if expected_dir != stat.S_ISDIR(metadata.st_mode):raise ResetError('unexpected chain entry type')
            self.visit(fd, name, name, delete, parent)

    def receipt(self):
        self.wallet_guard()
        self.scan()
        # Real write + fsync in both retained datadirs. O_EXCL, never an existing file.
        for path in (self.core, self.index):
            fd = self.directory(path)
            name = '.version-write-check-' + os.urandom(12).hex()
            file = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
            try: os.write(file, b'write-check'); os.fsync(file)
            finally: os.close(file); os.unlink(name, dir_fd=fd); os.fsync(fd)
        usage = os.fstatvfs(self.root)
        available = usage.f_bavail * usage.f_frsize
        # Startup reserve, in addition to space reclaimed by the reset. This is
        # not a promise that an unpruned full blockchain will fit indefinitely.
        if available < 512 * 1024 * 1024: raise ResetError('at least 512 MiB free startup reserve required')
        return {'schema': 1, 'volume_uuid': self.uuid, 'boot':self.boot, 'mount_id':self.mount, 'anchors': self.anchors, 'allowlist': self.allowlist(), 'startup_reserve_bytes': 512 * 1024 * 1024}


def run(request):
    with Scope(request['root'], request['instance']) as scope:
        if request['action'] == 'prepare': return scope.receipt()
        if request['action'] not in ('validate', 'reset'): raise ResetError('unknown private worker action')
        receipt = request['receipt']
        if receipt['schema'] != 1 or receipt['anchors'] != scope.anchors or receipt['allowlist'] != scope.allowlist():
            raise ResetError('registered path or volume changed; review required')
        if receipt['volume_uuid']!=scope.uuid or (receipt['boot']==scope.boot and receipt['mount_id']!=scope.mount):
            raise ResetError('registered mount changed; review required')
        usage=os.fstatvfs(scope.root)
        if usage.f_bavail*usage.f_frsize<receipt['startup_reserve_bytes']:raise ResetError('startup reserve no longer available')
        scope.wallet_guard()
        scope.scan()  # Whole scope validation before the first unlink.
        if request['action'] == 'reset':
            # Core uses an advisory data lock. A failed service shutdown or an
            # independently launched writer must not permit deletion.
            fd=scope.directory(scope.core_scope)
            lock=os.open('.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600,dir_fd=fd)
            try:
                fcntl.lockf(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                scope.scan(delete=True)
            finally:os.close(lock)
        return {'ok': True}


if __name__ == '__main__':
    try:
        request = json.loads(sys.stdin.buffer.read(65537))
        if sys.platform == 'linux':
            import ctypes, signal
            if ctypes.CDLL(None, use_errno=True).prctl(1, signal.SIGKILL, 0, 0, 0) != 0:raise ResetError('cannot bind reset worker lifetime')
            if os.getppid() != request['parent_pid']:raise ResetError('version daemon exited')
        elif request['action'] == 'reset':raise ResetError('destructive reset requires the Linux service environment')
        print(json.dumps({'ok': True, 'result': run(request)}))
    except Exception as error:
        # Never include OS exception paths, config values, or filenames.
        message = str(error) if isinstance(error, ResetError) else 'chain storage validation failed'
        print(json.dumps({'ok': False, 'error': message}))
        sys.exit(1)
