"""general.findings from saved detector scores (skin_findings_v1) and the three-angle fusion endpoint.
No model is loaded here: per-photo evidence is given as numbers, exactly as regional_skin_v3.analyze_photo returns it."""
import asyncio, sys
from pathlib import Path
import httpx
from fastapi import FastAPI
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'services/core-api'))
import skin_findings_v1 as SF
import regional_attach as RA
import local_health as health

KEYS = SF.EVIDENCE_KEYS
import pytest


@pytest.fixture(autouse=True)
def no_bundle(monkeypatch):
    """Unit tests never depend on a model bundle on this machine (ATTUNE_REGIONAL_V3_DIR); tests that need saved
    classifiers patch their own specs."""
    monkeypatch.setattr(SF, '_saved_specs', lambda: {})


def region(score=0.0, area=400, usable=True, **over):
    row = dict(areaPx=area, usable=usable, **{k: 0.0 for k in KEYS})
    row.update(over)
    return row


def photo(pose, evidence, boxes=(), causes=None):
    return dict(findingEvidence=evidence, findingBoxes=list(boxes), regions={k: dict(causes=v) for k, v in (causes or {}).items()},
                models={'findings.pt': 'c8d94801'})


def three(front, left, right):
    return {'FRONT': photo('FRONT', **front), 'LEFT': photo('LEFT', **left), 'RIGHT': photo('RIGHT', **right)}


def by(result, fid, reg):
    return next(f for f in result['findings'] if f['id'] == fid and f['region'] == reg)


def test_missing_poses_are_unavailable_never_not_seen():
    out = SF.findings_from_maps({'FRONT': photo('FRONT', {'nose': region(findings_Rozasea_max=0.99)})})
    assert out['status'] == 'unavailable' and out['reason'] == 'REQUIRED_POSES_MISSING'
    assert out['missingPoses'] == ['LEFT', 'RIGHT'] and out['findings'] == []
    reasons = {u['id']: u['reason'] for u in out['unavailable']}
    assert reasons['rosacea'] == reasons['mole'] == reasons['melasma'] == 'REQUIRED_POSES_MISSING'
    assert reasons['acne'] == 'MODEL_NOT_AVAILABLE' and reasons['spots'] == 'NOT_VALIDATED'


def test_thresholds_regions_and_poses():
    ev = {r: region() for r in SF.APP_REGIONS}
    front = dict(evidence={**ev, 'nose': region(findings_Rozasea_max=0.70), 'forehead': region(findings_Rozasea_max=0.68)})
    # LEFT pose shows the subject's right cheek: a mole score there counts; the same score on the hidden cheek does not
    left = dict(evidence={**ev, 'rightCheek': region(findings_Riskli_Ben_max=0.60), 'leftCheek': region(findings_Riskli_Ben_max=0.99, usable=False)},
                boxes=[dict(finding='mole', region='rightCheek', pose='LEFT', x=10.0, y=20.0, r=3.0, score=0.60),
                       dict(finding='mole', region='rightCheek', pose='LEFT', x=11.0, y=21.0, r=3.0, score=0.40)])
    right = dict(evidence={**ev, 'leftCheek': region(findings_Gunes_Lekesi_max=0.53), 'rightCheek': region(usable=False)})
    out = SF.findings_from_maps(three(front, left, right))
    assert out['status'] == 'measured' and out['poses'] == ['FRONT', 'LEFT', 'RIGHT']
    assert by(out, 'rosacea', 'nose')['status'] == 'seen' and by(out, 'rosacea', 'forehead')['status'] == 'notSeen'
    mole_r = by(out, 'mole', 'rightCheek')
    assert mole_r['status'] == 'seen' and mole_r['pose'] == 'LEFT'
    # every box the detector marks (score >= 0.35, research n35) on ONE photo (the side facing the cheek) is a marker,
    # and the displayed count is exactly the number of markers
    assert mole_r['markers'] == [dict(x=10.0, y=20.0, r=3.0, pose='LEFT'), dict(x=11.0, y=21.0, r=3.0, pose='LEFT')]
    assert mole_r['count'] == 2 and 'countAtLeast' not in mole_r
    assert by(out, 'mole', 'leftCheek')['status'] == 'notSeen'          # the hidden-cheek 0.99 was not read
    assert by(out, 'melasma', 'leftCheek')['status'] == 'notSeen'       # 0.53 < 0.54
    # no score, area, severity or count is produced by this version
    for f in out['findings']:
        assert not {'severity', 'areaPct', 'countRange'} & set(f)
    assert {u['id'] for u in out['unavailable']} == set(SF.UNAVAILABLE)


