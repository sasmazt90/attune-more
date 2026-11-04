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


def test_tool_and_its_state_live_outside_appdata():
    # Writes under AppData from a packaged app go to a private copy, which left the shortcuts pointing at nothing.
    install = (WINDOWS / 'Install-AttuneShortcuts.ps1').read_text(encoding='utf8')
    assert "$bin = Join-Path $env:USERPROFILE 'AttuneMore\\bin'" in install
    assert "$DataRoot = Join-Path $env:USERPROFILE 'AttuneMore'" in (WINDOWS / 'AttuneControl.ps1').read_text(encoding='utf8')
    domain = (WINDOWS / 'AttuneDomain.ps1').read_text(encoding='utf8')
    assert "$script:DomainDataRoot = Join-Path $env:USERPROFILE 'AttuneMore'" in domain
    assert domain.count('$env:LOCALAPPDATA') == 1, 'only the owner-saved IONOS key is read from AppData'


def test_shortcuts_cover_start_stop_status():
    source = (WINDOWS / 'Install-AttuneShortcuts.ps1').read_text(encoding='utf8')
    for name, action in [('START ATTUNE.MORE', 'Start'), ('STOP ATTUNE.MORE', 'Stop'), ('STATUS ATTUNE.MORE', 'Status')]:
        assert name in source and '-Action ' + action in source


@pytest.mark.skipif(not shutil.which('powershell'), reason='Windows PowerShell only')
@pytest.mark.parametrize('script', ['AttuneControl.ps1', 'AttuneDomain.ps1', 'Setup-AttuneOperator.ps1', 'Install-AttuneShortcuts.ps1'])
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


def provider_with(monkeypatch, tmp_path, outputs):
    secret = 'sk-' + 'x' * 40
    (tmp_path / 'provider.env').write_text('OPENAI_API_KEY={}\n'.format(secret))
    (tmp_path / 'provider.env').chmod(0o600)
    monkeypatch.setattr(host_ready, 'ENV_ROOT', tmp_path)
    monkeypatch.setattr(host_ready, 'http_json', lambda *a, **k: {'isLiveLLM': True, 'apiKeyConfigured': True, 'providerName': 'openai'})
    replies = iter(outputs)

    class Done:
        def __init__(self):
            self.stdout = next(replies)

    monkeypatch.setattr(host_ready.subprocess, 'run', lambda *a, **k: Done())
    report = host_ready.Report('web')
    host_ready.check_provider(report)
    return report, secret


def test_listing_models_does_not_hide_an_empty_account(monkeypatch, tmp_path):
    body = json.dumps({'error': {'code': 'credit_balance_exhausted', 'type': 'insufficient_quota', 'message': 'private text'}})
    report, secret = provider_with(monkeypatch, tmp_path, ['200', body + '\n429'])
    assert 'provider-credit' in report.payload()['failedRequired']
    text = json.dumps(report.payload())
    assert secret not in text and 'private text' not in text


def test_a_real_call_confirms_credit(monkeypatch, tmp_path):
    report, _ = provider_with(monkeypatch, tmp_path, ['200', '{}\n200'])
    assert 'provider-credit' not in report.payload()['failedRequired']
    assert any(c['id'] == 'provider-credit' and c['status'] == 'PASS' for c in report.checks)


def test_a_rate_limit_is_not_called_an_empty_account(monkeypatch, tmp_path):
    report, _ = provider_with(monkeypatch, tmp_path, ['200', json.dumps({'error': {'code': 'rate_limit_exceeded'}}) + '\n429'])
    assert 'provider-credit' not in report.payload()['failedRequired']
    assert any(c['id'] == 'provider-credit' and c['status'] == 'WARN' for c in report.checks)


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


def test_restart_config_uses_hostnames_never_public_addresses():
    import stable_host
    text = json.dumps(stable_host.ORIGINS)
    assert not re.search(r'\d+\.\d+\.\d+\.\d+', text)
    assert stable_host.ORIGINS['web']['api-web.env']['ATTUNE_TRUSTED_ORIGINS'] == 'https://attunemore.sasmaz.digital'
    assert stable_host.ORIGINS['web']['capture.env']['ATTUNE_CAPTURE_SENDER_ORIGIN'] == 'https://aaos.attunemore.sasmaz.digital'
    assert stable_host.ORIGINS['aaos']['aaos.env']['ATTUNE_AUDIO_ORIGIN'] == 'https://aaos.attunemore.sasmaz.digital'


