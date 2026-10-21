"""Small deterministic text rules, not a diagnosis or a clinical risk assessment.

English/German reassurance/history only masks its own bounded phrase.
Independent current-risk clauses remain visible. Turkish emergency rules
stay in the existing detector. The frontend executes these same policies.
"""
import json
from pathlib import Path
import re
import unicodedata

ENGLISH_CRISIS = json.loads((Path(__file__).resolve().parents[2] /
    'shared/localization/english-crisis.json').read_text('utf-8'))
GERMAN_CRISIS = json.loads((Path(__file__).resolve().parents[2] /
    'shared/localization/german-crisis.json').read_text('utf-8'))


def contextual_crisis_context(text, policy):
    value = re.sub(r'\s+', ' ', unicodedata.normalize('NFC', text).lower().replace('’', "'")).strip()
    if not re.search(policy['signal'], value, re.ASCII):
        return {'signal': False, 'context': 'NONE'}
    observed = set()
    for kind in ('reassurance', 'historical', 'uncertain'):
        for pattern in policy[kind]:
            value, count = re.subn(pattern, ' ', value, flags=re.ASCII)
            if count:
                observed.add(kind)
    if any(re.search(policy[key], value, re.ASCII) for key in ('selfDirected', 'currentState')):
        return {'signal': True, 'context': 'CURRENT_RISK_SIGNAL'}
    # A denial or reference to the past is not an all-message safe exemption.
    if observed and re.search(policy['continuedRisk'], value, re.ASCII):
        return {'signal': True, 'context': 'CONTINUING_RISK_SIGNAL'}
    if re.search(policy['signal'], value, re.ASCII):
        return {'signal': False, 'context': 'UNCERTAIN'}
    if observed and re.search(policy['conditional'], value, re.ASCII):
        return {'signal': False, 'context': 'UNCERTAIN'}
    context = 'UNCERTAIN' if 'uncertain' in observed else 'HISTORICAL' if 'historical' in observed else 'REASSURANCE'
    return {'signal': False, 'context': context}


def english_crisis_context(text):
    return contextual_crisis_context(text, ENGLISH_CRISIS)


def german_crisis_context(text):
    return contextual_crisis_context(text, GERMAN_CRISIS)


SUPPORT_RULES = {
    'en': {
        'professional': r'\b(?:psychologists?|psychological (?:support|help)|mental health professionals?)\b',
        'recommendationPattern': r"\b(?:(?:i|we) (?:(?:would|could|strongly|gently) )?(?:recommend|suggest|encourage|advise)|consider|helpful|beneficial|worth|good idea|(?:can|could|may|might) help|talk to|speak with|consult|seek|get support|(?:you )?(?:should|could|might|may) (?:see|contact|ask|visit|get|benefit))\b",
        'negative': r"\b(?:(?:don't|do not|wouldn't|would not|never|not) (?:recommend|suggest|advise|need|require)|(?:no|not) (?:need|needed|necessary|recommended|helpful|help)|(?:isn't|is not|aren't|are not) (?:needed|necessary|recommended|helpful)|(?:don't|do not) think you need|(?:don't|do not|shouldn't|should not) (?:see|consult|contact|seek|talk to|speak with)|(?:no|without) (?:psychologists?|psychological (?:support|help)))\b",
    },
    'de': {
        'professional': r'\b(?:psychologe[n]?|psychologin(?:nen)?|psychologisch(?:e|er|en|es) (?:unterstützung|hilfe|beratung))\b',
        'recommendationPattern': r'\b(?:(?:ich|wir)(?: \w+){0,3} empfehle[n]?|empfehlenswert|hilfreich|sinnvoll|ratsam|erwägen|in betracht|kann helfen|wäre gut|(?:sollten?|könnten?)(?: \w+){0,6} (?:aufsuchen|sprechen|kontaktieren|besuchen|suchen|helfen))\b',
        'negative': r'\b(?:(?:nicht|nie|keinesfalls) (?:empfehle[n]?|empfehlenswert|nötig|notwendig|erforderlich|ratsam|hilfreich|sinnvoll)|kein(?:e|en|er|es)? (?:psycholog\w*|psychologisch\w* (?:unterstützung|hilfe|beratung)))\b',
    },
    'tr': {
        'professional': r'\b(?:psikolog\w*|psikolojik (?:destek\w*|yardım\w*))\b',
        'recommendationPattern': r'\b(?:öneririm|öneriyorum|önerebil\w*|tavsiye|düşünebil\w*|faydalı|yararlı|iyi gelebilir|görüşebil\w*|görüşmenizi|başvurabil\w*)\b',
        'negative': r'\b(?:önermiyorum|önermem|önermeyiz|önermeyin|tavsiye etmiyorum|tavsiye etmem|gerekmez|gerekmiyor|gerekli değil|faydalı değil|yararlı değil|gitmeyin|görüşmeyin)\b',
    },
}


def professional_support_suggested(text, language):
    """Recommendation + profession in an unquoted, non-negated clause.

    This ordinary support flag never assigns acute emergency status.
    """
    rules = SUPPORT_RULES.get(language)
    if rules is None:
        return False
    value = unicodedata.normalize('NFC', text)
    # Do not mistake contractions for quoted text. Quotes cannot activate this
    # flag, while an independent recommendation outside a quote still can.
    value = re.sub(r'"[^"\n]*"|“[^”\n]*”|«[^»\n]*»|(?<!\w)\'[^\'\n]+\'(?!\w)', ' ', value)
    if language == 'tr':
        value = value.replace('I', 'ı').replace('İ', 'i')
    value = value.lower().replace('’', "'")
    clauses = re.split(r'[.!?;\n]|\b(?:but|however|aber|jedoch|ama|ancak)\b', value)
    return any(re.search(rules['professional'], clause) and re.search(rules['recommendationPattern'], clause)
               and not re.search(rules['negative'], clause) for clause in clauses)
