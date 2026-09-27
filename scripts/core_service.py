#!/usr/bin/python3 -I
"""Start the registered Core with its selected, Tor-owned P2P announcement."""
import base64
import hashlib
import json
import os
import pathlib
import pwd
import re
import stat
import sys


def read_regular(path, owners, limit):
    for item in (path, *path.parents):
        if item.is_symlink():
            raise ValueError('linked startup input')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid not in owners or info.st_mode & 0o022:
            raise ValueError('untrusted startup input')
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError('startup input too large')
    return data.decode()


def selection(policy, network):
    incoming = None
    outgoing = []
    proxy = []
    for line in policy.splitlines():
        if line.startswith('# JustVerify incoming='):
            if incoming is not None:
                raise ValueError('duplicate incoming selection')
            incoming = line.split('=', 1)[1].split(',')
            if len(set(incoming)) != len(incoming) or not (
                incoming == ['none'] or set(incoming) <= {'clearnet', 'tor', 'i2p'}
            ):
                raise ValueError('invalid incoming selection')
        elif line.startswith('onlynet='):
            outgoing.append(line.split('=', 1)[1])
        elif line.startswith('proxy='):
            proxy.append(line.split('=', 1)[1])
        elif re.match(r'(?:no)?(?:discover|externalip)=', line):
            raise ValueError('managed announcement option conflict')
    if len(set(outgoing)) != len(outgoing) or set(outgoing) - {'ipv4', 'ipv6', 'onion', 'i2p'}:
        raise ValueError('invalid outgoing selection')
    if len(proxy) > 1 or proxy and proxy[0] not in ('0', '127.0.0.1:9050'):
        raise ValueError('invalid proxy selection')
    if incoming is None:
        incoming = ['tor'] if network == 'regtest' else ['clearnet', 'tor']
    return set(incoming), set(outgoing or ['ipv4', 'ipv6', 'onion']), bool(proxy and proxy[0] != '0')


def onion_address(text):
    host = text.strip()
    if not re.fullmatch(r'[a-z2-7]{56}\.onion', host):
        raise ValueError('invalid P2P onion hostname')
    decoded = base64.b32decode(host[:-6].upper())
    if decoded[-1:] != b'\x03' or decoded[32:34] != hashlib.sha3_256(
        b'.onion checksum' + decoded[:32] + decoded[-1:]
    ).digest()[:2]:
        raise ValueError('invalid P2P onion checksum')
    return host


def announcement_args(policy, network, hostname=None):
    incoming, outgoing, proxied = selection(policy, network)
    # Supplying externalip otherwise disables Core's normal IP discovery.
    # Never undo proxy privacy or discover IPs with clearnet incoming disabled.
    discover = 'clearnet' in incoming and bool(outgoing & {'ipv4', 'ipv6'}) and not proxied and network != 'regtest'
    args = ['-discover=' + str(int(discover))]
    if 'tor' in incoming and 'onion' in outgoing:
        # onlynet/onion=0 also controls address gossip in upstream Core. Do not
        # silently re-enable outgoing Tor to announce an incoming-only address.
        args.append('-externalip=' + onion_address(hostname or '') + ':8333')
    return args


def main():
    if len(sys.argv) != 1:
        raise ValueError('fixed Core launcher takes no arguments')
    from node_ready import check
    check()
    etc = pathlib.Path('/etc/justverify')
    profile = json.loads(read_regular(etc / 'profile.json', {0}, 8192))
    registered = json.loads(read_regular(etc / 'node-ready.json', {0}, 16384))
    policy_path = pathlib.Path(profile['managed_config'])
    if policy_path != pathlib.Path('/var/lib/justverify/config/managed.conf'):
        policy_path.relative_to('/srv/justverify/data')
    policy = read_regular(policy_path, {0, pwd.getpwnam('justverify').pw_uid}, 65536)
    incoming, outgoing, _ = selection(policy, profile['network'])
    hostname = None
    if 'tor' in incoming and 'onion' in outgoing:
        hostname = read_regular(pathlib.Path('/run/justverify-tor/p2p.hostname'),
                                {0, pwd.getpwnam('debian-tor').pw_uid}, 128)
    binary = profile['binary']
    args = [binary, '-datadir=' + registered['instance']['core_data'],
            '-conf=/etc/justverify/bitcoin.conf', *announcement_args(policy, profile['network'], hostname)]
    os.execv(binary, args)


if __name__ == '__main__':
    try:
        # -I deliberately excludes the working directory from import paths.
        sys.path.insert(0, '/opt/justverify/scripts')
        main()
    except Exception:
        raise SystemExit('Core startup refused: check registered profile, peer policy and published Tor P2P hostname.')
