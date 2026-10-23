"""Product-heading semantics shared by the local skin result builders.

Tone is a broad chromatic-variation proxy. Post-acne marks and pigmentation are
localized instance concerns and must never be populated from the tone proxy.
"""

PRODUCT_APPEARANCE_IDS = (
    'tone', 'oil', 'redness', 'acne', 'sag', 'dry', 'lines', 'dark', 'bags',
    'postAcne', 'pigmentation',
)
PRODUCT_HEADING_COUNT_WITH_SKIN_TYPE = len(PRODUCT_APPEARANCE_IDS) + 1
SEPARATION_VERSION = 'tone-localized-pigmentation-separation-v1'

LOCALIZED_CONCERNS = {
    'postAcne': {
        'meaning': 'localized-visible-post-acne-mark-instances',
        'reason': 'ACCEPTED_POST_ACNE_LOCAL_DETECTOR_NOT_AVAILABLE',
        'target': 'post-acne-mark-instance',
    },
    'pigmentation': {
        'meaning': 'localized-visible-pigmentation-instances',
        'reason': 'ACCEPTED_PIGMENTATION_LOCAL_DETECTOR_NOT_AVAILABLE',
        'target': 'pigmentation-instance',
    },
}


def general_concern_contract(criterion):
    localized = LOCALIZED_CONCERNS.get(criterion)
    if not localized:
        return {
            'type': 'appearance_proxy',
            'unit': 'appearance-score-0-100',
            'methodVersion': None,
            'normalizationVersion': None,
            'limitationCode': 'INSUFFICIENT_FRONT_COVERAGE',
            'components': {},
        }
    return {
        'type': 'trained_prediction',
        'unit': 'candidate-count',
        'methodVersion': 'localized-concern-unavailable-v1',
        'normalizationVersion': 'localized-instance-count-v1',
        'limitationCode': localized['reason'],
        'components': {
            'target': localized['target'],
            'concernMeaning': localized['meaning'],
            'separationVersion': SEPARATION_VERSION,
            'derivedFromTone': False,
            'localizedInstancesAvailable': False,
        },
    }


def tone_separation_components(components=None, localized_support_excluded=False):
    return {
        **(components or {}),
        'concernMeaning': 'broad-regional-chromatic-variation',
        'separationVersion': SEPARATION_VERSION,
        'localizedPigmentationSupportExcluded': bool(localized_support_excluded),
        'toneCanSupplyLocalizedPigmentation': False,
        'coReportingPolicy': 'separate-headings-no-local-result-from-tone',
    }
