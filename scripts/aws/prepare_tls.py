#!/usr/bin/env python3
"""Prepare private demo TLS/mTLS material; no DNS, network or trust-store changes."""
import argparse
import ipaddress
import os
from pathlib import Path
import subprocess


def prepare(out, web_ip=None, aaos_ip=None):
    for value in (web_ip, aaos_ip):
        if value:
            ipaddress.ip_address(value)
    out.mkdir(mode=0o700, parents=True, exist_ok=False)
    os.chmod(out, 0o700)

    def run(*args):
        subprocess.run(['openssl', *args], cwd=out, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    def key(name):
        run('genpkey', '-algorithm', 'EC', '-pkeyopt', 'ec_paramgen_curve:P-256', '-out', name + '.key')
        (out / (name + '.key')).chmod(0o600)

    key('ca')
    run('req', '-new', '-x509', '-sha256', '-days', '7', '-key', 'ca.key',
        '-out', 'ca.crt', '-subj', '/CN=Attune Task13 Private Demo CA',
        '-addext', 'basicConstraints=critical,CA:TRUE,pathlen:0',
        '-addext', 'keyUsage=critical,keyCertSign,cRLSign')
    for name, dns, ip, usage in [
        ('web', 'attunemore.sasmaz.digital', web_ip, 'serverAuth'),
        ('aaos', 'aaos.attunemore.sasmaz.digital', aaos_ip, 'serverAuth'),
        ('internal', 'attune-internal', None, 'serverAuth'),
        ('client', 'attune-aaos-client', None, 'clientAuth'),
    ]:
        key(name)
        run('req', '-new', '-key', name + '.key', '-out', name + '.csr', '-subj', '/CN=' + dns)
        san = 'DNS:' + dns + (',IP:' + ip if ip else '')
        (out / (name + '.ext')).write_text(
            'basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature\n'
            'extendedKeyUsage=' + usage + '\nsubjectAltName=' + san + '\n')
        run('x509', '-req', '-sha256', '-days', '2', '-in', name + '.csr',
            '-CA', 'ca.crt', '-CAkey', 'ca.key', '-CAcreateserial',
            '-extfile', name + '.ext', '-out', name + '.crt')
        run('verify', '-CAfile', 'ca.crt', '-purpose', 'sslclient' if usage == 'clientAuth' else 'sslserver', name + '.crt')
    return out


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--web-ip')
    parser.add_argument('--aaos-ip')
    args = parser.parse_args()
    print(prepare(args.output, args.web_ip, args.aaos_ip))