def test_env_update_replaces_only_named_keys_and_keeps_secrets():
    import stable_host
    old = 'PORT=8000\nOPENAI_API_KEY=keep-me\nATTUNE_TRUSTED_ORIGINS=https://18.153.100.39\n# note\n'
    new = stable_host.updated_env(old, {'ATTUNE_TRUSTED_ORIGINS': 'https://attunemore.sasmaz.digital'})
    assert new == 'PORT=8000\nOPENAI_API_KEY=keep-me\nATTUNE_TRUSTED_ORIGINS=https://attunemore.sasmaz.digital\n# note\n'
    assert stable_host.updated_env(new, {'ATTUNE_TRUSTED_ORIGINS': 'https://attunemore.sasmaz.digital'}) == new
    assert 'NEW=1' in stable_host.updated_env('PORT=1\n', {'NEW': '1'})


@pytest.mark.skipif(not shutil.which('openssl'), reason='openssl required')
def test_issued_chain_is_long_lived_constrained_and_destroys_the_ca_key(tmp_path):
    import stable_host

    def run(*args, cwd=None):
        return subprocess.run(['openssl', *args], capture_output=True, text=True, cwd=cwd, check=True).stdout

    requests = {}
    for name, leaf in stable_host.LEAVES.items():
        run('genpkey', '-algorithm', 'EC', '-pkeyopt', 'ec_paramgen_curve:P-256', '-out', str(tmp_path / (name + '.key')))
        requests[name] = run('req', '-new', '-key', str(tmp_path / (name + '.key')), '-subj', '/CN=' + leaf['dns'])
    workspace = tmp_path / 'tmpfs'
    workspace.mkdir()
    bundle = stable_host.sign_all(requests, workspace=str(workspace))
    assert list(workspace.iterdir()) == []
    assert 'PRIVATE KEY' not in json.dumps(bundle)
    (tmp_path / 'ca.crt').write_text(bundle['ca'])
    constraints = run('x509', '-in', str(tmp_path / 'ca.crt'), '-noout', '-ext', 'nameConstraints')
    assert 'attune-internal' in constraints and 'attune-aaos-client' in constraints
    assert 'sasmaz.digital' not in constraints, 'public names use the public CA'
    for name, leaf in stable_host.LEAVES.items():
        path = tmp_path / (name + '.crt')
        path.write_text(bundle['certificates'][name])
        purpose = 'sslclient' if leaf['usage'] == 'clientAuth' else 'sslserver'
        run('verify', '-CAfile', str(tmp_path / 'ca.crt'), '-purpose', purpose, str(path))
        run('x509', '-in', str(path), '-noout', '-checkend', str(365 * 2 * 86400))
        assert leaf['dns'] in run('x509', '-in', str(path), '-noout', '-ext', 'subjectAltName')
        assert not re.search(r'IP Address', run('x509', '-in', str(path), '-noout', '-ext', 'subjectAltName'))
    with pytest.raises(ValueError):
        stable_host.sign_all({'internal': requests['internal']}, workspace=str(workspace))


def public_chain(tmp_path, name, key='web.key', days=90):
    def run(*args):
        return subprocess.run(['openssl', *args], capture_output=True, text=True, check=True, cwd=tmp_path).stdout
    if not (tmp_path / key).exists():
        run('genpkey', '-algorithm', 'EC', '-pkeyopt', 'ec_paramgen_curve:P-256', '-out', key)
    return run('req', '-new', '-x509', '-key', key, '-days', str(days), '-subj', '/CN=' + name, '-addext', 'subjectAltName=DNS:' + name)


