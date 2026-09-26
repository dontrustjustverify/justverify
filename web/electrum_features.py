"""Rewrite only pinned electrs feature announcements, with bounded buffering.

Other JSON-RPC objects, notifications and large replies retain their exact bytes.
Each batch member is handled independently; a large sibling cannot suppress the
small feature reply. This does not impose a message-size limit on the transport.
"""
import json
import re

FEATURE_FIELDS = {'genesis_hash', 'hosts', 'protocol_max', 'protocol_min',
                  'pruning', 'server_version', 'hash_function'}
TOKENS = re.compile(rb'\\.|["{}\[\]]|\\$', re.DOTALL)


class FeatureReplies:
    def __init__(self, backend_port, public_port=50001):
        self.backend_port = backend_port
        self.public_port = public_port
        self.stack = []
        self.quoted = False
        self.escaped = False
        self.record = None
        self.record_depth = None
        self.passthrough = False
        self.limit = 65536

    def rewrite(self, raw):
        try:
            reply = json.loads(raw)
            if not isinstance(reply, dict) or set(reply) not in (
                    {'id', 'result'}, {'id', 'jsonrpc', 'result'}):
                return raw
            result = reply['result']
            if not isinstance(result, dict) or set(result) != FEATURE_FIELDS:
                return raw
            if (result['hosts'] != {'tcp_port': self.backend_port}
                    or result['hash_function'] != 'sha256' or result['pruning'] is not None
                    or not isinstance(result['server_version'], str)
                    or not result['server_version'].startswith('electrs/')
                    or not isinstance(result['genesis_hash'], str)
                    or re.fullmatch('[0-9a-f]{64}', result['genesis_hash']) is None):
                return raw
            result['hosts']['tcp_port'] = self.public_port
            return json.dumps(reply, separators=(',', ':'), ensure_ascii=True).encode()
        except (ValueError, TypeError, KeyError, RecursionError):
            return raw

    def append(self, data, output):
        if self.record is None or self.passthrough:
            output.append(data)
        elif len(self.record) + len(data) <= self.limit:
            self.record.extend(data)
        else:
            output.extend((bytes(self.record), data))
            self.record.clear()
            self.passthrough = True

    def feed(self, data):
        output = []
        start = 0
        skip = 1 if self.escaped else 0
        self.escaped = False
        for match in TOKENS.finditer(data, skip):
            token = match.group()
            if token.startswith(b'\\'):
                if self.quoted and len(token) == 1:
                    self.escaped = True
                continue
            if token == b'"':
                self.quoted = not self.quoted
                continue
            if self.quoted:
                continue
            if token in (b'{', b'['):
                if token == b'{' and (not self.stack or self.stack == [b'[']):
                    self.append(data[start:match.start()], output)
                    start = match.start()
                    self.record = bytearray()
                    self.record_depth = len(self.stack)
                    self.passthrough = False
                self.stack.append(token)
            elif self.stack:
                self.stack.pop()
                if self.record is not None and len(self.stack) == self.record_depth:
                    self.append(data[start:match.end()], output)
                    start = match.end()
                    if not self.passthrough:
                        output.append(self.rewrite(bytes(self.record)))
                    self.record = None
                    self.record_depth = None
                    self.passthrough = False
        self.append(data[start:], output)
        return b''.join(output)

    def finish(self):
        # Preserve a truncated final object on upstream EOF, without inventing a reply.
        remaining = bytes(self.record) if self.record is not None else b''
        self.record = None
        return remaining
