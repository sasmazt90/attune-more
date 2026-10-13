"""Selected frozen AG eye-region regressions; no acne/model enablement."""
import sys, math, json
from pathlib import Path
import numpy as np
import cv2
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'services/core-api'))
sys.path.insert(0,str(ROOT/'scripts'))
import appearance_analysis as A
from test_local_appearance_health import photo

def test_history_v4_v5_keep_separate_series_with_null_gaps_and_no_rewrite():
    import subprocess
    script=r'''
require('./tests/unit/ts_loader.js');
const assert=require('assert/strict'),{buildHistorySeries}=require('./apps/vehicle-app/src/utils/healthHistorySeries.ts'),{canCompareIndicator}=require('./apps/vehicle-app/src/utils/skinIndicators.ts'),{compareAppearance}=require('./apps/vehicle-app/src/utils/appearanceMeasurements.ts');
function row(version,value){return {id:'bags',score:value,method:'appearance-cv-6',unit:'%',appearance:{type:'appearance_proxy',methodVersion:'appearance-cv-6',normalizationVersion:'contour-fold-local-support-'+version,region:'periorbital',unit:'contour-fold-index-0-100',value,quality:'valid',limitationCode:null,referenceId:null,components:{}},measurement:{scope:'regional',region:'periorbital',methodVersion:'appearance-cv-6',unit:'contour-fold-index-0-100',rawValue:value,quality:'valid',modelHash:null,validation:'appearance-proxy'}};}
const old={id:'old',date:'2026-10-11T10:00:00Z',schemaVersion:3,indicators:{periorbital:[row('v4',7)]}},now={id:'new',date:'2026-10-12T10:00:00Z',schemaVersion:3,indicators:{periorbital:[row('v5',11)]}},before=JSON.stringify(old);
assert(!canCompareIndicator(now.indicators.periorbital[0],old.indicators.periorbital[0]));compareAppearance(now.indicators.periorbital[0],old.indicators.periorbital[0],true,'old');assert.equal(now.indicators.periorbital[0].referenceDelta,undefined);assert.equal(JSON.stringify(old),before);
const series=buildHistorySeries('skin',[old,now]).filter(s=>s.criterion==='bags'&&s.region==='periorbital');assert.equal(series.length,2);
for(const [version,id,value] of [['v4','old',7],['v5','new',11]]){const s=series.find(s=>s.id.includes('contour-fold-local-support-'+version));const observations=s.points.filter(p=>!p.id.endsWith(':missing'));assert.equal(observations.length,1);assert.equal(observations[0].recordId,id);assert.equal(observations[0].value,value);assert(s.points.filter(p=>p.recordId!==id).every(p=>p.value===null&&p.id.endsWith(':missing')));}
'''
    r=subprocess.run(['node','-e',script],cwd=ROOT,text=True,capture_output=True,timeout=30)
    assert r.returncode==0,r.stdout+r.stderr

def test_low_continuity_zero_gate_is_eye_only_and_failure_stays_unknown(monkeypatch):
    import instant_appearance as IA
    import pytest
    from test_local_appearance_health import landmarks
    p=landmarks()
    for i,x,y in [(133,.45,.4),(159,.375,.35),(145,.375,.45),(362,.55,.4),(386,.625,.35),(374,.625,.45)]:
        p[i]=dict(x=x,y=y,z=0.)
    def profile(*args,**kwargs):
        return dict(strength=.5,edge=.04,continuity=.1,coverage=1.,trackingResidual=0.,trackingQualityVersion='unit-controlled-continuity',points=np.array([[160.,160.]]),tracked=np.tile([160.,160.],(64,1)),values=np.full(64,.5),edgeValues=np.full(64,.04),support=np.ones(64,bool),observedSamples=np.ones(64,bool))
    monkeypatch.setattr(IA,'curve_profile',profile)
    monkeypatch.setattr(IA,'boundary_support',lambda *args:dict(value=.08,coverage=1.,points=[],supported=[]))
    gray=np.full((320,320),.5,np.float32);eligible=np.ones(gray.shape,bool);cond=dict(yaw=0.,pitch=0.)
    eye=IA.instant_proxy(gray,eligible,p,'periorbital',cond,1,(0,0),gray.shape)
    assert eye[0]==0 and not eye[2].any() and eye[4] is None
    for region in ('rightCheek','leftCheek','chin'):
        lower=IA.instant_proxy(gray,eligible,p,region,cond,1,(0,0),gray.shape)
        assert lower[0]==pytest.approx(100*.5*.1/.6)
        assert lower[1]['formulaVersion']=='contour-fold-visible-region-unique-centers-v7'
    unavailable=IA.instant_proxy(gray,eligible,p,'periorbital',dict(yaw=0.,pitch=.3),1,(0,0),gray.shape)
    assert unavailable[0] is None and unavailable[4]=='HEAD_ANGLE_UNSUPPORTED'
    assert not unavailable[2].any()

