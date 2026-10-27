"""Explicit conversation controls, not inferred emotion or a model fallback.

Crisis detection must run before this function. No provider request is made for
these short control utterances; the response identifies its actual source.
"""
import re
import unicodedata

def conversation_control(text):
    value = unicodedata.normalize('NFC', text).lower().replace('i̇', 'i').strip()
    value = re.sub(r'[^\wçğıöşü ]', ' ', value)
    value = re.sub(r'\s+', ' ', value).strip()
    # Equivalent explicit controls in EN/DE; crisis detection still runs first.
    controls = {
        'finish': ('finish', 'end the conversation', 'finish the conversation', 'goodbye', 'beenden', 'gespräch beenden', 'auf wiedersehen'),
        'pause': ('pause', 'pause the conversation', 'take a break', 'pausieren', 'gespräch pausieren', 'eine pause machen'),
    }
    german_finish = re.fullmatch(
        r'(?:bitte )?(?:ich (?:möchte|will) (?:das )?gespräch(?: jetzt)? beenden|'
        r'(?:das )?gespräch(?: jetzt)? beenden|beenden sie(?: bitte)? (?:das )?gespräch)', value)
    english_finish = re.fullmatch(
        r'(?:please )?(?:i (?:want|would like) to )?(?:end|finish) (?:the|this|our) conversation(?: now| please)?', value)
    english_pause = re.fullmatch(
        r'(?:please )?(?:i (?:want|would like) to )?(?:pause (?:the|this|our) conversation|take a break)(?: now| please)?', value)
    german_pause = re.fullmatch(
        r'(?:bitte )?(?:ich (?:möchte|will) )?(?:(?:das )?gespräch pausieren|eine pause machen)', value)
    if value in controls['finish'] or german_finish or english_finish:
        return {'reply': 'Görüşmeyi bitiriyorum. Kendinize iyi bakın.', 'sessionAction': 'finish', 'providerType': 'CONVERSATION_CONTROL', 'isCrisis': False}
    if value in controls['pause'] or english_pause or german_pause:
        return {'reply': 'Görüşmeyi duraklatıyorum. Hazır olduğunuzda Devam et düğmesiyle sürdürebilirsiniz.', 'sessionAction': 'pause', 'providerType': 'CONVERSATION_CONTROL', 'isCrisis': False}
    if re.fullmatch(r'(lütfen )?(görüşmeyi bitir|görüşmeyi sonlandır|konuşmayı bitir|konuşmayı sonlandır|bitir|bitirelim|görüşmeyi bitirmek istiyorum|konuşmayı bitirmek istiyorum|şimdilik bu kadar|hoşça kal|hoşçakal|görüşürüz)', value):
        return {'reply': 'Görüşmeyi bitiriyorum. Kendinize iyi bakın.', 'sessionAction': 'finish', 'providerType': 'CONVERSATION_CONTROL', 'isCrisis': False}
    if re.fullmatch(r'(lütfen )?(duraklat|görüşmeyi duraklat|ara ver|görüşmeye ara ver|biraz ara vermek istiyorum|sonra devam etmek istiyorum)', value):
        return {'reply': 'Görüşmeyi duraklatıyorum. Hazır olduğunuzda Devam et düğmesiyle sürdürebilirsiniz.', 'sessionAction': 'pause', 'providerType': 'CONVERSATION_CONTROL', 'isCrisis': False}
    if len(value) <= 140 and re.search(r'\b(dönerim|döneceğim|sonra gelirim|sonra dönerim|ara verelim mi)\b', value):
        return {'reply': 'Görüşmeye ara vermek mi istiyorsunuz, yoksa konuşmaya devam edelim mi?', 'sessionAction': 'clarify', 'providerType': 'CONVERSATION_CONTROL', 'isCrisis': False}
    return None
