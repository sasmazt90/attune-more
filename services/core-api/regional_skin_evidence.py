"""Regional appearance decisions from explicitly accepted, calibrated methods.

This is a region summary, not a segmentation mask. The registry is deliberately
empty until held-out and camera evidence supports a method/threshold/coverage
combination. It is server-owned and never populated from request data, global
skin-type predictions, absent annotations, or the legacy visible-support proxy.
"""
import math

VERSION = 'regional-skin-evidence-v1'
REGIONS = ('forehead', 'nose', 'chin', 'leftCheek', 'rightCheek')
T_ZONE = ('forehead', 'nose', 'chin')
OUTSIDE_T = ('leftCheek', 'rightCheek')
ACCEPTED_METHODS = {}
COLOURS = {'dry': 'blue', 'oily': 'green', 'normal': None, 'unknown': 'lightgrey'}


def number(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def observe(rows, criterion, region, policies):
    """No zero-as-normal shortcut; a calibrated negative needs its own evidence."""
    found = [row for row in rows if isinstance(row, dict) and row.get('id') == criterion]
    if len(found) != 1:
        return {'state': 'unknown', 'reason': 'MISSING_OR_AMBIGUOUS_MEASUREMENT'}
    row = found[0]
    policy = policies.get(criterion)
    if not isinstance(policy, dict):
        return {'state': 'unknown', 'reason': 'REGIONAL_METHOD_NOT_ACCEPTED'}
    required = ('methodVersion', 'normalizationVersion', 'validationEvidence')
    if (not all(isinstance(policy.get(k), str) and policy[k] for k in required)
            or any(row.get(k) != policy[k] for k in required[:2])
            or row.get('modelHash') != policy.get('modelHash')):
        return {'state': 'unknown', 'reason': 'REGIONAL_METHOD_IDENTITY_MISMATCH'}
    low, high = policy.get('negativeMax'), policy.get('positiveMin')
    coverage_min, pixels_min = policy.get('minCoverage'), policy.get('minAnalysisPixels')
    if (not all(number(v) for v in (low, high, coverage_min, pixels_min))
            or not 0 <= low < high <= 100 or not 0 < coverage_min <= 1
            or pixels_min < 100):
        return {'state': 'unknown', 'reason': 'REGIONAL_POLICY_INVALID'}
    value = row.get('value')
    if (row.get('quality') != 'valid' or row.get('limitationCode')
            or not number(value) or not 0 <= value <= 100):
        return {'state': 'unknown', 'reason': 'REGIONAL_MEASUREMENT_UNAVAILABLE'}
    area = row.get('evaluatedArea')
    if not isinstance(area, dict):
        return {'state': 'unknown', 'reason': 'REGIONAL_COVERAGE_UNAVAILABLE'}
    source, anatomy, pixels = (area.get(k) for k in
                              ('sourcePixels', 'anatomicalSourcePixels', 'analysisPixels'))
    # Union ROIs, including the legacy nose+forehead oil ROI, cannot be treated
    # as a separate supported anatomical nose or counted twice in the T-zone.
    if (row.get('region') != region or area.get('scope') != 'anatomical-region'
            or area.get('region') != region):
        return {'state': 'unknown', 'reason': 'REGIONAL_SCOPE_MISMATCH'}
    if (not all(number(v) for v in (source, anatomy, pixels))
            or not 0 < source <= anatomy or pixels < pixels_min
            or source / anatomy < coverage_min):
        return {'state': 'unknown', 'reason': 'INSUFFICIENT_REGIONAL_COVERAGE'}
    state = 'positive' if value >= high else 'negative' if value <= low else 'unknown'
    return {'state': state, 'reason': 'REGIONAL_INDETERMINATE_RANGE' if state == 'unknown' else None,
            'coverage': source / anatomy, 'methodVersion': policy['methodVersion'],
            'normalizationVersion': policy['normalizationVersion'],
            'modelHash': policy.get('modelHash'), 'validationEvidence': policy['validationEvidence']}


def build_regional_map(measurements, policies=None):
    """Keep redness independent. Normal requires supported oil AND dry negatives.

    Policy injection is for offline evaluation; the product uses only the pinned
    server registry above. Test policies are not acceptance or fitted cutoffs.
    """
    policies = ACCEPTED_METHODS if policies is None else policies
    policies = policies if isinstance(policies, dict) else {}
    if not isinstance(measurements, dict):
        measurements = {}
    regions = {}
    for region in REGIONS:
        rows = measurements.get(region, [])
        if not isinstance(rows, list):
            rows = []
        observations = {key: observe(rows, key, region, policies)
                        for key in ('oil', 'dry', 'redness')}
        oil, dry = (observations[k]['state'] for k in ('oil', 'dry'))
        state, reason = 'unknown', 'REGIONAL_EVIDENCE_INCOMPLETE'
        if oil == 'negative' and dry == 'negative':
            state, reason = 'normal', None
        elif oil == 'positive' and dry == 'negative':
            state, reason = 'oily', None
        elif oil == 'negative' and dry == 'positive':
            state, reason = 'dry', None
        elif oil == 'positive' and dry == 'positive':
            reason = 'CONFLICTING_REGION_AGGREGATES_REQUIRE_LOCAL_SUPPORT'
        red = observations['redness']['state']
        regions[region] = {'state': state, 'fill': COLOURS[state], 'reason': reason,
                           'redness': {'state': red, 'colour': 'red' if red == 'positive' else None,
                                       'style': 'contour-or-hatching'},
                           'observations': observations}
    complete = all(row['state'] != 'unknown' for row in regions.values())
    combination = (complete and all(regions[r]['state'] == 'oily' for r in T_ZONE)
                   and all(regions[r]['state'] in ('normal', 'dry') for r in OUTSIDE_T))
    return {'version': VERSION, 'geometry': 'anatomical-region-summary-not-pixel-mask',
            'regions': regions, 'complete': complete, 'combinationMatched': combination,
            'tZone': list(T_ZONE), 'outsideTZone': list(OUTSIDE_T),
            'confidence': None, 'sensitivityInferred': False}