def test_unreadable_region_is_inconclusive_with_causes():
    ev = {r: region() for r in SF.APP_REGIONS}
    small = {**ev, 'chin': region(findings_Rozasea_max=0.95, area=SF.MIN_REGION_PX - 1)}
    out = SF.findings_from_maps(three(dict(evidence=small, causes={'chin': ['LIGHTING']}), dict(evidence=small), dict(evidence=small)))
    chin = by(out, 'rosacea', 'chin')
    assert chin['status'] == 'inconclusive' and chin['causes'] == ['LIGHTING'] and 'pose' not in chin


def test_bundle_failure_is_unavailable_for_every_finding():
    out = RA.findings_unavailable('MODEL_BUNDLE_UNAVAILABLE')
    assert out['status'] == 'unavailable' and out['findings'] == []
    assert {u['id'] for u in out['unavailable']} == set(SF.DETECTOR_FINDINGS) | set(SF.UNAVAILABLE)


def post(value, park=True):
    app = FastAPI(); app.include_router(health.router); previous = health.parked; health.parked = lambda: park
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as c:
            return await c.post('/api/local-health/skin/regional-fuse', json=value)
    try:
        return asyncio.run(run())
    finally:
        health.parked = previous


def test_regional_fuse_endpoint(monkeypatch):
    import regional_skin_v3 as R
    monkeypatch.setattr(R, 'fuse_maps', lambda maps: dict(version='stub', regions={}, skinType=dict(value=None, quality='insufficient')))
    assert post({'processingConsent': True, 'maps': {}}, park=False).status_code == 409
    assert post({'maps': {}}).status_code == 422                       # no processing consent
    assert post({'processingConsent': True, 'maps': 'x'}).status_code == 422
    assert post({'processingConsent': True, 'maps': {'LEFT': {}}}).status_code == 422   # FRONT required
    ev = {r: region() for r in SF.APP_REGIONS}
    maps = three(dict(evidence={**ev, 'nose': region(findings_Rozasea_max=0.9)}), dict(evidence=ev), dict(evidence=ev))
    body = post({'processingConsent': True, 'maps': maps}).json()
    assert body['regionalSkinMapStatus'] == 'OK' and body['regionalSkinMap']['version'] == 'stub'
    assert body['findings']['status'] == 'measured' and by(body['findings'], 'rosacea', 'nose')['status'] == 'seen'
    def boom(maps): raise RuntimeError('no bundle')
    monkeypatch.setattr(R, 'fuse_maps', boom)
    body = post({'processingConsent': True, 'maps': maps}).json()
    # the skin-type map is absent (nothing painted), the findings still come from the per-photo detector evidence
    assert body['regionalSkinMap'] is None and body['regionalSkinMapStatus'] == 'REGIONAL_FUSION_UNAVAILABLE'
    assert body['findings']['status'] == 'measured'
    # a photo without finding evidence (bundle missing for that photo) -> required poses missing, never "not seen"
    maps['LEFT'] = {'regions': {}}
    assert post({'processingConsent': True, 'maps': maps}).json()['findings']['reason'] == 'REQUIRED_POSES_MISSING'