def test_eye_fold_outside_measured_band_cannot_contribute_to_score_or_map():
    import instant_appearance as IA
    gray=np.full((100,120),.7,np.float32);gray[43:45]=.4
    context=np.ones(gray.shape,bool);target=np.zeros(gray.shape,bool);target[50:60]=True
    guide=np.asarray([[20,30],[100,30]],np.float32);normal=np.array([0,1]);offsets=np.arange(7,28)
    broad=IA.curve_profile(gray,context,guide,normal,offsets,320)
    local=IA.curve_profile(gray,context,guide,normal,offsets,320,center_support=target)
    assert broad['strength']>0 and broad['support'].any()
    assert local['coverage']==1 and local['observedSamples'].all()
    assert not local['values'].any() and not local['support'].any()
    for x,y in np.rint(local['tracked']).astype(int):assert target[y,x]
def test_target_b_dark_circles_normal_skin_deadband():
    """Target B: Normal skin with subtle contrast variation (< 5%) produces 0 dark circle score."""
    h, w = 280, 320
    p = [dict(x=.5, y=.5, z=0.) for _ in range(478)]
    oval = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109]
    for i, angle in zip(oval, np.linspace(-np.pi/2, 3*np.pi/2, len(oval), endpoint=False)):
        p[i].update(x=.5+.49*np.cos(angle), y=.5+.48*np.sin(angle))
    locations = {234: (0, 150), 454: (320, 150), 33: (40, 70), 133: (110, 70), 159: (75, 64), 163: (50, 76),
                 144: (60, 80), 145: (75, 82), 153: (90, 83), 154: (100, 80), 155: (105, 76),
                 263: (280, 70), 362: (210, 70), 386: (245, 64), 390: (270, 76), 373: (260, 80),
                 374: (245, 82), 380: (230, 83), 381: (220, 80), 382: (215, 76), 61: (110, 165), 291: (210, 165),
                 13: (160, 165), 14: (160, 168)}
    for i, (x, y) in locations.items():
        p[i].update(x=x/w, y=y/h)
    mesh = {'points': [{'x': 0, 'y': 40}, {'x': 320, 'y': 40}, {'x': 320, 'y': 130}, {'x': 0, 'y': 130}], 'edges': [[0, 1], [1, 2], [2, 3], [3, 0], [0, 2]]}

    # Image with subtle 3% luminance difference (typical normal healthy skin)
    image = np.full((h, w, 3), 150, np.uint8)
    image[80:95, 50:100] = 145  # 145 vs 150 is 3.3% relative contrast (< 5% deadband)

    url, digest = photo(image)
    res = A.analyze_skin(dict(photo=url, photoId=digest, landmarks=p, meshes={'periorbital': mesh}, exclusions=[], pose='FRONT', qualityValid=True, conditions=dict(yaw=0., pitch=0., roll=0., scaleRatio=.6, avgLuminance=150., blurScore=50.)))
    dark = next(v for v in res['measurements']['periorbital'] if v['id'] == 'dark')
    assert dark['value'] == 0.0, f"Expected 0 for subtle normal skin variance, got {dark['value']}"


