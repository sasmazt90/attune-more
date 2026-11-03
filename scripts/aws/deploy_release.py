#!/usr/bin/env python3
"""Deploys one pushed commit to both running hosts through SSM and records provenance."""
import argparse
import base64
import gzip
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', default='attune-claude')
    parser.add_argument('--commit', required=True, help='Full commit SHA, already pushed to GitHub')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = {'commit': args.commit, 'hosts': [deploy(args.profile, role, args.commit) for role in ('web', 'aaos')]}
    text = json.dumps(report, indent=2)
    print(text)
    if args.output:
        args.output.write_text(text + '\n', encoding='utf8')
    return 0


if __name__ == '__main__':
    sys.exit(main())