@pytest.mark.skipif(not shutil.which('openssl'), reason='openssl required')
def test_public_certificate_state_asks_for_renewal_only_when_needed(tmp_path, monkeypatch):
    import datetime as dt
    import stable_host
    (tmp_path / 'web.crt').write_text(public_chain(tmp_path, stable_host.WEB_DOMAIN))
    monkeypatch.setattr(stable_host, 'publicly_trusted', lambda path: True)
    fresh = stable_host.public_state('web', tmp_path)
    assert fresh['needsCertificate'] is False and fresh['names'] == [stable_host.WEB_DOMAIN]
    late = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=70)
    assert stable_host.public_state('web', tmp_path, now=late)['needsCertificate'] is True, 'last third of the lifetime'
    monkeypatch.setattr(stable_host, 'publicly_trusted', lambda path: False)
    assert stable_host.public_state('web', tmp_path)['needsCertificate'] is True, 'the private CA is not enough'
    monkeypatch.setattr(stable_host, 'publicly_trusted', lambda path: True)
    (tmp_path / 'web.crt').write_text(public_chain(tmp_path, 'attune.sasmaz.digital'))
    assert stable_host.public_state('web', tmp_path)['needsCertificate'] is True, 'old name'


@pytest.mark.skipif(not shutil.which('openssl'), reason='openssl required')
def test_public_certificate_install_refuses_a_wrong_key_or_name(tmp_path, monkeypatch):
    import stable_host
    other = tmp_path / 'other'
    other.mkdir()
    wrong_key = public_chain(other, stable_host.WEB_DOMAIN)
    public_chain(tmp_path, stable_host.WEB_DOMAIN)
    with pytest.raises(ValueError, match='does not match the key'):
        stable_host.install_public('web', wrong_key, tmp_path, check_trust=False)
    with pytest.raises(ValueError, match='not for'):
        stable_host.install_public('web', public_chain(tmp_path, 'www.sasmaz.digital'), tmp_path, check_trust=False)
    with pytest.raises(ValueError, match='public root'):
        monkeypatch.setattr(stable_host, 'publicly_trusted', lambda path: False)
        stable_host.install_public('web', public_chain(tmp_path, stable_host.WEB_DOMAIN), tmp_path)
    assert not (tmp_path / 'web.crt').exists()


def test_control_uses_real_dns_and_no_certificate_bypass():
    source = (WINDOWS / 'AttuneControl.ps1').read_text(encoding='utf8')
    assert '--resolve' not in source and 'host-resolver-rules' not in source and '-sk' not in source
    assert "$WebDomain = 'attunemore.sasmaz.digital'" in source and "$AaosDomain = 'aaos.attunemore.sasmaz.digital'" in source
    assert 'attune.sasmaz.digital' not in source and "'aaos.sasmaz.digital'" not in source


def test_only_the_authorized_names_can_be_written():
    source = (WINDOWS / 'AttuneDomain.ps1').read_text(encoding='utf8')
    assert "$script:DnsNames = @('attunemore.sasmaz.digital', 'aaos.attunemore.sasmaz.digital')" in source
    assert source.count("-notin $script:DnsNames") == 3
    # Accepting a CA's terms is the user's step, so no switch may do it unattended.
    control = (WINDOWS / 'AttuneControl.ps1').read_text(encoding='utf8')
    assert control.count('Register-AcmeAccount') == 1 and "Read-Host 'Do you accept these terms?" in control


def test_release_copy_never_nests_a_folder_inside_itself():
    import deploy_host
    assert deploy_host.tree_copy('/tmp/src/infra/aws/aaos', '/opt/attune/infra/aws/aaos') == ['rsync', '-a', '/tmp/src/infra/aws/aaos/', '/opt/attune/infra/aws/aaos/']
    assert deploy_host.tree_copy('/tmp/src/scripts/aws/', '/opt/attune/scripts/aws/')[2:] == ['/tmp/src/scripts/aws/', '/opt/attune/scripts/aws/']


def test_release_requires_an_exact_commit():
    import deploy_host
    assert deploy_host.valid_commit('a' * 40) == 'a' * 40
    for bad in ('main', 'a9b7919', '', None, 'a' * 39 + 'G'):
        with pytest.raises(ValueError):
            deploy_host.valid_commit(bad)
