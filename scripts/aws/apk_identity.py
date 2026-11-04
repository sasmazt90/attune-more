#!/usr/bin/env python3
"""Reads which certificate signed an APK, and compares it with the pinned public identity. Standard library only.

Android allows an in-place update only when the signing certificate stays the same, so this identity decides
whether saved data can survive an upgrade. Only the public certificate's fingerprint is involved. The private
key is never needed here, and nothing in the repository can sign with it.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

SCHEME_V2 = 0x7109871a
SCHEME_V3 = 0xf05368c0
MAGIC = b'APK Sig Block 42'
PIN_PATH = 'apps/automotive/signing/cloud-demo-certificate.json'


class NotSigned(ValueError):
    pass


def _sequence(data):
    """Splits a sequence of length-prefixed items, the format every level of the signing block uses."""
    at = 0
    while at < len(data):
        if at + 4 > len(data):
            raise NotSigned('Truncated signing block')
        size = struct.unpack_from('<I', data, at)[0]
        at += 4
        if at + size > len(data):
            raise NotSigned('Truncated signing block')
        yield data[at:at + size]
        at += size


def _prefixed(data):
    size = struct.unpack_from('<I', data, 0)[0]
    return data[4:4 + size], data[4 + size:]


def _block_pairs(apk):
    end = apk.rfind(b'PK\x05\x06')
    if end < 0:
        raise NotSigned('Not a ZIP file')
    directory = struct.unpack_from('<I', apk, end + 16)[0]
    if directory < 24 or apk[directory - 16:directory] != MAGIC:
        raise NotSigned('No APK signing block')
    size = struct.unpack_from('<Q', apk, directory - 24)[0]
    start = directory - size - 8
    if start < 0:
        raise NotSigned('Bad APK signing block')
    pairs = apk[start + 8:directory - 24]
    at = 0
    while at < len(pairs):
        length = struct.unpack_from('<Q', pairs, at)[0]
        identifier = struct.unpack_from('<I', pairs, at + 8)[0]
        yield identifier, pairs[at + 12:at + 8 + length]
        at += 8 + length


def signing_certificates(path):
    """SHA-256 of each certificate in the APK's v2 and v3 signatures, as {scheme: [fingerprints]}."""
    found = {}
    for identifier, value in _block_pairs(Path(path).read_bytes()):
        scheme = {SCHEME_V2: 'v2', SCHEME_V3: 'v3'}.get(identifier)
        if not scheme:
            continue
        signers, _ = _prefixed(value)
        for signer in _sequence(signers):
            signed, _ = _prefixed(signer)
            _digests, rest = _prefixed(signed)
            certificates, _ = _prefixed(rest)
            found.setdefault(scheme, []).extend(hashlib.sha256(der).hexdigest() for der in _sequence(certificates))
    return found


def signing_identity(path):
    """The one certificate fingerprint that signed this APK. Anything ambiguous is refused."""
    found = signing_certificates(path)
    every = {fingerprint for rows in found.values() for fingerprint in rows}
    if len(every) != 1:
        raise NotSigned('Expected exactly one signing certificate, found {}'.format(len(every)))
    return every.pop()


def pinned_identity(root):
    return json.loads((Path(root) / PIN_PATH).read_text(encoding='utf8'))['sha256']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('apk')
    parser.add_argument('--expect', help='Fingerprint to require. Exits 3 if the APK has another.')
    args = parser.parse_args()
    found = signing_identity(args.apk)
    print(json.dumps({'sha256': found, 'schemes': signing_certificates(args.apk)}))
    if args.expect and found != args.expect.lower():
        print('APK is signed by {}, not by the pinned identity {}'.format(found, args.expect), file=sys.stderr)
        return 3
    return 0


if __name__ == '__main__':
    sys.exit(main())
