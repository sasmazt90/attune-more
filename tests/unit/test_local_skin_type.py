import copy, sys
from pathlib import Path
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'services/core-api'))
import local_skin_type as T

NEG_METHODS = {'preserved', 'appearance-native-dry-2', 'appearance-cv-6', 'appearance-native-dry-3'}


def rows(oil=0, dry=0, redness=0):
    area = dict(sourcePixels=200, analysisPixels=200, foreheadSourcePixels=100, noseSourcePixels=100)
    out = [dict(id=k, value=v, quality='valid', methodVersion='preserved', evaluatedArea=area) for k, v in [('oil', oil), ('dry', dry)]]
    if redness is not None:
        out.append(dict(id='redness', value=redness, quality='valid', methodVersion='preserved', evaluatedArea=area))
    return out


def base(value='normal'):
    return dict(value=value, quality='valid', confidence=.8, methodVersion='new-local', modelHash='a' * 64)


def regions(dry=0):
    return dict(nose=rows(10), forehead=rows(10), leftCheek=rows(0, dry), rightCheek=rows(0, dry), chin=rows(0, dry))


@pytest.mark.parametrize('dry', [0, 4])
@pytest.mark.parametrize('global_value', ['normal', 'dry', 'oily'])
def test_user_combination_rule_overrides_all_global_argmax(dry, global_value):
    # With positive dry cheeks (dry=4), combination works even without accepted negative methods;
    # with dry=0, combination works when an accepted negative method confirms normal cheeks.
    neg = set() if dry >= 2 else NEG_METHODS
    value = T.regional_decision(base(global_value), regions(dry), accepted_negative_methods=neg)
    assert value['value'] == 'combination' and value['confidence'] is None and value['decisionTrace']['applied']


def test_all_face_oily_is_not_combination():
    r = regions()
    r.update(leftCheek=rows(10), rightCheek=rows(10), chin=rows(10))
    assert T.regional_decision(base('oily'), r)['value'] == 'oily'


@pytest.mark.parametrize('failure', ['missing', 'invalid', 'nan', 'no-area'])
def test_unknown_region_is_not_normal(failure):
    r = regions()
    if failure == 'missing':
        r.pop('leftCheek')
    elif failure == 'invalid':
        r['leftCheek'][0]['quality'] = 'insufficient'
    elif failure == 'nan':
        r['leftCheek'][0]['value'] = float('nan')
    else:
        r['leftCheek'][0]['evaluatedArea'] = {}
    result = T.regional_decision(base('dry'), r)
    assert result['value'] is None and result['quality'] == 'insufficient' and result['confidence'] is None
    assert result['limitationCode'] == 'INCOMPLETE_CHEEKS_UNVERIFIED'
    assert not result['decisionTrace']['complete'] and not result['decisionTrace']['applied']


def test_no_model_is_not_silently_replaced_by_rule():
    assert T.regional_decision(T.unavailable('MISSING'), regions())['value'] is None


def test_no_input_mutation():
    b = base()
    r = regions(4)
    original = copy.deepcopy((b, r))
    T.regional_decision(b, r)
    assert (b, r) == original


def test_missing_weights_and_invalid_image_never_network(monkeypatch, tmp_path):
    monkeypatch.setattr(T, 'CONFIG', tmp_path / 'absent.json')
    result = T.infer(np.zeros((32, 32, 3), np.uint8))
    assert result['value'] is None and result['quality'] == 'insufficient'
    assert T.infer(None)['value'] is None


def test_product_selector_uses_only_local_fallback(monkeypatch):
    import skin_models as M
    monkeypatch.setattr(M, 'load', lambda: dict(sessions={}))
    monkeypatch.setattr(M, 'infer_local_type', lambda crop: dict(**base('oily'), inferenceMs=1., inferenceKind='local-onnx', fileHashVerified=True, sessionLoaded=True))
    monkeypatch.setattr(M, 'infer_hosted_type', lambda *a, **k: pytest.fail('Hosted branch must not run'))
    p = [dict(x=.2 + (i % 2) * .6, y=.2 + (i % 3) * .2) for i in range(468)]
    assert M.infer(np.zeros((320, 320, 3), np.uint8), p, True, True)['skinType']['value'] == 'oily'


