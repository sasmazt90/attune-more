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
                raise RuntimeError('{}: {} {}'.format(comment, result['Status'], result['StandardErrorContent'][-400:]))
            return result['StandardOutputContent']
    raise RuntimeError(comment + ' timed out')


def install_apk(profile, path):
    """Replaces the APK that run.sh installs on every boot. CI's debug key differs per build, so
    Android refuses an update in place: uninstall once, which also clears the microphone grant."""
    data = Path(path).read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    encoded = base64.b64encode(data).decode()
    work = '/opt/attune-staging/app-cloudDemo.apk.incoming'
    run_commands(profile, [': > {}.b64'.format(work)], 'Attune APK upload')
    for start in range(0, len(encoded), 30000):
        run_commands(profile, ["printf %s '{}' >> {}.b64".format(encoded[start:start + 30000], work)], 'Attune APK upload')
    adb = '/opt/android-sdk/platform-tools/adb -s emulator-5554'
    package = 'more.attune.automotive.prototype.clouddemo'
    output = run_commands(profile, [
        'set -e', 'base64 -d {0}.b64 > {0}'.format(work), 'rm -f {}.b64'.format(work),
        'test "$(sha256sum {} | cut -d" " -f1)" = "{}"'.format(work, digest),
        'cp -p /opt/attune-staging/app-cloudDemo.apk /opt/attune-staging/app-cloudDemo.apk.previous',
        'chown --reference=/opt/attune-staging/app-cloudDemo.apk {}'.format(work),
        'chmod --reference=/opt/attune-staging/app-cloudDemo.apk {}'.format(work),
        'mv {} /opt/attune-staging/app-cloudDemo.apk'.format(work),
        '{} uninstall {} </dev/null || true'.format(adb, package),
        '{} install -r /opt/attune-staging/app-cloudDemo.apk </dev/null'.format(adb),
        'for user in 0 10; do {0} shell pm grant --user $user {1} android.permission.RECORD_AUDIO </dev/null || true; done'.format(adb, package),
        '{} shell am start -n {}/more.attune.automotive.MainActivity </dev/null'.format(adb, package),
        'sha256sum /opt/attune-staging/app-cloudDemo.apk',
    ], 'Attune APK install')
    return {'apkSha256': digest, 'bytes': len(data), 'hostOutput': output[-300:]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apk', help='Also install this cloudDemo APK on the AAOS host. Build it from the same commit.')
    parser.add_argument('--profile', default='attune-claude')
    parser.add_argument('--commit', required=True, help='Full commit SHA, already pushed to GitHub')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = {'commit': args.commit, 'hosts': [deploy(args.profile, role, args.commit) for role in ('web', 'aaos')]}
    if args.apk:
        report['apk'] = install_apk(args.profile, args.apk)
    text = json.dumps(report, indent=2)
    print(text)
    if args.output:
        args.output.write_text(text + '\n', encoding='utf8')
    return 0


if __name__ == '__main__':
    sys.exit(main())
