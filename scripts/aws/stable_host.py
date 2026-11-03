#!/usr/bin/env python3
"""Host steps that let an ordinary EC2 Stop/Start keep working. Idempotent.

A restart assigns new public IPs, so origins and certificates use the stable
hostnames instead of an address. Certificates are reissued from each host's
existing private keys, so no private key ever leaves its host. Only certificate
requests and public certificates travel between hosts. Standard library plus openssl.
"""
import argparse
import base64
import datetime as dt
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

WEB_DOMAIN = 'attune.sasmaz.digital'
AAOS_DOMAIN = 'aaos.sasmaz.digital'
ENV_ROOT = Path('/etc/attune')
TLS_ROOT = ENV_ROOT / 'tls'
CA_DAYS = 3650
LEAF_DAYS = 825
ORIGINS = {
    'web': {
        'caddy.env': {'WEB_DOMAIN': WEB_DOMAIN},
        'api-web.env': {'ATTUNE_TRUSTED_ORIGINS': 'https://' + WEB_DOMAIN},
        'web-web.env': {'ATTUNE_MENTAL_TTS_FRONTEND_ORIGIN': 'https://' + WEB_DOMAIN},
        'capture.env': {'ATTUNE_CAPTURE_SENDER_ORIGIN': 'https://' + AAOS_DOMAIN},
    },
    'aaos': {
        'caddy.env': {'AAOS_DOMAIN': AAOS_DOMAIN},
        'aaos.env': {'ATTUNE_AUDIO_ORIGIN': 'https://' + AAOS_DOMAIN},
    },
}
# CN and SAN are public names. 'internal' secures WEB:8443; 'client' is what AAOS presents to it.
LEAVES = {
    'web': {'host': 'web', 'dns': WEB_DOMAIN, 'usage': 'serverAuth'},
    'internal': {'host': 'web', 'dns': 'attune-internal', 'usage': 'serverAuth'},
    'aaos': {'host': 'aaos', 'dns': AAOS_DOMAIN, 'usage': 'serverAuth'},
    'client': {'host': 'aaos', 'dns': 'attune-aaos-client', 'usage': 'clientAuth'},
}
CA_FILES = {'web': ['clients-ca.crt', 'server-ca.crt'], 'aaos': ['server-ca.crt']}
RESTARTS = {
    'web': ['attune-caddy', 'attune-api@web', 'attune-web@web', 'attune-capture'],
    'aaos': ['attune-caddy', 'attune-audio'],
}


def openssl(*args, cwd=None):
    done = subprocess.run(['openssl', *args], cwd=cwd, capture_output=True, text=True)
    if done.returncode != 0:
        # openssl errors name files and reasons, never key material.
        raise RuntimeError('openssl {} failed: {}'.format(args[0], done.stderr.strip()[:300]))
    return done.stdout


def write_atomic(path, text, mode, group=None):
    import grp  # Linux only; hosts run Ubuntu.
    temporary = path.with_name('.' + path.name + '.tmp')
    temporary.write_text(text)
    os.chmod(temporary, mode)
    gid = grp.getgrnam(group).gr_gid if group else path.stat().st_gid if path.exists() else 0
    os.chown(temporary, 0, gid)
    os.replace(temporary, path)


def updated_env(text, updates):
    """Returns text with only the named keys replaced, or appended when missing."""
    lines = text.splitlines()
    seen = set()
    for index, line in enumerate(lines):
        match = re.fullmatch(r'\s*([A-Z][A-Z0-9_]*)=.*', line)
        if match and match[1] in updates:
            lines[index] = '{}={}'.format(match[1], updates[match[1]])
            seen.add(match[1])
    lines.extend('{}={}'.format(key, value) for key, value in updates.items() if key not in seen)
    return '\n'.join(lines) + '\n'


def set_origins(role, root=ENV_ROOT):
    changed = []
    for name, updates in ORIGINS[role].items():
        path = root / name
        old = path.read_text()
        new = updated_env(old, updates)
        if new != old:
            backup = path.with_name(name + '.before-stable-origins')
            if not backup.exists():
                shutil.copy2(path, backup)
            stat = path.stat()
            write_atomic(path, new, stat.st_mode & 0o777)
            os.chown(path, stat.st_uid, stat.st_gid)
            changed.append(name)
    return changed


def make_requests(role, tls=TLS_ROOT):
    requests = {}
    for name, leaf in LEAVES.items():
        if leaf['host'] == role:
            requests[name] = openssl('req', '-new', '-key', str(tls / (name + '.key')), '-subj', '/CN=' + leaf['dns'])
    return requests