def product_result(dry=4):
    return dict(general=dict(skinType={**base('oily'), 'inferenceKind': 'local-onnx'}, measurements=[]), measurements=regions(dry), maps={})


def test_final_native_zero_replaces_old_positive_trace_without_reinference(monkeypatch):
    monkeypatch.setattr(T, 'infer', lambda *_: pytest.fail('Finalization must not run model'))
    r = product_result(4)
    old = T.regional_decision(r['general']['skinType'], r['measurements'])
    r['general']['skinType'] = old
    for rows_ in r['measurements'].values():
        row = next(x for x in rows_ if x['id'] == 'dry')
        row.update(value=0, methodVersion='appearance-native-dry-2', normalizationVersion='native-final')
    # Without accepted negative evidence method, dry=0 and oil=0 on cheeks returns unevaluated (never normal)
    result_unverified = T.finalize_product_type(copy.deepcopy(r), accepted_negative_methods=set())
    t_unv = result_unverified['general']['skinType']
    assert t_unv['value'] is None
    assert t_unv['decisionTrace']['regions']['rightCheek']['state'] == 'unevaluated'

    # With accepted negative evidence method, dry=0 and oil=0 on cheeks confirms normal cheeks -> combination
    result = T.finalize_product_type(r, accepted_negative_methods=NEG_METHODS)
    t = result['general']['skinType']
    assert t['value'] == 'combination' and t['basePrediction']['value'] == 'oily'
    assert t['decisionTrace']['regions']['rightCheek']['dry']['value'] == 0
    assert t['decisionTrace']['regions']['rightCheek']['state'] == 'normal'
    assert t['decisionTrace']['regions']['rightCheek']['dry']['methodVersion'] == 'appearance-native-dry-2'
    assert t['decisionTrace']['regions']['rightCheek']['dry']['quality'] == 'valid'
    assert result['activeCriterionMethods']['criteria']['type']['overview']['methodVersion'] == t['methodVersion'] == t['modelVersion']
    assert t['methodVersion'].count(T.RULE) == 1


@pytest.mark.parametrize('failure', ['invalid', 'missing'])
def test_final_invalid_or_missing_retracts_previously_matched_combination(failure):
    r = product_result(4)
    r['general']['skinType'] = T.regional_decision(r['general']['skinType'], r['measurements'])
    if failure == 'missing':
        r['measurements']['leftCheek'] = [row for row in r['measurements']['leftCheek'] if row['id'] != 'dry']
    else:
        next(row for row in r['measurements']['leftCheek'] if row['id'] == 'dry').update(value=None, quality='insufficient', methodVersion='appearance-native-dry-2')
    result = T.finalize_product_type(r)
    t = result['general']['skinType']
    assert t['value'] is None and t['quality'] == 'insufficient' and t['confidence'] is None
    assert t['limitationCode'] == 'INCOMPLETE_CHEEKS_UNVERIFIED'
    assert not t['decisionTrace']['complete'] and not t['decisionTrace']['applied']
    assert t['decisionTrace']['regions']['leftCheek']['state'] is None
    assert t['decisionTrace']['regions']['leftCheek']['inputs']['dry'] == (None if failure == 'missing' else {k: next(row for row in r['measurements']['leftCheek'] if row['id'] == 'dry').get(k) for k in ['value', 'quality', 'methodVersion', 'normalizationVersion', 'evaluatedArea', 'limitationCode']})


def test_product_finalization_is_idempotent_and_preserves_base():
    r = product_result(4)
    before = copy.deepcopy(r['measurements'])
    T.finalize_product_type(r)
    first = copy.deepcopy(r)
    T.finalize_product_type(r)
    assert r == first and r['general']['skinType']['value'] == 'combination'
    assert r['general']['skinType']['basePrediction'] == {**base('oily'), 'inferenceKind': 'local-onnx'}
    for region, original in before.items():
        for old, current in zip(original, r['measurements'][region]):
            assert all(current[k] == v for k, v in old.items())


