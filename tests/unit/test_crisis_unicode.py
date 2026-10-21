"""Exercise actual frontend detector and backend reply guards, not footer text."""
import json
from pathlib import Path
import subprocess
import sys
import unicodedata

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'services/core-api'))
from main import app
from mental_provider import check_mental_crisis, normalize_crisis_text

PHRASES = [
    'intihar', 'İNTİHAR', 'İntihar', 'iNtIhAr', 'INTIHAR', 'i\u0307ntihar',
    'CANIMA KIYMAK', 'ÖLMEK İSTİYORUM', 'KeNdİmE ZaRaR',
    unicodedata.normalize('NFD', 'YAŞAMAK İSTEMİYORUM'),
]
BENIGN = ['Bugün yeni bir kitap okudum.', 'İyi hissediyorum, ailemle görüştüm.']


@pytest.mark.parametrize('text', PHRASES)
@pytest.mark.parametrize('driving', [False, True])
def test_backend_crisis_unicode(text, driving):
    result = check_mental_crisis(text, driving)
    assert result['isCrisis'] is True
    assert result['needsEmergencyEscalation'] is True
    assert '112' in result['reply'] and '182' not in result['reply']
    if driving:
        assert 'ekrana bakmayın' in result['reply']


@pytest.mark.parametrize('text', PHRASES + BENIGN)
def test_actual_backend_reply_path(text):
    response = TestClient(app).post('/api/mental/converse', json={'userMessage': text})
    assert response.status_code == 200
    data = response.json()
    if text in PHRASES:
        assert data['isCrisis'] is True
        assert data['providerType'] == 'CRISIS_SAFETY_GUARD'
        assert '112' in data['reply'] and '182' not in data['reply']
    else:
        assert not data.get('isCrisis', False)
        assert data['providerType'] != 'CRISIS_SAFETY_GUARD'


def test_frontend_detector_matches_backend_without_losing_turkish_accents():
    # Load production TypeScript with its real shared JSON dependencies.
    script = r"""
const fs = require('fs');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
require('./tests/unit/ts_loader.js');
const detector = require('./packages/safety/crisisDetector.ts');
process.stdout.write(JSON.stringify({
 results: input.texts.map(text=>detector.checkCrisisTrigger(text)),
 accents: detector.normalizeCrisisText('ÇĞÖŞÜ I İ')
}));
"""
    completed = subprocess.run(['node', '-e', script], cwd=ROOT, check=True,
        input=json.dumps({'texts': PHRASES + BENIGN}),
        capture_output=True, text=True, encoding='utf-8')
    observed = json.loads(completed.stdout)
    for i, result in enumerate(observed['results']):
        assert result['isCrisis'] is (i < len(PHRASES))
        if result['isCrisis']:
            assert '112' in result['emergencyResponseTr']
    assert observed['accents'] == normalize_crisis_text('ÇĞÖŞÜ I İ') == 'çğöşü ı i'
