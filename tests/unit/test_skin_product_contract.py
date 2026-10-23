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