def test_legacy_derived_combination_is_never_treated_as_base_model():
    b = {**base('normal'), 'value': 'combination', 'decisionTrace': {'baseValue': 'oily'}}
    assert T.regional_decision(b, regions(4))['value'] is None


def test_normal_endpoint_finalizes_after_all_product_replacements(monkeypatch):
    import asyncio, local_health as L, product_dryness as P, acne_v5_product as A
    monkeypatch.setattr(L, 'parked', lambda: True)
    monkeypatch.setattr(L, 'skin_geometry', lambda _: None)
    async def payload(_):
        return {'experimentalAcneV5': True}
    monkeypatch.setattr(L, 'payload', payload)
    monkeypatch.setattr(L, 'skin_capture_preflight', lambda _: dict(version='preserved', modelHash='eyewear'))
    events = []
    def product(*_):
        events.append('native-dry')
        return product_result(4)
    def acne(r, *_):
        events.append('acne')
        next(row for row in r['measurements']['leftCheek'] if row['id'] == 'dry').update(value=None, quality='insufficient')
        return r
    monkeypatch.setattr(P, 'analyze_product', product)
    monkeypatch.setattr(A, 'replace_acne', acne)
    class Request:
        async def is_disconnected(self):
            return False
    async def run():
        L._busy = asyncio.Lock()
        return await L.skin(Request())
    result = asyncio.run(run())
    assert events == ['native-dry', 'acne']
    assert result['general']['skinType']['value'] is None and result['general']['skinType']['quality'] == 'insufficient'
    assert not result['general']['skinType']['decisionTrace']['complete']
    assert result['activeCriterionMethods']['criteria']['type']['overview']['methodVersion'].endswith(T.RULE)


def test_combination_includes_chin_oil_with_forehead_or_nose_2of3():
    r = dict(nose=rows(10, 0), forehead=rows(0, 0), chin=rows(12, 0), leftCheek=rows(0.2, 3.0), rightCheek=rows(0.1, 3.2))
    res = T.regional_decision(base('normal'), r)
    assert res['value'] == 'combination'
    assert res['decisionTrace']['applied'] is True
    assert res['decisionTrace']['tZone']['valid'] is True
    assert set(res['decisionTrace']['tZone']['oilyRegions']) == {'nose', 'chin'}


def test_chin_only_oil_or_tiny_noise_oil_is_never_combination():
    # Only chin oily (1/3 of T-zone) -> NOT combination
    r_chin_only = dict(nose=rows(0, 0), forehead=rows(0, 0), chin=rows(8.0, 0), leftCheek=rows(0, 0), rightCheek=rows(0, 0))
    res1 = T.regional_decision(base('normal'), r_chin_only, accepted_negative_methods=NEG_METHODS)
    assert res1['value'] != 'combination'
    assert res1['decisionTrace']['tZone']['state'] == 'non-oily'
    # Tiny 0.01% oil on forehead and nose -> NOT combination
    r_tiny = dict(nose=rows(0.01, 0), forehead=rows(0.01, 0), chin=rows(0, 0), leftCheek=rows(0, 0), rightCheek=rows(0, 0))
    res2 = T.regional_decision(base('dry'), r_tiny, accepted_negative_methods=NEG_METHODS)
    assert res2['value'] == 'normal'
    assert res2['decisionTrace']['tZone']['state'] == 'non-oily'
    # Missing chin -> T-zone incomplete -> value is None
    r_no_chin = dict(nose=rows(10, 0), forehead=rows(10, 0), leftCheek=rows(0, 0), rightCheek=rows(0, 0))
    res3 = T.regional_decision(base('normal'), r_no_chin)
    assert res3['value'] is None and res3['quality'] == 'insufficient'
    assert res3['limitationCode'] == 'INCOMPLETE_TZONE_UNVERIFIED'
    assert res3['decisionTrace']['complete'] is False


