"""Closing A/B/C bridge: committed assets, manifest contract and the real frontend closures (fixtures only)."""
import hashlib
import itertools
import json
from pathlib import Path
import re
import subprocess
import wave

import pytest

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / 'apps/vehicle-app/public'
MANIFEST = json.loads((PUBLIC / 'audio/mental/closing-abc/v1/manifest.json').read_text('utf-8'))
CATALOG = json.loads((ROOT / 'shared/mental/closing-abc/v1/catalog.json').read_text('utf-8'))
FEMALE = json.loads((PUBLIC / 'audio/mental/v1/female-calm-v1-manifest.json').read_text('utf-8'))
VOICE = json.loads((ROOT / 'shared/mental/voices/female-calm-v1.json').read_text('utf-8'))
SOURCE = json.loads((ROOT / 'shared/localization/chatterbox-v3-source.json').read_text('utf-8'))


@pytest.mark.parametrize('script', ['mental_closing_bridge_runtime.cjs', 'mental_closing_finish_runtime.cjs', 'vehicle_polling_runtime.cjs',
                                    'aaos_closing_stop_verdict_runtime.cjs'])
def test_closing_bridge_frontend_closures(script):
    result = subprocess.run(['node', 'tests/unit/' + script], cwd=ROOT, text=True, capture_output=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr


def test_forty_five_clips_five_per_language_and_group():
    entries = MANIFEST['entries']
    assert len(entries) == 45
    for language, group in itertools.product(('tr', 'en', 'de'), 'ABC'):
        rows = [e for e in entries if e['language'] == language and e['group'] == group]
        assert [e['variantId'] for e in rows] == [f'{group}{i}' for i in range(1, 6)]
        assert [e['fileName'] for e in rows] == [f'{language.upper()}_{group}{i}.wav' for i in range(1, 6)]
    assert MANIFEST['playbackOrder'] == ['A', 'B', 'C']


def test_exact_catalog_text_and_formal_german():
    texts = {r['assetId']: r['exactText'] for r in CATALOG['rows']}
    assert {e['assetId']: e['exactText'] for e in MANIFEST['entries']} == texts
    for e in MANIFEST['entries']:
        assert e['textSha256'] == hashlib.sha256(e['exactText'].encode()).hexdigest()
    german = ' '.join(e['exactText'] for e in MANIFEST['entries'] if e['language'] == 'de')
    assert not re.search(r'\b(du|dich|dir|dein\w*)\b', german, re.I)
    assert 'Sie' in german and 'Ihnen' in german
    # No claims that the conversation was productive or successful.
    assert not re.search(r'verimli|başarılı|productive|successful|erfolgreich|produktiv', ' '.join(texts.values()), re.I)


def test_same_approved_profile_reference_settings_and_pins():
    assert MANIFEST['speakerProfile'] == FEMALE['speakerProfile'] == VOICE['id'] == 'female-calm-v1'
    assert MANIFEST['referenceSha256'] == FEMALE['conditioningSha256'] == VOICE['referenceSha256'] == \
        '4d2bd83ff0f7fe33491b03193abdf623f1b4cc2d8103972b33638d3607d86dc5'
    assert MANIFEST['generation'] == FEMALE['generation'] == VOICE['generation'] == \
        {'exaggeration': 0.35, 'cfg_weight': 0.0, 'temperature': 0.8}
    assert MANIFEST['model']['sourceRevision'] == SOURCE['sourceRevision'] == '5de7a54aa4e5e2baadb0182dde554908b48b85c2'
    assert MANIFEST['model']['packageVersion'] == SOURCE['packageVersion'] == '0.1.7'
    assert MANIFEST['model']['revision'] == FEMALE['entries'][0]['recipe']['modelRevision']
    for e in MANIFEST['entries']:
        assert (e['speakerProfile'], e['referenceSha256'], e['generation'], e['model']) == \
            (MANIFEST['speakerProfile'], MANIFEST['referenceSha256'], MANIFEST['generation'], MANIFEST['model'])
        assert e['seed'] == int(hashlib.sha256(e['assetId'].encode()).hexdigest()[:8], 16)
    # The approved prepared library is a separate, untouched manifest.
    assert len(FEMALE['entries']) == 414


def test_committed_wav_bytes_match_manifest():
    for e in MANIFEST['entries']:
        assert e['audioPath'] == f"/audio/mental/closing-abc/v1/{e['language']}/female-calm-v1/{e['group']}/{e['fileName']}"
        raw = (PUBLIC / e['audioPath'].lstrip('/')).read_bytes()
        assert len(raw) == e['bytes'] and hashlib.sha256(raw).hexdigest() == e['sha256']
        with wave.open(str(PUBLIC / e['audioPath'].lstrip('/'))) as w:
            assert (w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getcomptype()) == \
                (e['channels'], e['sampleWidthBytes'], e['sampleRate'], 'NONE') == (1, 2, 24000, 'NONE')
            assert w.getnframes() == e['frames'] and len(w.readframes(w.getnframes())) == 2 * e['frames']
        assert abs(e['durationSeconds'] - e['frames'] / 24000) < 1e-6
        assert e['qualityMetrics']['clippedSamples'] == 0
        assert e['qualityMetrics']['leadingSilenceMs'] <= 1000 and e['qualityMetrics']['trailingSilenceMs'] <= 1200


def test_no_unearned_owner_approval_and_no_drive_urls():
    assert MANIFEST['approval']['status'] == 'technical-preview-awaiting-owner-listening'
    assert MANIFEST['approval']['ownerApprovedAt'] is None
    for e in MANIFEST['entries']:
        assert e['approvalStatus'] == 'technical-preview-awaiting-owner-listening' and e['ownerApprovedAt'] is None
    text = json.dumps(MANIFEST)
    assert 'drive.google.com' not in text and 'http' not in text.replace('https://huggingface.co', '')


def test_bridge_is_off_unless_explicitly_enabled():
    source = (ROOT / 'apps/vehicle-app/src/utils/mentalClosingBridge.ts').read_text('utf-8')
    assert "value==='approved'||value==='technical-preview'?value:'off'" in source
    # No checked-in deployment or environment file enables it.
    hits = [p for p in (ROOT / 'infra').rglob('*') if p.is_file() and 'NEXT_PUBLIC_MENTAL_CLOSING_BRIDGE' in p.read_text('utf-8', 'ignore')]
    assert hits == []


def test_all_125_combinations_per_language_are_computable():
    for language in ('tr', 'en', 'de'):
        groups = [[e for e in MANIFEST['entries'] if e['language'] == language and e['group'] == g] for g in 'ABC']
        totals = [sum(c['durationSeconds'] for c in combo) + 2 * MANIFEST['joinSilenceMs'] / 1000 for combo in itertools.product(*groups)]
        assert len(totals) == 125 and all(t > 0 for t in totals)


def test_page_skips_completion_guidance_after_a_spoken_closing():
    """After the bridge spoke (or the user stopped it), the separate 'mental-complete' guidance would be a second
    completion message in another voice; the page only plays it when nothing was spoken."""
    page = (ROOT / 'apps/vehicle-app/src/app/mental/page.tsx').read_text('utf-8')
    hook = (ROOT / 'apps/vehicle-app/src/utils/useMentalConversation.ts').read_text('utf-8')
    assert "c.phase==='completed'?(c.spokenClosing?undefined:'mental-complete'):'mental-entry'" in page
    assert "setSpokenClosing(outcome!=='fallback')" in hook and 'setSpokenClosing(false);' in hook
