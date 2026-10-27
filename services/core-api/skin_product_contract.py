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
SAG_APPEARANCE_SEMANTICS = 'visible-lower-face-contour-fold-appearance-v1'
SAG_COMPARISON_MODE = 'same-person-compatible-capture-only'
GENERIC_DEGREE_BLOCKED_TARGETS = {
    'sag': 'WHOLE_FACE_ORDINAL_SAG_NOT_A_LOCAL_APPEARANCE_TARGET',
}

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


def sag_appearance_components(components=None):
    return {
        **(components or {}),
        'appearanceSemantics': SAG_APPEARANCE_SEMANTICS,
        'clinicalSeverity': False,
        'elasticity': False,
        'comparisonMode': SAG_COMPARISON_MODE,
    }


def generic_degree_target_policy(head):
    """Return the usable targets of the generic whole-face ordinal head.

    The source's ``elasticity`` grade is not a localized sag label.  Even if a
    future manifest accidentally lists ``sag`` as accepted, it must not leave
    the model boundary or appear as an unavailable product target.
    """
    if head.get('accepted') is not True:
        return {'acceptedTargets': [], 'blockedTargets': []}
    outputs = set(head.get('targets', ()))
    accepted = []
    blocked = []
    for target in dict.fromkeys(head.get('acceptedTargets', ())):
        reason = GENERIC_DEGREE_BLOCKED_TARGETS.get(target)
        if reason is None and target not in outputs:
            reason = 'ACCEPTED_TARGET_NOT_IN_MODEL_OUTPUTS'
        if reason:
            blocked.append({'target': target, 'reason': reason})
        else:
            accepted.append(target)
    return {'acceptedTargets': accepted, 'blockedTargets': blocked}


def general_concern_contract(criterion):
    localized = LOCALIZED_CONCERNS.get(criterion)
    if not localized:
        return {
            'type': 'appearance_proxy',
            'unit': 'appearance-score-0-100',
            'methodVersion': None,
            'normalizationVersion': None,
            'limitationCode': 'INSUFFICIENT_FRONT_COVERAGE',
            'components': sag_appearance_components() if criterion == 'sag' else {},
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



def learned_degree_replacement_policy(criterion, degree):
    """Whole-face ordinal heads cannot replace localized sag appearance.

    A future accepted localized sag model needs its own localization contract;
    it must not enter through the generic whole-face degree head.
    """
    scope = degree.get('scope')
    if criterion == 'sag':
        return {
            'allowed': False,
            'reason': 'WHOLE_FACE_ORDINAL_CANNOT_REPLACE_LOCAL_SAG',
            'candidateScope': scope,
        }
    return {'allowed': True, 'reason': None, 'candidateScope': scope}


def apply_learned_general_degree(item, degree):
    """Apply a generic learned degree without mixing score and map methods."""
    decision = learned_degree_replacement_policy(item['id'], degree)
    components = item.setdefault('components', {})
    if not decision['allowed']:
        components.update(
            learnedDegreeCandidateBlocked=True,
            learnedDegreeBlockReason=decision['reason'],
            learnedDegreeScope=decision['candidateScope'],
        )
        return False
    item.update(
        value=degree['value'],
        type='trained_prediction',
        methodVersion=degree['methodVersion'],
        modelVersion=degree['methodVersion'],
        modelHash=degree['modelHash'],
        quality='valid',
        limitationCode=None,
        normalizationVersion=degree['normalizationVersion'],
        uncertainty=['source-label-protocol-unverified', 'camera-domain-shift'],
        localMap=None,
    )
    components.update(
        rawGrade=degree['rawGrade'],
        normalizationVersion=degree['normalizationVersion'],
        modelScope=degree.get('scope', 'whole-face'),
        pixelLocalizationAvailable=False,
    )
    return True

def tone_separation_components(components=None, localized_support_excluded=False):
    return {
        **(components or {}),
        'concernMeaning': 'broad-regional-chromatic-variation',
        'separationVersion': SEPARATION_VERSION,
        'localizedPigmentationSupportExcluded': bool(localized_support_excluded),
        'toneCanSupplyLocalizedPigmentation': False,
        'coReportingPolicy': 'separate-headings-no-local-result-from-tone',
    }