def test_missing_cheek_withholds_value_and_flags_incomplete_limitation():
    r = regions(dry=4)
    r.pop('rightCheek')
    res = T.regional_decision(base('dry'), r)
    assert res['value'] is None
    assert res['quality'] == 'insufficient'
    assert res['confidence'] is None
    assert res['decisionTrace']['limitationCode'] == 'INCOMPLETE_CHEEKS_UNVERIFIED'
    assert res.get('limitationCode') == 'INCOMPLETE_CHEEKS_UNVERIFIED'


def test_scenarios_a_b_c_d_e_contract():
    # Scenario A: 5 regions normal (with accepted negative method), ViT oily -> returns 'normal', NEVER leaks ViT 'oily'!
    r_all_normal = {k: rows(0.2, 0.2) for k in T.REGIONS}
    res_a = T.regional_decision(base('oily'), r_all_normal, accepted_negative_methods=NEG_METHODS)
    assert res_a['value'] == 'normal' and res_a['quality'] == 'valid'

    # Scenario B: 5 regions normal (with accepted negative method), ViT dry -> symmetric with A, returns 'normal'!
    res_b = T.regional_decision(base('dry'), r_all_normal, accepted_negative_methods=NEG_METHODS)
    assert res_b['value'] == 'normal' and res_b['quality'] == 'valid'

    # Scenario A/B without accepted negative method: returns value=None, displayValue='Değerlendirilmedi', NEVER leaks ViT!
    res_unv = T.regional_decision(base('oily'), r_all_normal, accepted_negative_methods=set())
    assert res_unv['value'] is None and res_unv['quality'] == 'insufficient'
    assert res_unv['displayValue'] == 'Değerlendirilmedi'
    assert all(res_unv['decisionTrace']['regions'][k]['state'] == 'unevaluated' for k in T.REGIONS)

    # Scenario C: Every region has oil 1.9% (intermediate band 1.0 < v < 2.0) -> every region returns 'unknown', NEVER 'normal'!
    r_inter = {k: rows(1.9, 0.1) for k in T.REGIONS}
    res_c = T.regional_decision(base('normal'), r_inter, accepted_negative_methods=NEG_METHODS)
    assert res_c['value'] is None and res_c['quality'] == 'insufficient'
    assert res_c['limitationCode'] == 'INTERMEDIATE_BAND_UNDETERMINED'
    assert all(res_c['decisionTrace']['regions'][k]['state'] == 'unknown' for k in T.REGIONS)

    # Scenario D: Mixed regions (forehead oily, chin dry), ViT oily -> returns value=None ('Karışık desen (Belirlenemedi)'), NEVER leaks ViT 'oily'!
    r_mixed = dict(forehead=rows(4.5, 0.1), nose=rows(0.2, 0.1), chin=rows(0.1, 4.0), leftCheek=rows(0.2, 0.1), rightCheek=rows(0.2, 0.1))
    res_d = T.regional_decision(base('oily'), r_mixed, accepted_negative_methods=NEG_METHODS)
    assert res_d['value'] is None and res_d['quality'] == 'insufficient'
    assert res_d['limitationCode'] == 'MIXED_REGIONAL_PATTERN_UNDETERMINED'
    assert res_d['displayValue'] == 'Karışık desen (Belirlenemedi)'

    # Scenario E: Two cheeks have redness = 20 (or 50) -> NEVER produces 'sensitive'!
    r_red = dict(forehead=rows(0.2, 0.1, redness=25), nose=rows(0.2, 0.1, redness=20), chin=rows(0.2, 0.1, redness=18), leftCheek=rows(0.2, 3.5, redness=20), rightCheek=rows(0.2, 3.5, redness=20))
    res_e = T.regional_decision(base('normal'), r_red, accepted_negative_methods=NEG_METHODS)
    assert res_e['value'] != 'sensitive'
    assert all(res_e['decisionTrace']['regions'][k]['state'] != 'sensitive' for k in T.REGIONS)
    assert not hasattr(T, 'SENSITIVE_REDNESS_MIN')