def test_saved_crop_classifiers_decision_rule(monkeypatch):
    """findings-v2 (saved DINOv2-crop classifiers): fa4 recipe = max over poses per region; nested-CV recipe = mean over
    the poses that show the crop; available findings leave the 'unavailable' list; no scores -> inconclusive."""
    specs = {'eyeBags': dict(id='eyeBags', recipe='fa4', threshold=0.9, regionOf={'under_L': 'periorbital', 'under_R': 'periorbital'}),
             'eczema': dict(id='eczema', recipe='eczema', threshold=0.8, regionOf={'cheek_L': 'rightCheek', 'cheek_R': 'leftCheek', 'forehead': 'forehead', 'jaw': 'chin'})}
    monkeypatch.setattr(SF, '_saved_specs', lambda: specs)
    ev = {r: region() for r in SF.APP_REGIONS}
    maps = three(dict(evidence=ev), dict(evidence=ev), dict(evidence=ev))
    maps['FRONT']['findingScores'] = {'eyeBags': {'under_L': 0.5, 'under_R': 0.95}, 'eczema': {'cheek_L': 0.9, 'cheek_R': 0.1, 'forehead': 0.2}}
    maps['LEFT']['findingScores'] = {'eyeBags': {'under_L': 0.3}, 'eczema': {'cheek_L': 0.6, 'forehead': 0.3}}
    maps['RIGHT']['findingScores'] = {'eyeBags': {'under_R': 0.2}, 'eczema': {'cheek_R': 0.2, 'forehead': 0.1}}
    out = SF.findings_from_maps(maps)
    assert by(out, 'eyeBags', 'periorbital')['status'] == 'seen' and by(out, 'eyeBags', 'periorbital')['pose'] == 'FRONT'
    # eczema rightCheek: mean(0.9, 0.6) = 0.75 < 0.8, but the person-level max 0.9 >= 0.8 -> the top region is shown
    assert by(out, 'eczema', 'rightCheek')['status'] == 'seen' and by(out, 'eczema', 'leftCheek')['status'] == 'notSeen'
    assert by(out, 'eczema', 'chin')['status'] == 'inconclusive'          # no jaw crop score in any photo
    assert not {'eyeBags', 'eczema'} & {u['id'] for u in out['unavailable']}
    assert out['version'] == 'skin-findings-v2'
    missing = SF.findings_from_maps({'FRONT': maps['FRONT']})
    assert {u['id']: u['reason'] for u in missing['unavailable']}['eyeBags'] == 'REQUIRED_POSES_MISSING'


def test_dino_module_probability_matches_sklearn():
    """skin_findings_dino._prob reproduces a StandardScaler+LogisticRegression fold-ensemble exactly."""
    import numpy as np, skin_findings_dino as SD
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline
    rng = np.random.default_rng(0); X = rng.normal(size=(60, 8)); y = (X[:, 0] + rng.normal(size=60) > 0)
    ms = [make_pipeline(StandardScaler(), LogisticRegression(C=0.02, class_weight='balanced')).fit(X[i::2], y[i::2]) for i in (0, 1)]
    folds = [dict(mean=m[0].mean_.tolist(), scale=m[0].scale_.tolist(), coef=m[1].coef_[0].tolist(), intercept=float(m[1].intercept_[0])) for m in ms]
    x = rng.normal(size=8)
    assert abs(SD._prob(folds, x) - np.mean([m.predict_proba(x[None])[0, 1] for m in ms])) < 1e-12


def test_counts_never_double_count_and_melasma_area():
    ev = {r: region() for r in SF.APP_REGIONS}
    box = lambda pose, x: dict(finding='mole', region='leftCheek', pose=pose, x=x, y=1.0, r=2.0, score=0.6)
    front = dict(evidence={**ev, 'leftCheek': region(findings_Riskli_Ben_max=0.7, findings_Gunes_Lekesi_max=0.6, findings_Gunes_Lekesi_cov20=0.123)},
                 boxes=[box('FRONT', 1.0), box('FRONT', 2.0), box('FRONT', 3.0)])
    right = dict(evidence={**ev, 'leftCheek': region(findings_Riskli_Ben_max=0.65)}, boxes=[box('RIGHT', 5.0)])
    out = SF.findings_from_maps(three(front, dict(evidence=ev), right))
    m = by(out, 'mole', 'leftCheek')
    # the same moles are visible in the front and the right photo: counted once, from the photo facing the cheek (RIGHT)
    assert m['count'] == 1 and [k['pose'] for k in m['markers']] == ['RIGHT']
    assert by(out, 'melasma', 'leftCheek')['areaPct'] == 12.3
    # seen by the decision but the completed count marked no lesion -> 0 (no invented "1+")
    out2 = SF.findings_from_maps(three(dict(evidence={**ev, 'leftCheek': region(findings_Riskli_Ben_max=0.7)}), dict(evidence=ev), dict(evidence=ev)))
    m2 = by(out2, 'mole', 'leftCheek')
    assert m2['count'] == 0 and 'countAtLeast' not in m2 and m2['markers'] == [] and m2['countPose'] == 'RIGHT'
    # the count could not be done (no detector boxes on any photo) -> no number at all, never a measured 0
    maps3 = three(dict(evidence={**ev, 'leftCheek': region(findings_Riskli_Ben_max=0.7)}), dict(evidence=ev), dict(evidence=ev))
    for m in maps3.values(): m['findingBoxes'] = None
    m3 = by(SF.findings_from_maps(maps3), 'mole', 'leftCheek')
    assert 'count' not in m3 and 'countAtLeast' not in m3 and m3['countUnavailable'] == 'COUNT_NOT_RUN'
    # the region is unreadable on every photo -> not counted either
    maps4 = three(dict(evidence={**ev, 'leftCheek': region(findings_Riskli_Ben_max=0.7)}), dict(evidence={**ev, 'leftCheek': region(usable=False)}), dict(evidence={**ev, 'leftCheek': region(usable=False)}))
    m4 = by(SF.findings_from_maps(maps4), 'mole', 'leftCheek')
    assert m4['count'] == 0 and m4['countPose'] == 'FRONT'   # FRONT read the cheek and counted it