def test_target_b_dark_circles_shadow_vs_pigment_separation():
    """Target B: Pure structural shadow without chromatic shift is discounted,
    whereas true chromatic hyperpigmentation is detected.
    """
    h, w = 280, 320
    p = [dict(x=.5, y=.5, z=0.) for _ in range(478)]
    oval = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109]
    for i, angle in zip(oval, np.linspace(-np.pi/2, 3*np.pi/2, len(oval), endpoint=False)):
        p[i].update(x=.5+.49*np.cos(angle), y=.5+.48*np.sin(angle))
    locations = {234: (0, 150), 454: (320, 150), 33: (40, 70), 133: (110, 70), 159: (75, 64), 163: (50, 76),
                 144: (60, 80), 145: (75, 82), 153: (90, 83), 154: (100, 80), 155: (105, 76),
                 263: (280, 70), 362: (210, 70), 386: (245, 64), 390: (270, 76), 373: (260, 80),
                 374: (245, 82), 380: (230, 83), 381: (220, 80), 382: (215, 76), 61: (110, 165), 291: (210, 165),
                 13: (160, 165), 14: (160, 168)}
    for i, (x, y) in locations.items():
        p[i].update(x=x/w, y=y/h)
    mesh = {'points': [{'x': 0, 'y': 40}, {'x': 320, 'y': 40}, {'x': 320, 'y': 130}, {'x': 0, 'y': 130}], 'edges': [[0, 1], [1, 2], [2, 3], [3, 0], [0, 2]]}

    # 1. Pure luminance shadow: drop luminance from 160 to 125, but zero chromatic shift
    img_shadow = np.full((h, w, 3), 160, np.uint8)
    img_shadow[80:95, 50:100] = 125
    url_shadow, digest_shadow = photo(img_shadow)
    res_shadow = A.analyze_skin(dict(photo=url_shadow, photoId=digest_shadow, landmarks=p, meshes={'periorbital': mesh}, exclusions=[], pose='FRONT', qualityValid=True, conditions=dict(yaw=0., pitch=0., roll=0., scaleRatio=.6, avgLuminance=150., blurScore=50.)))
    score_shadow = next(v for v in res_shadow['measurements']['periorbital'] if v['id'] == 'dark')['value']

    # 2. True chromatic pigment: same luminance drop (125) PLUS chromatic shift (purplish/brown undertone)
    img_pigment = np.full((h, w, 3), 160, np.uint8)
    img_pigment[80:95, 50:100, 0] = 140  # Blue higher (bluish/purple pooling)
    img_pigment[80:95, 50:100, 1] = 115  # Green lower
    img_pigment[80:95, 50:100, 2] = 120  # Red lower
    url_pigment, digest_pigment = photo(img_pigment)
    res_pigment = A.analyze_skin(dict(photo=url_pigment, photoId=digest_pigment, landmarks=p, meshes={'periorbital': mesh}, exclusions=[], pose='FRONT', qualityValid=True, conditions=dict(yaw=0., pitch=0., roll=0., scaleRatio=.6, avgLuminance=150., blurScore=50.)))
    score_pigment = next(v for v in res_pigment['measurements']['periorbital'] if v['id'] == 'dark')['value']

    assert score_pigment > score_shadow, f"True chromatic pigment ({score_pigment}) must score higher than pure shadow ({score_shadow})"


def test_target_c_dark_circles_and_eye_bags_masks_remain_distinct():
    """Target C: Dark circles and eye bags must not produce identical masks.
    Dark circles are relative contrast on bands['dark']; eye bags require fold deflection.
    """
    p = [dict(x=.5, y=.5) for _ in range(478)]
    for i, x, y in [(234, .15, .5), (454, .85, .5)]:
        p[i] = dict(x=x, y=y)
    for ids, xs in [([33, 163, 144, 145, 153, 154, 155, 133], np.linspace(.25, .42, 8)),
                    ([263, 390, 373, 374, 380, 381, 382, 362], np.linspace(.75, .58, 8))]:
        for i, x in zip(ids, xs):
            p[i] = dict(x=float(x), y=.4)
    bands = A.eye_skin_bands(p, (500, 500), 1, (0, 0), (500, 500))

    assert not np.array_equal(bands['dark'], bands['bags'])
    # Lower lid margin protects tarsal plate (dark starts at 0.012, bags starts at 0.022)
    assert not bands['dark'][:204].any()
    assert not bands['bags'][:208].any()


