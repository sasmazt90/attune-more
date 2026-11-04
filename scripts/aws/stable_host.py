#!/usr/bin/env python3
"""Host steps that let an ordinary EC2 Stop/Start keep working. Idempotent.

A restart assigns new public IPs, so origins and certificates use the stable
hostnames instead of an address. The public names carry browser-trusted certificates
requested from this PC's control tool. The private mTLS link between the hosts keeps
its own private CA. No private key ever leaves its host: only certificate requests and
public certificates travel. Standard library plus openssl.
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

WEB_DOMAIN = 'attunemore.sasmaz.digital'
AAOS_DOMAIN = 'aaos.attunemore.sasmaz.digital'
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
# Private CA, private names only. 'internal' secures WEB:8443; 'client' is what AAOS presents to it.
LEAVES = {
    'internal': {'host': 'web', 'dns': 'attune-internal', 'usage': 'serverAuth'},
    'client': {'host': 'aaos', 'dns': 'attune-aaos-client', 'usage': 'clientAuth'},
}
# Browser-trusted certificates: file name and the one name each may carry.
PUBLIC_LEAVES = {'web': {'file': 'web', 'dns': WEB_DOMAIN}, 'aaos': {'file': 'aaos', 'dns': AAOS_DOMAIN}}
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


def public_request(role, tls=TLS_ROOT):
    """A request from the key already on this host. Reusing it keeps the key where it is."""
    leaf = PUBLIC_LEAVES[role]
    return openssl('req', '-new', '-key', str(tls / (leaf['file'] + '.key')), '-subj', '/CN=' + leaf['dns'],
                   '-addext', 'subjectAltName=DNS:' + leaf['dns'])


def certificate_names(path):
    text = openssl('x509', '-in', str(path), '-noout', '-ext', 'subjectAltName')
    return sorted(re.findall(r'DNS:([^\s,]+)', text))


def certificate_dates(path):
    def parse(value):
        return dt.datetime.strptime(value.split('=', 1)[1].strip(), '%b %d %H:%M:%S %Y %Z').replace(tzinfo=dt.timezone.utc)
    lines = openssl('x509', '-in', str(path), '-noout', '-startdate', '-enddate').splitlines()
    return parse(lines[0]), parse(lines[1])


def publicly_trusted(path):
    """Checks the chain against the system's public roots, as a browser would."""
    try:
        openssl('verify', '-CApath', '/etc/ssl/certs', '-untrusted', str(path), str(path))
        return True
    except RuntimeError:
        return False


def public_state(role, tls=TLS_ROOT, now=None):
    leaf = PUBLIC_LEAVES[role]
    path = tls / (leaf['file'] + '.crt')
    if not path.exists():
        return {'role': role, 'name': leaf['dns'], 'present': False, 'needsCertificate': True}
    start, end = certificate_dates(path)
    now = now or dt.datetime.now(dt.timezone.utc)
    names = certificate_names(path)
    trusted = publicly_trusted(path)
    days_left = (end - now).total_seconds() / 86400
    lifetime = (end - start).total_seconds() / 86400
    # Renew in the last third of the lifetime, because a stopped host cannot renew itself.
    needs = names != [leaf['dns']] or not trusted or days_left < lifetime / 3
    return {'role': role, 'name': leaf['dns'], 'present': True, 'names': names, 'trusted': trusted,
            'notAfter': end.isoformat(), 'daysLeft': round(days_left, 1), 'lifetimeDays': round(lifetime, 1), 'needsCertificate': needs}


def install_public(role, chain, tls=TLS_ROOT, group='caddy', check_trust=True):
    leaf = PUBLIC_LEAVES[role]
    target = tls / (leaf['file'] + '.crt')
    key = tls / (leaf['file'] + '.key')
    with tempfile.TemporaryDirectory() as directory:
        candidate = Path(directory, 'candidate.crt')
        candidate.write_text(chain)
        if public_key('x509', '-in', str(candidate)) != public_key('pkey', '-in', str(key)):
            raise ValueError('Certificate does not match the key on this host')
        if certificate_names(candidate) != [leaf['dns']]:
            raise ValueError('Certificate is not for ' + leaf['dns'])
        if check_trust and not publicly_trusted(candidate):
            raise ValueError('Certificate does not chain to a public root')
    if target.exists():
        stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d%H%M%S%f')
        archive = tls / ('previous-' + stamp)
        archive.mkdir(mode=0o750)
        shutil.copy2(target, archive / target.name)
        shutil.chown(archive, 'root', group)
    write_atomic(target, chain, 0o640, group)
    return public_state(role, tls)


def read_payload(encoded):
    return json.loads(base64.b64decode(encoded))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('step', choices=['origins', 'requests', 'sign', 'install', 'restart', 'public-state', 'public-request', 'install-public'])
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
    elif args.step == 'public-state':
        output = public_state(args.role)
    elif args.step == 'public-request':
        output = {'role': args.role, 'name': PUBLIC_LEAVES[args.role]['dns'], 'request': public_request(args.role)}
    elif args.step == 'install-public':
        output = install_public(args.role, read_payload(args.payload)['chain'])
        subprocess.run(['systemctl', 'restart', 'attune-caddy'], check=True)
    else:
        subprocess.run(['systemctl', 'restart', *RESTARTS[args.role]], check=True)
        output = {'role': args.role, 'restarted': RESTARTS[args.role]}
    json.dump(output, sys.stdout)


if __name__ == '__main__':
    main()