def test_eye_rows_front_only_and_missing_score(monkeypatch):
    import skin_findings_eye as SEYE
    spec = {'darkCircles': dict(id='darkCircles', threshold=0.85), 'downturnedCorners': dict(id='downturnedCorners', threshold=0.67)}
    monkeypatch.setattr(SF, '_eye_specs', lambda: spec)
    monkeypatch.setattr(SEYE, 'decide', lambda p, s: 'seen' if p >= s['threshold'] else 'notSeen')
    ev = {r: region() for r in SF.APP_REGIONS}
    maps = three(dict(evidence=ev), dict(evidence=ev), dict(evidence=ev))
    maps['FRONT']['eyeScores'] = {'downturnedCorners': 0.9}; maps['FRONT']['eyeMeasures'] = {'downturnedCorners': 72.0}
    maps['LEFT']['eyeScores'] = {'darkCircles': 0.99}          # side photos never decide eye findings
    out = SF.findings_from_maps(maps)
    assert by(out, 'downturnedCorners', 'periorbital') == dict(id='downturnedCorners', region='periorbital', status='seen', pose='FRONT', readFrom=['FRONT'], severity=72.0)
    assert by(out, 'darkCircles', 'periorbital')['status'] == 'inconclusive'
    assert not {'darkCircles', 'downturnedCorners'} & {u['id'] for u in out['unavailable']}


def test_appearance_raw_values_shared_mask_and_unavailable():
    """appearance-v1 on the server: raw area/intensity from the light-corrected red pixel mask (never a box), the
    score from them, the shared regional mask said explicitly, and no score where no affected-area mask exists."""
    import skin_findings_det as SFD, skin_appearance as SA
    v9 = [10.0, 14.0, 1.5, 0.2, 0.05, 3.0, 1000, 200, 9.0]
    m = SFD.redness_measures({'lightRedness': {rk: v9 for rk in SFD.FACE}}, 'FRONT')
    assert m and all(r['appearance'] == SA.region(1000, 200, 9.0) for r in m.values())
    assert all(r['areaPct'] == 20.0 and r['toneDiff'] == 1.5 for r in m.values())     # existing raw values unchanged
    m6 = SFD.redness_measures({'lightRedness': {rk: v9[:6] for rk in SFD.FACE}}, 'FRONT')
    assert m6 and not any('appearance' in r for r in m6.values())                   # older 6-field input: no score invented
    app = SA.region(1000, 200, 9.0)
    rows = [dict(id='redness', region='nose', status='seen', appearance=app), dict(id='rosacea', region='nose', status='seen', appearance=app),
            dict(id='eczema', region='chin', status='seen'), dict(id='melasma', region='leftCheek', status='seen', areaPct=12.0),
            dict(id='acneMarks', region='chin', status='seen', severity=40.0), dict(id='rosacea', region='chin', status='notSeen', appearance=app)]
    SF._mark_appearance(rows)
    assert rows[0]['appearanceSharedWith'] == ['rosacea'] and rows[1]['appearanceSharedWith'] == ['redness']
    assert rows[2]['appearanceUnavailable'] == 'MEASURE_NOT_AVAILABLE' and 'appearance' not in rows[2]
    assert rows[3]['appearanceUnavailable'] == 'AFFECTED_MASK_NOT_AVAILABLE' and rows[3]['areaPct'] == 12.0
    assert rows[4]['appearanceUnavailable'] == 'AFFECTED_MASK_NOT_AVAILABLE' and rows[4]['severity'] == 40.0
    assert 'appearanceSharedWith' not in rows[5]