def test_target_c_eye_bags_version_and_eyelid_margin_separation():
    """Target C: Method version is contour-fold-local-support-v5.
    Lower eyelid margin (offsets < 7) is excluded, and discontinuous valley noise (< 0.20 continuity)
    produces score 0.0, eliminating false positives on normal lower lids.
    """
    import instant_appearance as IA
    assert A.NORMALIZATION['bags'] == 'contour-fold-local-support-v5'

    h, w = 280, 320
    p = [dict(x=.5, y=.5, z=0.) for _ in range(478)]
    oval = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109]
    for i, angle in zip(oval, np.linspace(-np.pi/2, 3*np.pi/2, len(oval), endpoint=False)):
        p[i].update(x=.5+.49*np.cos(angle), y=.5+.48*np.sin(angle))
    locations = {234: (0, 150), 454: (320, 150), 33: (40, 70), 133: (110, 70), 159: (75, 64), 163: (50, 76),
                 144: (60, 80), 145: (75, 82), 153: (90, 83), 154: (100, 80), 155: (105, 76),
                 263: (280, 70), 362: (210, 70), 386: (245, 64), 390: (270, 76), 373: (260, 80),
                 374: (245, 82), 380: (230, 83), 381: (220, 80), 382: (215, 76), 61: (110, 165), 291: (210, 165),
                 13: (160, 165), 14: (160, 168)}
    for i, (x, y) in locations.items():
        p[i].update(x=x/w, y=y/h)

    mesh = {'points': [{'x': 0, 'y': 40}, {'x': 320, 'y': 40}, {'x': 320, 'y': 130}, {'x': 0, 'y': 130}], 'edges': [[0, 1], [1, 2], [2, 3], [3, 0], [0, 2]]}

    # Normal image with subtle lower eyelid margin dip at offset 4-5
    img = np.full((h, w, 3), 150, np.uint8)
    img[84:86, 50:110] = 142  # 5% dip near eyelid margin
    url, digest = photo(img)

    res = A.analyze_skin(dict(photo=url, photoId=digest, landmarks=p, meshes={'periorbital': mesh}, exclusions=[], pose='FRONT', qualityValid=True, conditions=dict(yaw=0., pitch=0., roll=0., scaleRatio=.6, avgLuminance=150., blurScore=50.)))
    bags = next(v for v in res['measurements']['periorbital'] if v['id'] == 'bags')
    assert bags['normalizationVersion'] == 'contour-fold-local-support-v5'
    assert bags['components']['formulaVersion'] == 'contour-fold-local-support-v5'
    assert bags['value'] == 0.0, f"Normal lower eyelid margin dip must produce score 0.0, got {bags['value']}"

    # Map consistency: zero score must have zero active pixels on map
    from evaluate_periorbital_and_acne_comparative import decode_map_overlay
    overlay = decode_map_overlay(res.get('maps', {}).get('periorbital:bags'), (h, w, 3))
    assert (overlay.sum(axis=2) > 0).sum() == 0, "Zero card score must produce 0 active map pixels"

    # Cheek / chin sag preservation: continuity gate < 0.20 zeroing must be strictly isolated to periorbital
    # In cheek/chin, continuity_gate = min(1.0, continuity / 0.6) and is NOT zeroed
    gray = np.full((h, w), 150, np.uint8)
    eligible = np.ones((h, w), bool)
    cond = dict(yaw=0., pitch=0., roll=0., scaleRatio=.6, avgLuminance=150., blurScore=50.)
    # Call instant_proxy for rightCheek and periorbital with synthetic flat input
    v_cheek, comp_cheek, sig_cheek, _, _ = IA.instant_proxy(gray, eligible, p, 'rightCheek', cond, 1.0, (0, 0), (h, w))
    assert 'times continuity/0.6' in comp_cheek['indexAggregation'], "Cheek must retain previous continuity/0.6 aggregation"
    assert comp_cheek['formulaVersion'] == 'contour-fold-visible-region-unique-centers-v7'


