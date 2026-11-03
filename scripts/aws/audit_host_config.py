#!/usr/bin/env python3
"""Run via SSM after approved boot. Report configuration presence, never values."""
import argparse
import json
from pathlib import Path
import re
import stat


def audit(root):
    rows = []
    required = {
        'api-web.env': ['OPENAI_API_KEY', 'ATTUNE_CLOUD_ASR_ENABLED', 'ATTUNE_TRUSTED_ORIGINS',
                        'ATTUNE_MENTAL_TTS_CONFIG', 'ATTUNE_MENTAL_TTS_FEMALE_CONFIG', 'ATTUNE_MENTAL_TTS_PYTHON', 'ATTUNE_MENTAL_TTS_TOKEN'],
        'api-aaos.env': ['OPENAI_API_KEY', 'ATTUNE_CLOUD_ASR_ENABLED', 'ATTUNE_TRUSTED_ORIGINS',
                         'ATTUNE_MENTAL_TTS_CONFIG', 'ATTUNE_MENTAL_TTS_FEMALE_CONFIG', 'ATTUNE_MENTAL_TTS_PYTHON', 'ATTUNE_MENTAL_TTS_TOKEN'],
        'web-web.env': ['ATTUNE_MENTAL_TTS_TOKEN', 'ATTUNE_MENTAL_TTS_BACKEND_URL', 'ATTUNE_MENTAL_TTS_FRONTEND_ORIGIN'],
        'web-aaos.env': ['ATTUNE_MENTAL_TTS_TOKEN', 'ATTUNE_MENTAL_TTS_BACKEND_URL', 'ATTUNE_MENTAL_TTS_FRONTEND_ORIGIN'],
    }
    provider = root / 'provider.env'
    provider_values = {}
    provider_secure = False
    if provider.is_file() and not provider.is_symlink():
        for line in provider.read_text().splitlines():
            match = re.fullmatch(r'\s*([A-Z][A-Z0-9_]*)=(.*)', line)
            if match:
                provider_values[match[1]] = match[2].strip().strip('\"\'')
        provider_secure = provider.stat().st_uid == 0 and stat.S_IMODE(provider.stat().st_mode) == 0o600
    parsed = {}
    for name, keys in required.items():
        path = root / name
        values = {}
        if path.is_file() and not path.is_symlink():
            for line in path.read_text().splitlines():
                match = re.fullmatch(r'\s*([A-Z][A-Z0-9_]*)=(.*)', line)
                if match:
                    values[match[1]] = match[2].strip().strip('\"\'')
            secure = path.stat().st_uid == 0 and stat.S_IMODE(path.stat().st_mode) == 0o600
        else:
            secure = False
        if name.startswith('api-'):
            values.update(provider_values)
            if provider_values:
                secure = secure and provider_secure
        parsed[name] = values
        rows.append({'file': name, 'rootOwned0600': secure,
                     'present': {key: bool(values.get(key)) for key in keys},
                     'ttsTokenLengthOK': len(values.get('ATTUNE_MENTAL_TTS_TOKEN', '')) >= 32,
                     'cloudAsrEnabled': values.get('ATTUNE_CLOUD_ASR_ENABLED') == '1' if name.startswith('api-') else None})
    def token(name):
        return parsed[name].get('ATTUNE_MENTAL_TTS_TOKEN', '')
    pairs = {role: bool(token('api-' + role + '.env')) and token('api-' + role + '.env') == token('web-' + role + '.env')
             for role in ('web', 'aaos')}
    return {'providerFile': {'present': bool(provider_values), 'rootOwned0600': provider_secure},
            'files': rows, 'ttsPairMatches': pairs,
            'ttsRuntimeTokensDistinct': bool(token('api-web.env')) and bool(token('api-aaos.env')) and token('api-web.env') != token('api-aaos.env'),
            'providerAuthentication': 'NOT_TESTED', 'secretValuesLogged': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('/etc/attune'))
    args = parser.parse_args()
    print(json.dumps(audit(args.root), indent=2))
