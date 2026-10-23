"""Actual Python server summaries cross the browser/history contract unchanged.

Synthetic policies test protocol boundaries only; no method is accepted by them.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'services/core-api'))
import regional_skin_evidence as R


def test_server_browser_and_numeric_history_contract():
    policies = {k: dict(methodVersion='fixture-' + k, normalizationVersion='fixture-scale',
                       validationEvidence='synthetic-test-only', modelHash='fixture-hash',
                       negativeMax=10, positiveMin=30, minCoverage=.8, minAnalysisPixels=100)
                for k in ('oil', 'dry', 'redness')}
    measurements = {region: [dict(id=k, region=region, value=40 if (
        k == 'oil' and region in R.T_ZONE or k in ('dry', 'redness') and region == 'leftCheek') else 0,
        quality='valid', methodVersion='fixture-' + k, normalizationVersion='fixture-scale',
        modelHash='fixture-hash', evaluatedArea=dict(scope='anatomical-region', region=region,
        sourcePixels=900, anatomicalSourcePixels=1000, analysisPixels=200))
        for k in ('oil', 'dry', 'redness')] for region in R.REGIONS}
    fixtures = dict(unknown=R.build_regional_map(measurements),
                    combination=R.build_regional_map(measurements, policies))
    measurements['forehead'] = []
    fixtures['partial'] = R.build_regional_map(measurements, policies)
    next(r for r in measurements['leftCheek'] if r['id'] == 'oil')['value'] = 40
    fixtures['conflict'] = R.build_regional_map(measurements, policies)
    result = subprocess.run(['node', '--no-warnings', '--experimental-vm-modules',
        'tests/unit/regional_skin_map_frontend.cjs'], cwd=ROOT, input=json.dumps(fixtures),
        capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report['checks'] >= 55 and report['serverFixtures'] == 4
    assert report['result'] == 'pass'
    assert report['scope'] == 'numeric-contract-converter-and-svg-layer-plan'


def test_face_panel_renders_only_the_sanitized_layer_plan():
    source = (ROOT / 'apps/vehicle-app/src/components/skin/SkinFacePanel.tsx').read_text('utf8')
    assert 'regionalSkinLayers(snapshot.general?.regionalSkinMap' in source
    assert 'data-regional-geometry={layer.geometry}' in source
    assert 'data-regional-redness={layer.redness}' in source
    assert 'red-hatch' in source
    assert "layer.fill==='lightgrey'?'.20':'.24'" in source
    assert 'sensitivity' not in source[source.index('regionalLayers.map'):source.index("{localMap&&")]