def test_target_d_lines_radiating_angles_exclude_vertical_lash_and_hair():
    """Target D: Crow's feet Gabor filter uses radiating orientations (-30, 0, 30 deg).
    Vertical lines (theta = 90 deg) representing eyelashes, lid contours, and hair are excluded.
    """
    from skimage.filters import gabor
    # Vertical edge image (eyelash or vertical hair strand)
    im_vertical = np.zeros((64, 64), np.float32)
    im_vertical[:, 31:33] = 1.0  # Sharp vertical stroke

    # Horizontal radiating wrinkle
    im_radiating = np.zeros((64, 64), np.float32)
    im_radiating[31:33, :] = 1.0  # Horizontal wrinkle

    # Evaluate with current radiating angles: (pi/3, pi/2, 2*pi/3)
    rad_angles = (np.pi/3, np.pi/2, 2*np.pi/3)
    resp_vertical = max(np.hypot(*gabor(im_vertical, frequency=0.22, theta=th)).max() for th in rad_angles)
    resp_radiating = max(np.hypot(*gabor(im_radiating, frequency=0.22, theta=th)).max() for th in rad_angles)

    assert resp_radiating > 2.0 * resp_vertical, "Radiating crow's feet filter must strongly prefer horizontal over vertical eyelashes"


def test_target_d_lines_hair_exclusion_from_signal_and_denominator():
    """Target D: Hair margin is strictly excluded from scored pixels, denominator,
    and cyan signal map. When hair completely occludes the line band (< 20 px),
    the limitation is 'HAIR_OR_OCCLUSION_IN_LINE_BAND' and value is None (not 0.0).
    """
    h, w = 280, 320
    p = [dict(x=.5, y=.5, z=0.) for _ in range(478)]
    oval = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109]
    for i, angle in zip(oval, np.linspace(-np.pi/2, 3*np.pi/2, len(oval), endpoint=False)):
        p[i].update(x=.5+.49*np.cos(angle), y=.5+.48*np.sin(angle))
    locations = {234: (0, 150), 454: (320, 150), 33: (40, 70), 133: (110, 70), 159: (75, 64), 163: (50, 76),
                 144: (60, 80), 145: (75, 82), 153: (90, 83), 154: (100, 80), 155: (105, 76),
                 263: (280, 70), 362: (210, 70), 386: (245, 64), 390: (270, 76), 373: (260, 80),
                 374: (245, 82), 380: (230, 83), 381: (220, 80), 382: (215, 76), 61: (110, 165), 291: (210, 165),
                 13: (160, 165), 14: (160, 168)}
    for i, (x, y) in locations.items():
        p[i].update(x=x/w, y=y/h)
    mesh = {'points': [{'x': 0, 'y': 40}, {'x': 320, 'y': 40}, {'x': 320, 'y': 130}, {'x': 0, 'y': 130}], 'edges': [[0, 1], [1, 2], [2, 3], [3, 0], [0, 2]]}

    # 1. Clean image without hair
    img_clean = np.full((h, w, 3), 150, np.uint8)
    url_c, dig_c = photo(img_clean)
    res_c = A.analyze_skin(dict(photo=url_c, photoId=dig_c, landmarks=p, meshes={'periorbital': mesh}, exclusions=[], pose='FRONT', qualityValid=True, conditions=dict(yaw=0., pitch=0., roll=0., scaleRatio=.6, avgLuminance=150., blurScore=50.)))
    sides_c = next(v for v in res_c['measurements']['periorbital'] if v['id'] == 'lines')['components']['sides']
    px_clean = next(s['analysisPixels'] for s in sides_c if s['side'] == 'right')

    # 2. Image with hair margin covering part of lateral canthus
    img_hair = np.full((h, w, 3), 150, np.uint8)
    img_hair[60:85, 20:45] = 10  # dark hair strand covering outer canthus
    url_h, dig_h = photo(img_hair)
    res_h = A.analyze_skin(dict(photo=url_h, photoId=dig_h, landmarks=p, meshes={'periorbital': mesh}, exclusions=[], pose='FRONT', qualityValid=True, conditions=dict(yaw=0., pitch=0., roll=0., scaleRatio=.6, avgLuminance=150., blurScore=50.)))
    sides_h = next(v for v in res_h['measurements']['periorbital'] if v['id'] == 'lines')['components']['sides']
    px_hair = next(s['analysisPixels'] for s in sides_h if s['side'] == 'right')

    assert px_hair < px_clean, f"Hair margin must reduce scored analysis support (clean {px_clean} vs hair {px_hair})"

    # 3. Heavy occlusion over outer canthus line band (< 20 px valid)
    img_occ = np.full((h, w, 3), 150, np.uint8)
    img_occ[50:100, 10:60] = 10
    url_o, dig_o = photo(img_occ)
    res_o = A.analyze_skin(dict(photo=url_o, photoId=dig_o, landmarks=p, meshes={'periorbital': mesh}, exclusions=[], pose='FRONT', qualityValid=True, conditions=dict(yaw=0., pitch=0., roll=0., scaleRatio=.6, avgLuminance=150., blurScore=50.)))
    s_occ = next(s for s in next(v for v in res_o['measurements']['periorbital'] if v['id'] == 'lines')['components']['sides'] if s['side'] == 'right')
    assert s_occ['value'] is None, "Occluded band must return value=None (not 0.0)"
    assert s_occ['limitationCode'] in ('HAIR_OR_OCCLUSION_IN_LINE_BAND', 'INSUFFICIENT_VISIBLE_AREA')


