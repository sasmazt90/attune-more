"""Stable controlled theme values; no translations of user-authored content."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / 'shared/localization'
VOCABULARY = json.loads((ROOT / 'mental-themes.json').read_text('utf-8'))
SESSION_THEME_KEYS = tuple(VOCABULARY['session'])
_messages = list(json.loads((ROOT / 'messages.json').read_text('utf-8')).values())
_aliases = {}
for raw in SESSION_THEME_KEYS:
    message = next((m for m in _messages if m['tr'] == raw), None)
    for label in [raw] + ([message['en'], message['de']] if message else []):
        _aliases[label.strip().casefold()] = raw

def stable_session_themes(values):
    if not isinstance(values, list) or any(not isinstance(v, str) or v.strip().casefold() not in _aliases for v in values):
        raise ValueError('INVALID_MENTAL_THEME_KEYS')
    return list(dict.fromkeys(_aliases[v.strip().casefold()] for v in values))
