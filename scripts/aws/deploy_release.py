#!/usr/bin/env python3
"""Deploys one pushed commit to both running hosts through SSM and records provenance."""
import argparse
import base64
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from apk_identity import pinned_identity, signing_identity
from targets import REGION, TARGETS

ROLE_ID = {target['role']: key for key, target in TARGETS.items()}
SCRIPT = Path(__file__).with_name('deploy_host.py')
ENV = {**os.environ, 'PYTHONUTF8': '1', 'AWS_PAGER': ''}


def aws(profile, *args):
    done = subprocess.run(['aws', *args, '--profile', profile, '--region', REGION, '--output', 'json'],
                          capture_output=True, text=True, encoding='utf8', env=ENV)
    if done.returncode != 0:
        raise RuntimeError(done.stderr.strip()[:400])
    return json.loads(done.stdout) if done.stdout.strip() else None


def host_commands(role, commit):
    encoded = base64.b64encode(gzip.compress(SCRIPT.read_bytes())).decode()
    commands = ['set -e', 'work=$(mktemp -d /run/attune-deploy.XXXXXX)', "trap 'rm -rf \"$work\"' EXIT"]
    commands += ["printf %s '{}' >> \"$work/s.b64\"".format(encoded[i:i + 3000]) for i in range(0, len(encoded), 3000)]
    commands.append('base64 -d "$work/s.b64" | gunzip > "$work/deploy_host.py"')
    commands.append('python3 "$work/deploy_host.py" --role {} --commit {}'.format(role, commit))
    return commands


def deploy(profile, role, commit, timeout=1800):
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf8') as parameters:
        json.dump({'commands': host_commands(role, commit)}, parameters)
    try:
        sent = aws(profile, 'ssm', 'send-command', '--instance-ids', ROLE_ID[role], '--document-name', 'AWS-RunShellScript',
                   '--comment', 'Attune release ' + commit[:12], '--timeout-seconds', str(timeout),
                   '--parameters', 'file://' + parameters.name.replace('\\', '/'))
    finally:
        os.unlink(parameters.name)
    command = sent['Command']['CommandId']
    deadline = time.monotonic() + timeout + 30
    while time.monotonic() < deadline:
        time.sleep(10)
        try:
            result = aws(profile, 'ssm', 'get-command-invocation', '--command-id', command, '--instance-id', ROLE_ID[role])
        except RuntimeError:
            continue
        if result['Status'] not in ('Pending', 'InProgress', 'Delayed'):
            if result['Status'] != 'Success':
                raise RuntimeError('Deploy on {}: {} {}'.format(role, result['Status'], result['StandardErrorContent'][-500:]))
            report = json.loads(result['StandardOutputContent'])
            report['ssmCommandId'] = command
            return report
    raise RuntimeError('Deploy on {} timed out'.format(role))


def run_commands(profile, commands, comment, timeout=300):
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf8') as parameters:
        json.dump({'commands': commands}, parameters)
    try:
        sent = aws(profile, 'ssm', 'send-command', '--instance-ids', ROLE_ID['aaos'], '--document-name', 'AWS-RunShellScript', '--comment', comment,
                   '--timeout-seconds', str(timeout), '--parameters', 'file://' + parameters.name.replace('\\', '/'))
    finally:
        os.unlink(parameters.name)
    command = sent['Command']['CommandId']
    deadline = time.monotonic() + timeout + 30
    while time.monotonic() < deadline:
        time.sleep(2)
        try:
            result = aws(profile, 'ssm', 'get-command-invocation', '--command-id', command, '--instance-id', ROLE_ID['aaos'])
        except RuntimeError:
            continue
        if result['Status'] not in ('Pending', 'InProgress', 'Delayed'):
            if result['Status'] != 'Success':
                raise RuntimeError('{}: {} {}'.format(comment, result['Status'], result['StandardErrorContent'][-1500:]))
            return result['StandardOutputContent']
    raise RuntimeError(comment + ' timed out')


def check_apk_identity(path):
    """Stops before anything is deployed if this APK is not signed by the pinned identity."""
    found, expected = signing_identity(path), pinned_identity(SCRIPT.parents[2])
    if found != expected:
        raise SystemExit('APK_NOT_PINNED_IDENTITY: {} is signed by {}, and the pinned identity is {}. Nothing was deployed.'.format(path, found, expected))
    return expected


def install_apk(profile, path, migrate_signing=False):
    """Updates the app in place on the emulator, which keeps its data. The steps and refusals are in apk_upgrade_host.py."""
    expected = check_apk_identity(path)
    data = Path(path).read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    encoded = base64.b64encode(data).decode()
    work = '/opt/attune-staging/app-cloudDemo.incoming.apk'
    run_commands(profile, [': > {}.b64'.format(work)], 'Attune APK upload')
    for start in range(0, len(encoded), 30000):
        run_commands(profile, ["printf %s '{}' >> {}.b64".format(encoded[start:start + 30000], work)], 'Attune APK upload')
    flag = ' --migrate-signing' if migrate_signing else ''
    output = run_commands(profile, [
        'set -e', 'base64 -d {0}.b64 > {0}'.format(work), 'rm -f {}.b64'.format(work),
        'test "$(sha256sum {} | cut -d" " -f1)" = "{}"'.format(work, digest),
        'python3 /opt/attune/scripts/aws/apk_upgrade_host.py --incoming {} --expected-cert {}{}'.format(work, expected, flag),
    ], 'Attune APK install', timeout=900)
    return {'apkSha256': digest, 'bytes': len(data), 'certificate': expected, 'upgrade': json.loads(output.strip().splitlines()[-1])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apk', help='Also update the cloudDemo app on the AAOS host, in place. Build it from the same commit.')
    parser.add_argument('--migrate-signing-once', action='store_true', help='One time only: move an app signed by an old key to the pinned one, keeping its data.')
    parser.add_argument('--profile', default='attune-claude')
    parser.add_argument('--commit', required=True, help='Full commit SHA, already pushed to GitHub')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.apk:
        check_apk_identity(args.apk)
    report = {'commit': args.commit, 'hosts': [deploy(args.profile, role, args.commit) for role in ('web', 'aaos')]}
    if args.apk:
        report['apk'] = install_apk(args.profile, args.apk, args.migrate_signing_once)
    text = json.dumps(report, indent=2)
    print(text)
    if args.output:
        args.output.write_text(text + '\n', encoding='utf8')
    return 0


if __name__ == '__main__':
    sys.exit(main())