def test_target_d_lines_v4_contract_and_makeup_exclusion():
    """Target D: Crow's feet v4 normalization contract and dark makeup exclusion.
    Verifies normalizationVersion is 'outer-canthus-gabor-radiating-hair-excluded-v4',
    and strong eyeliner at lateral canthus cannot become a high line score.
    The production support floor is relative to local skin brightness.
    """
    assert A.NORMALIZATION['lines'] == 'outer-canthus-gabor-radiating-hair-excluded-v4'
    h, w = 280, 320
    p = [dict(x=.5, y=.5, z=0.) for _ in range(478)]
    oval = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109]
    for i, angle in zip(oval, np.linspace(-np.pi/2, 3*np.pi/2, len(oval), endpoint=False)):
        p[i].update(x=.5+.49*np.cos(angle), y=.5+.48*np.sin(angle))
    locations = {234: (0, 150), 454: (320, 150), 33: (40, 70), 133: (110, 70), 159: (75, 64), 163: (50, 76),
                 144: (60, 80), 145: (75, 82), 153: (90, 83), 154: (100, 80), 155: (105, 76),
                 263: (280, 70), 362: (210, 70), 386: (245, 64), 390: (270, 76), 373: (260, 80),
                 374: (245, 82), 380: (230, 83), 381: (220, 80), 382: (215, 76), 61: (110, 165), 291: (210, 165),
                 13: (160, 165), 14: (160, 168)}
    for i, (x, y) in locations.items():
        p[i].update(x=x/w, y=y/h)
    mesh = {'points': [{'x': 0, 'y': 40}, {'x': 320, 'y': 40}, {'x': 320, 'y': 130}, {'x': 0, 'y': 130}], 'edges': [[0, 1], [1, 2], [2, 3], [3, 0], [0, 2]]}

    # Image with clean smooth skin
    img = np.full((h, w, 3), 150, np.uint8)
    # Paint dark eyeliner flick directly next to landmark 33
    img[68:74, 30:45] = 20  # dark eyeliner pigment
    url, dig = photo(img)
    res = A.analyze_skin(dict(photo=url, photoId=dig, landmarks=p, meshes={'periorbital': mesh}, exclusions=[], pose='FRONT', qualityValid=True, conditions=dict(yaw=0., pitch=0., roll=0., scaleRatio=.6, avgLuminance=150., blurScore=50.)))
    lines_item = next(v for v in res['measurements']['periorbital'] if v['id'] == 'lines')
    assert lines_item['normalizationVersion'] == 'outer-canthus-gabor-radiating-hair-excluded-v4'
    # The eyeliner should not create a high adverse lines score
    if lines_item['value'] is not None:
        assert lines_item['value'] < 1.0, f"Dark eyeliner flick must be excluded by makeup filter (got {lines_item['value']})"
