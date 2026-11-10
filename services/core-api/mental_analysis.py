"""Consent-gated summary context and strict additive structured-analysis contract."""
from pydantic import BaseModel, Field, StrictBool, ConfigDict, field_validator
from typing import Literal
from mental_themes import SESSION_THEME_KEYS, stable_session_themes


def reject_template_support_reason(value):
    if isinstance(value, str) and value.strip() == 'Klinik öneri gerekçesi veya null':
        raise ValueError('TEMPLATE_SUPPORT_REASON')
    return value


def relevant_history(messages, records):
    from mental_provider import LocalFallbackSessionAnalyzer
    from mental_structured import normalize
    normalized=[{**m,'content':normalize(m['content'])} for m in messages]
    current=set(LocalFallbackSessionAnalyzer().analyze_session(normalized)['themes'])-{'günlük iyi oluş paylaşımı'}
    result=[]
    for record in records:
        try:themes=stable_session_themes(record.themes)
        except ValueError:continue
        if current.intersection(themes):
            result.append({'id':record.id,'summaryText':record.summaryText,'themes':themes,'source':'previous-assistant-summary-not-user-quotation'})
    return result


class SessionAnalysis(BaseModel):
    model_config=ConfigDict(extra='ignore',str_strip_whitespace=True)
    summaryText: str = Field(min_length=1,max_length=4000)
    themes: list[str] = Field(max_length=12)
    moodTrend: Literal['STRESSED','RELAXED','TIRED','NEUTRAL']
    professionalSupportSuggested: StrictBool
    professionalSupportReason: str | None = Field(default=None,max_length=2000)
    recommendations: list[str] = Field(default_factory=list,max_length=5)
    relatedSessionIds: list[str] = Field(default_factory=list,max_length=5)
    recurringThemes: list[str] = Field(default_factory=list,max_length=12)
    spokenSummary: str = Field(min_length=1,max_length=2000)

    @field_validator('professionalSupportReason')
    @classmethod
    def reject_template_reason(cls, value):
        return reject_template_support_reason(value)


def structured_analysis_response_format():
    """Require the existing complete analysis contract at the provider boundary.

    JSON mode alone permits missing fields, including the spoken closing. Keep
    server validation authoritative; never synthesize missing provider output.
    """
    schema=SessionAnalysis.model_json_schema()
    schema['additionalProperties']=False
    schema['required']=list(schema['properties'])
    for prop in schema['properties'].values():
        prop.pop('default',None)
    for name in ('themes','recurringThemes'):
        schema['properties'][name]['items']={'type':'string','enum':list(SESSION_THEME_KEYS)}
    return {'type':'json_schema','json_schema':{'name':'mental_session_analysis','strict':True,'schema':schema}}