def sign_all(requests, days=LEAF_DAYS, ca_days=CA_DAYS, workspace=None):
    """Issues every leaf from a new CA whose key is destroyed before this returns."""
    if set(requests) != set(LEAVES):
        raise ValueError('A request for every certificate is required')
    root = workspace or ('/run' if os.path.isdir('/run') and os.access('/run', os.W_OK) else None)
    directory = tempfile.mkdtemp(prefix='attune-ca-', dir=root)
    os.chmod(directory, 0o700)
    try:
        openssl('genpkey', '-algorithm', 'EC', '-pkeyopt', 'ec_paramgen_curve:P-256', '-out', 'ca.key', cwd=directory)
        os.chmod(os.path.join(directory, 'ca.key'), 0o600)
        permitted = ','.join('permitted;DNS:' + leaf['dns'] for leaf in LEAVES.values())
        openssl('req', '-new', '-x509', '-sha256', '-days', str(ca_days), '-key', 'ca.key', '-out', 'ca.crt',
                '-subj', '/CN=Attune.more Private CA',
                '-addext', 'basicConstraints=critical,CA:TRUE,pathlen:0',
                '-addext', 'keyUsage=critical,keyCertSign,cRLSign',
                '-addext', 'nameConstraints=critical,' + permitted, cwd=directory)
        certificates = {}
        for name, leaf in LEAVES.items():
            Path(directory, name + '.csr').write_text(requests[name])
            Path(directory, name + '.ext').write_text(
                'basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature\n'
                'extendedKeyUsage={}\nsubjectAltName=DNS:{}\n'.format(leaf['usage'], leaf['dns']))
            openssl('x509', '-req', '-sha256', '-days', str(days), '-in', name + '.csr', '-CA', 'ca.crt', '-CAkey', 'ca.key',
                    '-CAcreateserial', '-extfile', name + '.ext', '-out', name + '.crt', cwd=directory)
            purpose = 'sslclient' if leaf['usage'] == 'clientAuth' else 'sslserver'
            openssl('verify', '-CAfile', 'ca.crt', '-purpose', purpose, name + '.crt', cwd=directory)
            certificates[name] = Path(directory, name + '.crt').read_text()
        return {'ca': Path(directory, 'ca.crt').read_text(), 'certificates': certificates}
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def public_key(*args):
    return openssl(*args, '-noout', '-pubkey') if args[0] == 'x509' else openssl(*args, '-pubout')


def install_certificates(role, bundle, tls=TLS_ROOT, group='caddy'):
    stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d%H%M%S')
    names = [name for name, leaf in LEAVES.items() if leaf['host'] == role]
    for name in names:
        # Refuse before touching anything if a certificate does not belong to the key on this host.
        with tempfile.NamedTemporaryFile('w', suffix='.crt') as candidate:
            candidate.write(bundle['certificates'][name])
            candidate.flush()
            if public_key('x509', '-in', candidate.name) != public_key('pkey', '-in', str(tls / (name + '.key'))):
                raise ValueError('Certificate for {} does not match the key on this host'.format(name))
    archive = tls / ('previous-' + stamp)
    archive.mkdir(mode=0o750)
    for path in tls.glob('*.crt'):
        shutil.copy2(path, archive / path.name)
    shutil.chown(archive, 'root', group)
    for name in names:
        write_atomic(tls / (name + '.crt'), bundle['certificates'][name], 0o640, group)
    for name in CA_FILES[role]:
        write_atomic(tls / name, bundle['ca'], 0o640, group)
    return names + CA_FILES[role]


def read_payload(encoded):
    return json.loads(base64.b64decode(encoded))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('step', choices=['origins', 'requests', 'sign', 'install', 'restart'])
    parser.add_argument('--role', choices=sorted(ORIGINS))
    parser.add_argument('--payload', help='Base64 JSON from the previous step. Public data only.')
    args = parser.parse_args()
    if args.step == 'origins':
        output = {'role': args.role, 'changed': set_origins(args.role)}
    elif args.step == 'requests':
        output = {'role': args.role, 'requests': make_requests(args.role)}
    elif args.step == 'sign':
        output = sign_all(read_payload(args.payload))
    elif args.step == 'install':
        output = {'role': args.role, 'installed': install_certificates(args.role, read_payload(args.payload))}
    else:
        subprocess.run(['systemctl', 'restart', *RESTARTS[args.role]], check=True)
        output = {'role': args.role, 'restarted': RESTARTS[args.role]}
    json.dump(output, sys.stdout)


if __name__ == '__main__':
    main()
