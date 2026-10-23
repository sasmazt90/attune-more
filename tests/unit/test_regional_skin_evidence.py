"""Synthetic policy fixtures test the contract, not model accuracy/calibration."""
import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'services/core-api'))
import regional_skin_evidence as R
import local_skin_type as T


def policies():
    # Deliberately synthetic; never installed in the product registry.
    return {k: dict(methodVersion='fixture-' + k, normalizationVersion='fixture-scale',
                    validationEvidence='synthetic-test-only', modelHash='fixture-hash',
                    negativeMax=10, positiveMin=30, minCoverage=.8, minAnalysisPixels=100)
            for k in ('oil', 'dry', 'redness')}


def measurements():
    return {region: [dict(id=k, region=region, value=40 if k == 'oil' and region in R.T_ZONE else 0,
                         quality='valid', methodVersion='fixture-' + k,
                         normalizationVersion='fixture-scale', modelHash='fixture-hash',
                         evaluatedArea=dict(scope='anatomical-region', region=region,
                                            sourcePixels=900, anatomicalSourcePixels=1000,
                                            analysisPixels=200))
                     for k in ('oil', 'dry', 'redness')] for region in R.REGIONS}


def row(data, region, criterion):
    return next(r for r in data[region] if r['id'] == criterion)


def test_default_registry_cannot_promote_fixtures_or_legacy_proxies():
    result = R.build_regional_map(measurements())
    assert not result['complete'] and not result['combinationMatched']
    assert all(r['state'] == 'unknown' and r['fill'] == 'lightgrey'
               for r in result['regions'].values())


def test_supported_combination_uses_anatomical_t_zone_and_both_cheeks():
    data = measurements()
    row(data, 'leftCheek', 'dry')['value'] = 40
    result = R.build_regional_map(data, policies())
    assert result['complete'] and result['combinationMatched']
    assert result['regions']['leftCheek']['fill'] == 'blue'
    assert result['regions']['rightCheek']['state'] == 'normal'
    assert result['regions']['rightCheek']['fill'] is None
    assert all(result['regions'][r]['fill'] == 'green' for r in R.T_ZONE)
    assert result['confidence'] is None and not result['sensitivityInferred']


@pytest.mark.parametrize('region', R.T_ZONE)
def test_each_t_zone_region_needs_oily_support(region):
    data = measurements()
    row(data, region, 'oil')['value'] = 0
    assert not R.build_regional_map(data, policies())['combinationMatched']


@pytest.mark.parametrize('region', R.OUTSIDE_T)
def test_oily_cheek_prevents_combination(region):
    data = measurements()
    row(data, region, 'oil')['value'] = 40
    assert not R.build_regional_map(data, policies())['combinationMatched']


def test_redness_is_independent_and_does_not_hide_dryness():
    data = measurements()
    row(data, 'leftCheek', 'dry')['value'] = 40
    row(data, 'leftCheek', 'redness')['value'] = 40
    left = R.build_regional_map(data, policies())['regions']['leftCheek']
    assert left['fill'] == 'blue' and left['redness']['colour'] == 'red'
    assert left['redness']['style'] == 'contour-or-hatching'
    # Missing redness never implies absent redness or changes oil/dry truth.
    data['leftCheek'] = [r for r in data['leftCheek'] if r['id'] != 'redness']
    left = R.build_regional_map(data, policies())['regions']['leftCheek']
    assert left['fill'] == 'blue' and left['redness']['state'] == 'unknown'


@pytest.mark.parametrize('value', [None, True, float('nan'), float('inf'), -1, 101, '0'])
def test_invalid_measurement_is_unknown_never_normal(value):
    data = measurements()
    row(data, 'leftCheek', 'oil')['value'] = value
    result = R.build_regional_map(data, policies())
    assert result['regions']['leftCheek']['fill'] == 'lightgrey'
    assert not result['combinationMatched']


@pytest.mark.parametrize('mutation', ['missing', 'duplicate', 'quality', 'scope', 'region',
                                   'coverage', 'pixels', 'area-overflow', 'bool-area',
                                   'method', 'normalization', 'hash', 'limitation'])