SPOKEN_SUMMARY_MAX_WORDS = 12
SPOKEN_SUMMARY_MAX_CHARS = 100
# The closing bridge already thanks the user (A), closes the conversation (B) and announces the summary (C).
_BRIDGE_PHRASES = {
    'tr': (r'teşekkür', r'sağ ?ol', r'sonuna geldi', r'kapanış', r'sonlandır', r'noktalı', r'tamamlıyoruz',
           r'özet\w* hazırl', r'özetliyorum', r'bir araya getir', r'topluyorum', r'toparlıyorum'),
    'en': (r'\bthank', r'\bend of (our|the|this|today\'s) (conversation|session)', r'\bto a close\b', r'\bclosing\b',
           r'\bwrap(ping)? up\b', r"\bi'?m (preparing|summari[sz]ing|bringing together|gathering|putting)", r'\bsummary\b'),
    'de': (r'\bdank', r'\babschluss', r'\bbeende', r'\bschließen\b', r'\bam ende unseres', r'\bfasse\b',
           r'\bzusammenfassung', r'\btrage\b.*\bzusammen'),
}
# Characters that cannot occur in the requested language's own words (a heuristic language check).
_FOREIGN_LETTERS = {'en': 'ğĞıİşŞçÇöÖüÜäÄß', 'de': 'ğĞıİşŞçÇ', 'tr': 'äÄß'}
_INFORMAL = {'de': r'\b(du|dich|dir|dein\w*|euch|euer\w*)\b', 'tr': r'\b(sen|seni|sana|senin|seninle)\b', 'en': None}
# The line restates what the user said. Clear markers of advice, suggestion, reassurance or evaluation reject it
# (a live provider returned "It's normal to feel ...", "... effectively" and "... destek almayı düşünebilirsiniz").
_ADVICE_OR_EVALUATION = {
    'tr': (r'düşünebilirsiniz', r'öneri', r'almalısınız', r'yapmalısınız', r'\bdeneyin', r'deneyebilirsiniz', r'normaldir',
           r'\bnormal\b', r'anlaşılır', r'başarıyla', r'harika', r'çok iyi'),
    'en': (r'\bshould\b', r'\bconsider', r'\bmight want\b', r'\btry\b', r"\bit'?s (normal|okay|ok|fine|good|great|understandable)\b",
           r'\b(normal|understandable)\b', r'\beffectively\b', r'\bwell done\b', r'\bgreat\b', r'\brecommend'),
    'de': (r'\bsollten\b', r'\bempfehl', r'\bversuchen sie\b', r'\bkönnten sie\b', r'\b(ist|sei) (normal|verständlich|gut|okay)\b',
           r'\bnormal\b', r'\bverständlich\b', r'\berfolgreich\b', r'\bgroßartig\b', r'\bratsam\b'),
}


def _stems(text):
    import re
    return {w[:5] for w in re.findall(r'\w+', text.casefold()) if len(w) >= 5 and not w.isdigit()}


def validate_spoken_summary(value, language, messages):
    """Short closing line for the normal conversation: one sentence, <= 12 words and <= 100 characters, a recap of
    what the user said (no advice, suggestion, reassurance or evaluation).

    Returns (text, None) or (None, reason). Never trims words or characters to make a text fit: an
    invalid line is rejected, the written summary stays, and the caller does not speak a longer text instead.
    """
    import re
    import unicodedata
    if not isinstance(value, str):
        return None, 'missing'
    text = re.sub(r'\s+', ' ', unicodedata.normalize('NFC', value)).strip()
    if not text:
        return None, 'empty'
    if len(text) > SPOKEN_SUMMARY_MAX_CHARS:
        return None, 'too-many-characters'
    if len(text.split(' ')) > SPOKEN_SUMMARY_MAX_WORDS:
        return None, 'too-many-words'
    if re.search(r'[.!?…]["\'”’)]?\s+\S', text):
        return None, 'more-than-one-sentence'
    if language not in _BRIDGE_PHRASES:
        return None, 'unsupported-language'
    if any(ch in _FOREIGN_LETTERS[language] for ch in text):
        return None, 'wrong-language'
    lowered = text.casefold()
    if _INFORMAL[language] and re.search(_INFORMAL[language], lowered):
        return None, 'informal-address'
    if any(re.search(pattern, lowered) for pattern in _BRIDGE_PHRASES[language]):
        return None, 'repeats-bridge-phrase'
    if any(re.search(pattern, lowered) for pattern in _ADVICE_OR_EVALUATION[language]):
        return None, 'advice-or-evaluation'
    said = _stems(' '.join(m.get('content', '') for m in messages if m.get('role') == 'user'))
    if not _stems(text) & said:
        return None, 'not-grounded-in-user-words'
    return text, None


def validate_analysis(data, history, no_advice=False):
    result=SessionAnalysis.model_validate(data).model_dump()
    result['themes']=stable_session_themes(result['themes'])
    allowed={r['id']:r for r in history}
    result['relatedSessionIds']=list(dict.fromkeys(i for i in result['relatedSessionIds'] if i in allowed))
    historical={t for i in result['relatedSessionIds'] for t in allowed[i]['themes']}
    result['recurringThemes']=[t for t in stable_session_themes(result['recurringThemes']) if t in result['themes'] and t in historical]
    if any(not s.strip() or len(s)>1000 for s in result['recommendations']):raise ValueError('INVALID_RECOMMENDATION')
    if no_advice:result['recommendations']=[]
    return result
