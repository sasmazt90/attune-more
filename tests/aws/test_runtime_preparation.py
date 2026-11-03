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
