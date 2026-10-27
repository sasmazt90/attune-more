"""Synthetic projection fixtures; not model, browser or camera acceptance."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'e2e'))
from skin_browser_support import expected_findings

def test_seen_classifier_without_measurement_requires_explicit_unavailability():
 r=expected_findings(dict(version='synthetic-test',status='measured',findings=[dict(id='redness',region='chin',status='seen',appearanceUnavailable='MEASURE_NOT_AVAILABLE')],unavailable=[]))
 item=r['overview'][0]
 assert item['id']=='redness' and item['score'] is None and item['count'] is None
 assert item['text']=='Görünüm skoru hesaplanamadı' and not item['band']
 assert r['unavailable']==[]

def test_actual_zero_score_remains_measured_not_unavailable():
 r=expected_findings(dict(version='synthetic-test',status='measured',findings=[dict(id='darkCircles',region='periorbital',status='seen',severity=0)],unavailable=[]))
 item=r['overview'][0];assert item['score']==0 and item['text']=='%0' and item['band']

def test_unavailable_findings_have_reasons_and_do_not_become_seen_cards():
 r=expected_findings(dict(version='synthetic-test',status='unavailable',findings=[],unavailable=[dict(id='redness',reason='MODEL_BUNDLE_UNAVAILABLE')]))
 assert r['overview']==[] and r['unavailable']==[dict(id='redness',reason='MODEL_BUNDLE_UNAVAILABLE')]
