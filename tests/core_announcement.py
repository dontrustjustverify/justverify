#!/usr/bin/env python3
"""Announcement selection and untrusted-input boundaries; no node data."""
import base64
import hashlib
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('core_service', Path(__file__).resolve().parents[1] / 'scripts/core_service.py')
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)
public = bytes(range(32))
HOST = base64.b32encode(public + hashlib.sha3_256(b'.onion checksum' + public + b'\x03').digest()[:2] + b'\x03').decode().lower() + '.onion'


class Announcement(unittest.TestCase):
    def test_selection_and_proxy_privacy(self):
        for incoming in ('none', 'clearnet', 'tor', 'i2p', 'clearnet,tor', 'tor,i2p', 'clearnet,tor,i2p'):
            for outgoing in ('ipv4,ipv6', 'onion', 'i2p', 'ipv4,ipv6,onion,i2p'):
                for proxy in ('0', '127.0.0.1:9050'):
                    for network in ('main', 'test', 'testnet4', 'signet', 'regtest'):
                        policy = '# JustVerify incoming=' + incoming + '\n' + ''.join('onlynet=' + n + '\n' for n in outgoing.split(',')) + 'proxy=' + proxy + '\n'
                        announce = 'tor' in incoming.split(',') and 'onion' in outgoing.split(',')
                        args = core.announcement_args(policy, network, HOST if announce else None)
                        self.assertEqual(any(a.startswith('-externalip=') for a in args), announce)
                        self.assertEqual(args[0], '-discover=' + str(int('clearnet' in incoming.split(',') and 'ipv4' in outgoing.split(',') and proxy == '0' and network != 'regtest')))

    def test_defaults_and_hostname(self):
        self.assertEqual(core.announcement_args('', 'main', HOST), ['-discover=1', '-externalip=' + HOST + ':8333'])
        self.assertEqual(core.announcement_args('', 'regtest', HOST)[0], '-discover=0')
        for bad in (None, '', HOST + ':8333', HOST + '\nexternalip=example.invalid', 'a' * 56 + '.onion', HOST.upper()):
            with self.assertRaises(ValueError): core.announcement_args('', 'main', bad)

    def test_ambiguous_or_conflicting_policy(self):
        for bad in ('# JustVerify incoming=tor,tor', '# JustVerify incoming=', '# JustVerify incoming=none,tor', '# JustVerify incoming=tor\n# JustVerify incoming=none', 'onlynet=bad', 'onlynet=onion\nonlynet=onion', 'proxy=example.invalid', 'proxy=0\nproxy=0', 'discover=1', 'externalip=example.invalid', 'noexternalip=1'):
            with self.assertRaises(ValueError): core.selection(bad, 'main')

    def test_link_owner_size_and_permissions(self):
        with tempfile.TemporaryDirectory(prefix='jv-announcement-') as directory:
            parent = Path(directory).resolve()
            p = parent / 'hostname'; p.write_text(HOST); p.chmod(0o644)
            self.assertEqual(core.read_regular(p, {os.getuid()}, 128), HOST)
            with self.assertRaises(ValueError): core.read_regular(p, {os.getuid() + 1}, 128)
            with self.assertRaises(ValueError): core.read_regular(p, {os.getuid()}, 10)
            link = parent / 'linked'; link.symlink_to(p)
            with self.assertRaises(ValueError): core.read_regular(link, {os.getuid()}, 128)
            p.chmod(0o666)
            with self.assertRaises(ValueError): core.read_regular(p, {os.getuid()}, 128)
            fifo = parent / 'fifo'; os.mkfifo(fifo)
            with self.assertRaises(ValueError): core.read_regular(fifo, {os.getuid()}, 128)


if __name__ == '__main__': unittest.main()
