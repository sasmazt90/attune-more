#!/usr/bin/env python3
"""Moves the two running hosts to hostname origins and long-lived certificates.

Run once from an operator PC with the AWS CLI. Sends stable_host.py through SSM.
Carries only certificate requests and public certificates; private keys stay on
their hosts and the CA key is destroyed when signing ends. Safe to repeat.
"""
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

from targets import IDS, REGION, TARGETS

ROLE_ID = {target['role']: key for key, target in TARGETS.items()}
SCRIPT = Path(__file__).with_name('stable_host.py')
ENV = {**os.environ, 'PYTHONUTF8': '1', 'AWS_PAGER': ''}


def aws(profile, *args):
    done = subprocess.run(['aws', *args, '--profile', profile, '--region', REGION, '--output', 'json'],
                          capture_output=True, text=True, encoding='utf8', env=ENV)
    if done.returncode != 0:
        raise RuntimeError(done.stderr.strip()[:400])
    return json.loads(done.stdout) if done.stdout.strip() else None


def host_commands(step, role=None, payload=None):
    encoded = base64.b64encode(gzip.compress(SCRIPT.read_bytes())).decode()
    commands = ['set -e', 'work=$(mktemp -d /run/attune-stable.XXXXXX)', "trap 'rm -rf \"$work\"' EXIT"]
    commands += ["printf %s '{}' >> \"$work/s.b64\"".format(encoded[i:i + 3000]) for i in range(0, len(encoded), 3000)]
    commands.append('base64 -d "$work/s.b64" | gunzip > "$work/stable_host.py"')
    call = 'python3 "$work/stable_host.py" {}'.format(step)
    if role:
        call += ' --role ' + role
    if payload is not None:
        data = base64.b64encode(json.dumps(payload).encode()).decode()
        commands += ["printf %s '{}' >> \"$work/p.b64\"".format(data[i:i + 3000]) for i in range(0, len(data), 3000)]
        call += ' --payload "$(cat "$work/p.b64")"'
    commands.append(call)
    return commands


def run_on_host(profile, role, step, payload=None, timeout=300):
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf8') as parameters:
        json.dump({'commands': host_commands(step, role, payload)}, parameters)
    try:
        sent = aws(profile, 'ssm', 'send-command', '--instance-ids', ROLE_ID[role], '--document-name', 'AWS-RunShellScript',
                   '--comment', 'Attune stable config: ' + step, '--timeout-seconds', str(timeout),
                   '--parameters', 'file://' + parameters.name.replace('\\', '/'))
    finally:
        os.unlink(parameters.name)
    command = sent['Command']['CommandId']
    deadline = time.monotonic() + timeout + 30
    while time.monotonic() < deadline:
        time.sleep(2)
        try:
            result = aws(profile, 'ssm', 'get-command-invocation', '--command-id', command, '--instance-id', ROLE_ID[role])
        except RuntimeError:
            continue
        if result['Status'] not in ('Pending', 'InProgress', 'Delayed'):
            if result['Status'] != 'Success':
                raise RuntimeError('{} on {}: {} {}'.format(step, role, result['Status'], result['StandardErrorContent'][:400]))
            return json.loads(result['StandardOutputContent'])
    raise RuntimeError('{} on {} timed out'.format(step, role))


def apply(profile, ca_output):
    states = aws(profile, 'ec2', 'describe-instances', '--instance-ids', *IDS)
    running = {i['InstanceId']: i['State']['Name'] for r in states['Reservations'] for i in r['Instances']}
    if set(running.values()) != {'running'}:
        raise SystemExit('Both instances must be running: {}'.format(running))
    report = {}
    for role in ('web', 'aaos'):
        report[role] = {'originsChanged': run_on_host(profile, role, 'origins')['changed']}
    requests = {}
    for role in ('web', 'aaos'):
        requests.update(run_on_host(profile, role, 'requests')['requests'])
    # sign_all runs on WEB in tmpfs and removes the CA key before returning.
    bundle = run_on_host(profile, 'web', 'sign', requests)
    for role in ('web', 'aaos'):
        report[role]['certificatesInstalled'] = run_on_host(profile, role, 'install', bundle)['installed']
    for role in ('web', 'aaos'):
        report[role]['restarted'] = run_on_host(profile, role, 'restart')['restarted']
    ca_output.parent.mkdir(parents=True, exist_ok=True)
    ca_output.write_text(bundle['ca'])
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', default='attune-claude')
    parser.add_argument('--ca-output', type=Path, default=Path.home() / 'AttuneMore' / 'attune-private-ca.crt')
    args = parser.parse_args()
    print(json.dumps(apply(args.profile, args.ca_output), indent=2))
    print('Public CA certificate saved to', args.ca_output, file=sys.stderr)


if __name__ == '__main__':
    main()
