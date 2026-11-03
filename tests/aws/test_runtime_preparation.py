import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('audit_host_config', ROOT / 'scripts/aws/audit_host_config.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def test_audit_reports_mismatch_without_disclosing_secrets(tmp_path):
    secret = 'private-provider-key-never-log'
    a, b = 'a' * 48, 'b' * 48
    for name, token in [('api-web', a), ('web-web', a), ('api-aaos', b), ('web-aaos', a)]:
        (tmp_path / (name + '.env')).write_text(
            f'OPENAI_API_KEY="{secret}"\nATTUNE_MENTAL_TTS_TOKEN={token}\nATTUNE_CLOUD_ASR_ENABLED=1\n')
    result = audit.audit(tmp_path)
    assert result['ttsPairMatches'] == {'web': True, 'aaos': False}
    assert result['ttsRuntimeTokensDistinct'] is True
    assert all(s not in json.dumps(result) for s in [secret, a, b])


def test_missing_and_linked_secret_files_are_not_present(tmp_path):
    other = tmp_path / 'other.env'
    other.write_text('OPENAI_API_KEY=secret\n')
    (tmp_path / 'api-web.env').symlink_to(other)
    result = audit.audit(tmp_path)
    assert not result['files'][0]['present']['OPENAI_API_KEY']
    assert result['ttsPairMatches'] == {'web': False, 'aaos': False}
    assert not result['ttsRuntimeTokensDistinct']


def test_shared_provider_file_is_audited_without_disclosing_value(tmp_path):
    for name in ('api-web', 'api-aaos'):
        (tmp_path / (name + '.env')).write_text('ATTUNE_CLOUD_ASR_ENABLED=1\n')
    secret = 'provider-secret-value-never-report'
    provider = tmp_path / 'provider.env'
    provider.write_text('OPENAI_API_KEY="' + secret + '"\n')
    provider.chmod(0o600)
    result = audit.audit(tmp_path)
    assert result['providerFile']['present']
    assert all(row['present']['OPENAI_API_KEY'] for row in result['files'][:2])
    assert secret not in json.dumps(result)
    provider.unlink()
    other = tmp_path / 'other.env'
    other.write_text('OPENAI_API_KEY=' + secret)
    provider.symlink_to(other)
    result = audit.audit(tmp_path)
    assert not result['providerFile']['present']
    assert not any(row['present']['OPENAI_API_KEY'] for row in result['files'][:2])


def test_provider_prompt_rejects_repeated_paste_without_writing(tmp_path, monkeypatch, capsys):
    import io
    import pytest
    spec = importlib.util.spec_from_file_location('configure_provider_secret', ROOT / 'scripts/aws/configure_provider_secret.py')
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    monkeypatch.setattr(helper.os, 'geteuid', lambda: 0)
    monkeypatch.setattr(helper.sys, 'argv', ['configure_provider_secret.py', '--replace'])
    terminal = io.StringIO()
    monkeypatch.setattr(terminal, 'isatty', lambda: True)
    monkeypatch.setattr(helper.sys, 'stdin', terminal)
    monkeypatch.setattr(helper.subprocess, 'run', lambda *args, **kwargs: None)
    monkeypatch.setattr(helper, 'Path', lambda value: tmp_path if value == '/etc/attune' else Path(value))
    repeated = 'sk-test-onlysk-test-only'
    monkeypatch.setattr(helper.getpass, 'getpass', lambda *args: repeated)
    with pytest.raises(SystemExit, match='Repeated key prefix') as error:
        helper.main()
    assert not (tmp_path / 'provider.env').exists()
    assert repeated not in str(error.value) + capsys.readouterr().out
