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
    # only boxes at or above the decision threshold become markers, each with its own photo
    assert mole_r['markers'] == [dict(x=10.0, y=20.0, r=3.0, pose='LEFT')]
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
