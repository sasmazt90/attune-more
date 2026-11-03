"""Desktop control and host readiness contracts. No AWS call or paid action."""
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/aws'))
from targets import REGION, TARGETS
import host_ready

WINDOWS = ROOT / 'scripts/aws/windows'
IAM = ROOT / 'infra/aws/iam'
ACCOUNT = '798886013428'
INSTANCE_ARNS = {'arn:aws:ec2:{}:{}:instance/{}'.format(REGION, ACCOUNT, key) for key in TARGETS}


def statements(name):
    return {s['Sid']: s for s in json.loads((IAM / name).read_text())['Statement']}


@pytest.mark.parametrize('policy', ['attune-ops-control.json', 'attune-ops-verifier.json'])
def test_roles_only_touch_the_two_existing_instances(policy):
    rules = statements(policy)
    assert set(rules['StartAndStopTheTwoExistingInstancesOnly']['Resource']) == INSTANCE_ARNS
    send = set(rules['RunShellCommandsOnTheTwoExistingInstancesOnly']['Resource'])
    assert send == INSTANCE_ARNS | {'arn:aws:ssm:{}::document/AWS-RunShellScript'.format(REGION)}
    granted = {a for rule in rules.values() for a in ([rule['Action']] if isinstance(rule['Action'], str) else rule['Action'])}
    for forbidden in ['ec2:RunInstances', 'ec2:TerminateInstances', 'ec2:AllocateAddress', 'iam:*', 'ssm:GetParameter', 'secretsmanager:GetSecretValue']:
        assert forbidden not in granted
    assert all(rule['Effect'] == 'Allow' for rule in rules.values())
    assert not any(rule['Resource'] == '*' and any(a.startswith('ec2:') and not a.startswith('ec2:Describe') for a in ([rule['Action']] if isinstance(rule['Action'], str) else rule['Action'])) for rule in rules.values())


def test_only_control_role_may_edit_security_groups():
    assert 'UpdateHttpsSourceIpOnTheTwoExistingSecurityGroupsOnly' in statements('attune-ops-control.json')
    verifier = json.loads((IAM / 'attune-ops-verifier.json').read_text())
    assert 'SecurityGroupIngress' not in json.dumps(verifier)


def test_setup_creates_no_access_keys_and_prompts_for_password_privately():
    source = (WINDOWS / 'Setup-AttuneOperator.ps1').read_text(encoding='utf8')
    assert 'create-access-key' not in source
    assert '-AsSecureString' in source
    assert 'Password = $plain' in source and '--password' not in source
    assert 'no-new-infrastructure.json' in source


def test_control_targets_match_recorded_instances():
    source = (WINDOWS / 'AttuneControl.ps1').read_text(encoding='utf8')
    for key, target in TARGETS.items():
        assert re.search(r"Id = '{}'; Name = '{}'; Type = '{}'".format(key, target['name'], target['type']), source)
        assert host_ready.TARGETS[target['role']] == {'id': key, 'type': target['type']}
    assert "$Region = '{}'".format(REGION) in source and host_ready.REGION == REGION


def test_control_never_forces_stop_or_runs_as_root():
    source = (WINDOWS / 'AttuneControl.ps1').read_text(encoding='utf8')
    assert '--force' not in source and '--hibernate' not in source
    assert 'terminate-instances' not in source and 'run-instances' not in source
    assert "Arn -match ':root$'" in source


def test_shortcuts_cover_start_stop_status():
    source = (WINDOWS / 'Install-AttuneShortcuts.ps1').read_text(encoding='utf8')
    for name, action in [('START ATTUNE.MORE', 'Start'), ('STOP ATTUNE.MORE', 'Stop'), ('STATUS ATTUNE.MORE', 'Status')]:
        assert name in source and '-Action ' + action in source


@pytest.mark.skipif(not shutil.which('powershell'), reason='Windows PowerShell only')
@pytest.mark.parametrize('script', ['AttuneControl.ps1', 'Setup-AttuneOperator.ps1', 'Install-AttuneShortcuts.ps1'])
def test_powershell_scripts_parse(script):
    command = "$e=$null;$t=$null;[void][System.Management.Automation.Language.Parser]::ParseFile('{}',[ref]$t,[ref]$e);$e.Count".format(WINDOWS / script)
    result = subprocess.run(['powershell', '-NoProfile', '-Command', command], capture_output=True, text=True)
    assert result.stdout.strip() == '0', result.stdout + result.stderr


def test_report_is_ready_only_when_every_required_check_passes():
    report = host_ready.Report('web')
    report.add('a', 'A', True)
    report.add('optional', 'Optional', False, required=False)
    report.warn('renewal', 'Renewal soon')
    assert report.payload()['ready'] is True
    report.add('b', 'B', False, 'x' * 1000)
    payload = report.payload()
    assert payload['ready'] is False and payload['failedRequired'] == ['b']
    assert len(payload['checks'][-1]['detail']) == 300


def test_read_env_parses_only_assignments(tmp_path):
    path = tmp_path / 'env'
    path.write_text('# comment\nWEB_PRIVATE_IP=172.31.11.240\nQUOTED="value"\nbad line\n')
    assert host_ready.read_env(path) == {'WEB_PRIVATE_IP': '172.31.11.240', 'QUOTED': 'value'}
    assert host_ready.read_env(tmp_path / 'missing') == {}


def test_provider_check_never_reports_key_material(monkeypatch, tmp_path):
    secret = 'sk-' + 'x' * 40
    (tmp_path / 'provider.env').write_text('OPENAI_API_KEY={}\n'.format(secret))
    (tmp_path / 'provider.env').chmod(0o600)
    monkeypatch.setattr(host_ready, 'ENV_ROOT', tmp_path)
    monkeypatch.setattr(host_ready, 'http_json', lambda *a, **k: {'isLiveLLM': True, 'apiKeyConfigured': True, 'providerName': 'openai'})

    class Done:
        stdout = '200'

    monkeypatch.setattr(host_ready.subprocess, 'run', lambda *a, **k: Done())
    report = host_ready.Report('web')
    host_ready.check_provider(report)
    assert secret not in json.dumps(report.payload())
    assert any(c['id'] == 'provider-auth' and c['status'] == 'PASS' for c in report.checks)


def test_expired_certificate_blocks_readiness(monkeypatch, tmp_path):
    (tmp_path / 'web.crt').write_text('x')
    monkeypatch.setattr(host_ready, 'TLS_ROOT', tmp_path)
    monkeypatch.setattr(host_ready, 'run', lambda *a, **k: (0, 'notAfter=Nov  5 19:00:00 2020 GMT', ''))
    report = host_ready.Report('web')
    host_ready.check_certificates(report)
    assert report.payload()['failedRequired'] == ['tls-valid']


def test_certificate_close_to_expiry_warns_without_blocking(monkeypatch, tmp_path):
    (tmp_path / 'web.crt').write_text('x')
    soon = host_ready.dt.datetime.now(host_ready.dt.timezone.utc) + host_ready.dt.timedelta(days=2)
    monkeypatch.setattr(host_ready, 'TLS_ROOT', tmp_path)
    monkeypatch.setattr(host_ready, 'run', lambda *a, **k: (0, 'notAfter=' + soon.strftime('%b %d %H:%M:%S %Y GMT'), ''))
    report = host_ready.Report('web')
    host_ready.check_certificates(report)
    payload = report.payload()
    assert payload['ready'] is True and any(c['id'] == 'tls-renewal' for c in payload['checks'])
