import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'services/core-api'))
import skin_product_contract as C


def test_product_has_eleven_appearance_headings_plus_skin_type():
    assert len(C.PRODUCT_APPEARANCE_IDS) == 11
    assert C.PRODUCT_HEADING_COUNT_WITH_SKIN_TYPE == 12
    assert C.PRODUCT_APPEARANCE_IDS[-2:] == ('postAcne', 'pigmentation')


def test_localized_concerns_are_explicitly_unavailable_not_derived_from_tone():
    for criterion in ('postAcne', 'pigmentation'):
        value = C.general_concern_contract(criterion)
        assert value['type'] == 'trained_prediction'
        assert value['unit'] == 'candidate-count'
        assert value['limitationCode'].startswith('ACCEPTED_')
        assert value['components']['derivedFromTone'] is False
        assert value['components']['localizedInstancesAvailable'] is False


def test_tone_contract_never_supplies_localized_pigmentation():
    value = C.tone_separation_components({'colorSpace': 'CIELAB a*,b*'})
    assert value['concernMeaning'] == 'broad-regional-chromatic-variation'
    assert value['toneCanSupplyLocalizedPigmentation'] is False
    assert value['localizedPigmentationSupportExcluded'] is False
    assert value['coReportingPolicy'] == 'separate-headings-no-local-result-from-tone'



def test_sag_is_appearance_only_even_when_unavailable():
    value = C.general_concern_contract('sag')
    assert value['components'] == {
        'appearanceSemantics': C.SAG_APPEARANCE_SEMANTICS,
        'clinicalSeverity': False,
        'elasticity': False,
        'comparisonMode': C.SAG_COMPARISON_MODE,
    }

def test_existing_concerns_keep_existing_general_defaults():
    value = C.general_concern_contract('tone')
    assert value['type'] == 'appearance_proxy'
    assert value['unit'] == 'appearance-score-0-100'
    assert value['methodVersion'] is None


def _degree(value=80):
    return {
        'value': value,
        'rawGrade': value / 20,
        'methodVersion': 'whole-face-ordinal-test-v1',
        'modelHash': 'test-hash',
        'normalizationVersion': 'ordinal-0-5-times-20-v1',
        'scope': 'whole-face',
    }


def test_whole_face_ordinal_sag_cannot_replace_local_contour_or_map():
    local_map = {'key': 'overview:sag'}
    item = {
        'id': 'sag',
        'value': 12,
        'type': 'appearance_proxy',
        'methodVersion': 'local-contour-v1',
        'modelHash': None,
        'localMap': local_map,
        'components': C.sag_appearance_components(),
    }
    assert C.apply_learned_general_degree(item, _degree()) is False
    assert item['value'] == 12
    assert item['methodVersion'] == 'local-contour-v1'
    assert item['modelHash'] is None
    assert item['localMap'] is local_map
    assert item['components']['learnedDegreeCandidateBlocked'] is True
    assert item['components']['learnedDegreeBlockReason'] == 'WHOLE_FACE_ORDINAL_CANNOT_REPLACE_LOCAL_SAG'
    assert item['components']['learnedDegreeScope'] == 'whole-face'


def test_nonlocal_degree_clears_any_unrelated_analytic_map():
    item = {'id': 'redness', 'value': 4, 'localMap': {'key': 'overview:redness'}, 'components': {}}
    assert C.apply_learned_general_degree(item, _degree(60)) is True
    assert item['value'] == 60
    assert item['type'] == 'trained_prediction'
    assert item['localMap'] is None
    assert item['components']['modelScope'] == 'whole-face'
    assert item['components']['pixelLocalizationAvailable'] is False


def test_appearance_analysis_wires_policy_and_defensive_sag_map_gate():
    source = (ROOT / 'services/core-api/appearance_analysis.py').read_text('utf8')
    assert 'apply_learned_general_degree(item,degree)' in source
    assert "sag_overview['components'].get('modelScope')!='whole-face'" in source
