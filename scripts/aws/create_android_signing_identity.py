#!/usr/bin/env python3
"""Creates the one signing identity for the cloudDemo APK. Run once, by an operator, on Windows with `gh` signed in.

The private key goes to two places and no others: a GitHub environment secret, which only the job that builds this APK
can read, and a copy on this PC encrypted for this Windows user. GitHub secrets cannot be read back, so that copy is the
only recovery. Only the public certificate's fingerprint enters the repository. No value is printed or passed in a command
line. It refuses to run if an identity already exists, because a new key would stop every future in-place update.
"""
import argparse
import base64
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID

ROOT = Path(__file__).resolve().parents[2]
PIN = ROOT / 'apps/automotive/signing/cloud-demo-certificate.json'
ALIAS = 'attune-cloud-demo'
REPOSITORY = 'sasmazt90/attune-more'
ENVIRONMENT = 'android-cloud-demo-signing'
# Pull requests build from refs/pull/<n>/merge, and GitHub matches that full name. Forks get no secrets, and the job skips them.
BRANCHES = ['main', 'claude/**', 'refs/pull/*/merge']
BACKUP = Path(os.environ.get('USERPROFILE', '.')) / 'AttuneMore' / 'secrets' / 'android-cloud-demo-signing.xml'
YEARS = 30


def make_identity():
    """Returns (keystore bytes, password, certificate DER). Nothing touches the disk here."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=4096)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Attune.more Cloud Demo'), x509.NameAttribute(NameOID.ORGANIZATION_NAME, 'Attune.more')])
    now = dt.datetime.now(dt.timezone.utc)
    certificate = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number())
                   .not_valid_before(now - dt.timedelta(days=1)).not_valid_after(now + dt.timedelta(days=365 * YEARS)).sign(key, hashes.SHA256()))
    password = secrets.token_urlsafe(36)
    keystore = pkcs12.serialize_key_and_certificates(ALIAS.encode(), key, certificate, None, serialization.BestAvailableEncryption(password.encode()))
    return keystore, password, certificate.public_bytes(serialization.Encoding.DER), certificate


def gh(*args, stdin=None):
    done = subprocess.run(['gh', *args], input=stdin, capture_output=True, text=True, encoding='utf8')
    if done.returncode != 0:
        raise RuntimeError('gh {} failed: {}'.format(args[0], done.stderr.strip()[:300]))
    return done.stdout


def prepare_environment():
    body = json.dumps({'deployment_branch_policy': {'protected_branches': False, 'custom_branch_policies': True}})
    subprocess.run(['gh', 'api', '-X', 'PUT', 'repos/{}/environments/{}'.format(REPOSITORY, ENVIRONMENT), '--input', '-'], input=body, text=True, check=True, capture_output=True)
    for branch in BRANCHES:
        subprocess.run(['gh', 'api', '-X', 'POST', 'repos/{}/environments/{}/deployment-branch-policies'.format(REPOSITORY, ENVIRONMENT), '-f', 'name=' + branch, '-f', 'type=branch'], check=True, capture_output=True)


def store_secret(name, value):
    """gh reads the value from stdin, so it never appears in a command line."""
    gh('secret', 'set', name, '--env', ENVIRONMENT, '--repo', REPOSITORY, stdin=value)


def save_backup(keystore_b64, password):
    """Encrypted for this Windows user with DPAPI, the same way as the IONOS key."""
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    document = json.dumps({'alias': ALIAS, 'keystoreBase64': keystore_b64, 'password': password})
    script = ("$v=[Console]::In.ReadToEnd();$s=ConvertTo-SecureString $v -AsPlainText -Force;"
              "New-Object Management.Automation.PSCredential('{}',$s)|Export-Clixml -LiteralPath '{}';"
              "$r=(Import-Clixml -LiteralPath '{}').GetNetworkCredential().Password;"
              "if($r -ceq $v){{'match'}}else{{'differs'}}").format(ALIAS, BACKUP, BACKUP)
    done = subprocess.run(['powershell', '-NoProfile', '-Command', script], input=document, capture_output=True, text=True, encoding='utf8')
    if done.stdout.strip() != 'match':
        raise RuntimeError('The local encrypted copy could not be verified')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    if PIN.exists() or BACKUP.exists():
        print('A signing identity already exists. A new key would stop every future in-place update, so nothing was done.', file=sys.stderr)
        return 3
    keystore, password, der, certificate = make_identity()
    encoded = base64.b64encode(keystore).decode()
    save_backup(encoded, password)
    prepare_environment()
    store_secret('ATTUNE_ANDROID_KEYSTORE_B64', encoded)
    store_secret('ATTUNE_ANDROID_KEYSTORE_PASSWORD', password)
    PIN.parent.mkdir(parents=True, exist_ok=True)
    PIN.write_text(json.dumps({
        'purpose': 'Public fingerprint of the certificate that signs the cloudDemo APK. Not a secret. The key itself is never in this repository.',
        'sha256': hashlib.sha256(der).hexdigest(), 'alias': ALIAS, 'subject': certificate.subject.rfc4514_string(), 'notAfter': certificate.not_valid_after_utc.date().isoformat(),
        'createdOn': dt.datetime.now(dt.timezone.utc).date().isoformat(), 'githubEnvironment': ENVIRONMENT}, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'sha256': hashlib.sha256(der).hexdigest(), 'environment': ENVIRONMENT, 'localCopy': str(BACKUP)}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