def test_unsupported_inputs_fail_closed(mutation):
    data = measurements()
    r = row(data, 'leftCheek', 'oil')
    if mutation == 'missing': data.pop('leftCheek')
    elif mutation == 'duplicate': data['leftCheek'].append(copy.deepcopy(r))
    elif mutation == 'quality': r['quality'] = 'insufficient'
    elif mutation == 'scope': r['evaluatedArea']['scope'] = 'forehead-union-nose'
    elif mutation == 'region': r['evaluatedArea']['region'] = 'rightCheek'
    elif mutation == 'coverage': r['evaluatedArea']['sourcePixels'] = 799
    elif mutation == 'pixels': r['evaluatedArea']['analysisPixels'] = 99
    elif mutation == 'area-overflow': r['evaluatedArea']['sourcePixels'] = 1001
    elif mutation == 'bool-area': r['evaluatedArea']['sourcePixels'] = True
    elif mutation == 'method': r['methodVersion'] = 'different'
    elif mutation == 'normalization': r['normalizationVersion'] = 'different'
    elif mutation == 'hash': r['modelHash'] = 'different'
    elif mutation == 'limitation': r['limitationCode'] = 'GLARE'
    result = R.build_regional_map(data, policies())
    assert result['regions']['leftCheek']['state'] == 'unknown'
    assert not result['complete'] and not result['combinationMatched']


@pytest.mark.parametrize('field,value', [('negativeMax', 30), ('positiveMin', 10),
                                      ('minCoverage', 0), ('minCoverage', float('nan')),
                                      ('minAnalysisPixels', 99), ('validationEvidence', '')])
def test_invalid_acceptance_policy_is_not_used(field, value):
    policy = policies()
    policy['oil'][field] = value
    result = R.build_regional_map(measurements(), policy)
    assert all(r['state'] == 'unknown' for r in result['regions'].values())


def test_indeterminate_range_and_conflicting_aggregates_are_grey():
    data = measurements()
    row(data, 'leftCheek', 'oil')['value'] = 20
    row(data, 'rightCheek', 'oil')['value'] = 40
    row(data, 'rightCheek', 'dry')['value'] = 40
    result = R.build_regional_map(data, policies())
    assert result['regions']['leftCheek']['fill'] == 'lightgrey'
    assert result['regions']['rightCheek']['fill'] == 'lightgrey'
    assert 'CONFLICTING' in result['regions']['rightCheek']['reason']


def test_boundary_values_and_input_immutability():
    data, policy = measurements(), policies()
    row(data, 'nose', 'oil')['value'] = 30
    row(data, 'nose', 'dry')['value'] = 10
    row(data, 'nose', 'oil')['evaluatedArea']['sourcePixels'] = 800
    original = copy.deepcopy((data, policy))
    assert R.build_regional_map(data, policy)['combinationMatched']
    assert (data, policy) == original


@pytest.mark.parametrize('global_value', ['normal', 'dry', 'oily'])
def test_final_product_type_obeys_accepted_map_and_retracts_when_coverage_lost(monkeypatch, global_value):
    monkeypatch.setattr(R, 'ACCEPTED_METHODS', policies())
    base = dict(value=global_value, quality='valid', confidence=.8, methodVersion='fixture-base',
                modelHash='base-hash', inferenceKind='local-onnx')
    result = dict(general=dict(skinType=base, measurements=[]), measurements=measurements(), maps={})
    T.finalize_product_type(result)
    assert result['general']['skinType']['value'] == 'combination'
    first = copy.deepcopy(result)
    T.finalize_product_type(result)
    assert result == first
    row(result['measurements'], 'chin', 'oil')['quality'] = 'insufficient'
    T.finalize_product_type(result)
    assert result['general']['skinType']['value'] == global_value
    assert result['general']['skinType']['confidence'] == .8
    assert result['general']['regionalSkinMap']['regions']['chin']['fill'] == 'lightgrey'
    assert not result['general']['skinType']['decisionTrace']['applied']
    assert result['activeCriterionMethods']['criteria']['type']['overview']['methodVersion'].endswith(T.RULE)


@pytest.mark.parametrize('bad', [None, [], {'leftCheek': None}])
def test_missing_input_produces_unknown_map(bad):
    assert not R.build_regional_map(bad, policies())['complete']
