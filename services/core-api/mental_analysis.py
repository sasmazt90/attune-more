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
# Characters that cannot occur in the requested language's own words.
_FOREIGN_LETTERS = {'en': 'ğĞıİşŞçÇöÖüÜäÄß', 'de': 'ğĞıİşŞçÇ', 'tr': 'äÄß'}
# Function words: what is not a content word, and (when exclusive to another language) a sign of the wrong language.
_FUNCTION_WORDS = {
    'en': set('a an the and or but of to in on at for with about from by into over after before as is are was were be been '
              'being am i me my you your yours we our they them their he she it its this that these those there here very '
              'really much many lot lots some any more most also just still so too not no than then when while how what '
              'which who do does did have has had can could will would may might must talked spoke'.split()),
    'de': set('der die das den dem des ein eine einen einem einer eines und oder aber von zu zum zur in im an am auf für mit '
              'bei über unter nach vor aus als ist sind war waren sein bin bist hat haben hatte ich mich mir mein meine '
              'meinen meinem meiner sie ihr ihre ihren ihrem ihrer ihres ihnen es sich nicht kein keine sehr viel viele '
              'auch noch so wie was wer wenn dass da dann seit sprachen gesprochen'.split()),
    'tr': set('ve veya ile için bir bu şu o çok daha en de da ki mi mı mu mü ama ya gibi kadar sonra önce her hiç ben beni '
              'bana benim sen seni sana senin söz ettin bahsettin'.split()),
}
# Exclusive markers: words that only the other languages use (a line containing one is in the wrong language).
_EXCLUSIVE = {lang: words - set().union(*(w for l, w in _FUNCTION_WORDS.items() if l != lang)) for lang, words in _FUNCTION_WORDS.items()}
# The required sentence form of the recap, per language (Turkish uses sen, as the recorded A/B/C closing does).
_RECAP_FORM = {
    'en': r'^you (?:talked|spoke) about (?P<body>.+)$',
    'de': r'^sie (?:sprachen über (?P<body>.+)|haben über (?P<body2>.+) gesprochen)$',
    'tr': r'^(?P<body>.+) (?:söz ettin|bahsettin)$',
}
_ADDRESS = {
    # Turkish: second person singular (sen). Plural/polite forms (siz, -ınız/-iniz + case, ettiniz) do not match the recordings.
    'tr': r'\b(siz|sizin|size|sizi|sizinle|sizden|sizde)\b|\w*[ıiuü]n[ıiuü]z(dan|den|tan|ten|a|e|ı|i|u|ü|da|de|la|le|ın|in|un|ün)?\b|(ettiniz|bahsettiniz)\b',
    'de': r'\b(du|dich|dir|dein\w*|euch|euer\w*|hast|bist)\b',
    'en': None,
}
# Words that state no fact of their own and may appear without the user having said them.
_NEUTRAL = {'en': {'feeling', 'feelings', 'things', 'being', 'topic', 'topics'}, 'de': {'gefühl', 'gefühle', 'thema', 'themen'},
            'tr': {'konu', 'konular', 'konulardan', 'konusundan', 'duygu', 'duygulardan'}}
# Clear markers of advice, suggestion, reassurance or evaluation (live examples: "It's normal to feel ...",
# "... effectively", "... destek almayı düşünebilirsiniz").
_ADVICE_OR_EVALUATION = {
    'tr': (r'düşünebil', r'öneri', r'\w+m[ae]l[ıi]s[ıi]n', r'\bdeneyin', r'deneyebilir', r'normaldir', r'\bnormal\b',
           r'anlaşılır', r'başarıyla', r'harika', r'çok iyi', r'\biyi ki\b'),
    'en': (r'\bshould\b', r'\bconsider', r'\bmight want\b', r'\btry\b', r"\bit'?s (normal|okay|ok|fine|good|great|understandable)\b",
           r'\b(normal|understandable)\b', r'\beffectively\b', r'\bwell done\b', r'\bgreat\b', r'\brecommend'),
    'de': (r'\bsollten\b', r'\bempfehl', r'\bversuchen sie\b', r'\bkönnten sie\b', r'\b(ist|sei) (normal|verständlich|gut|okay)\b',
           r'\bnormal\b', r'\bverständlich\b', r'\berfolgreich\b', r'\bgroßartig\b', r'\bratsam\b'),
}


def _fold(text, language):
    if language == 'tr':
        text = text.replace('I', 'ı').replace('İ', 'i')
    return text.lower()


def _words(text, language):
    import re
    return [w.strip("'’") for w in re.findall(r"[^\W\d_]+(?:['’][^\W\d_]+)?", _fold(text, language))]


def _grounded(token, said, language):
    import re
    """Lexical grounding only: a shared stem (>= 5 letters, or >= 4 letters covering 60% of the shorter word; Turkish
    roots: >= 4 letters, as suffixes change the stem's end), or one word containing the other (compounds). It cannot
    tell whether the meaning, e.g. a negation, was kept."""
    token = token.split("'")[0]
    for word in said:
        common = 0
        for a, b in zip(token, word):
            if a != b:
                break
            common += 1
        if common >= 5 or (common >= 4 and (language == 'tr' or common >= 0.6 * min(len(token), len(word)))):
            return True
        if (len(word) >= 5 and word in token) or (len(token) >= 5 and token in word):
            return True
        # German separable verbs and nouns made from them ("lenkt ... ab" -> "Ablenkungen"): the verb stem inside the word.
        if language == 'de':
            stem = re.sub(r'(en|st|t|e|n)$', '', word)
            if len(stem) >= 4 and stem in token:
                return True
    return False


def validate_spoken_summary(value, language, messages):
    """Short closing line for the normal conversation. Formal checks only, applied to every provider response.

    Enforced: one sentence, <= 12 words and <= 100 characters; letters and function words of the session language;
    Turkish sen / German Sie (matching the recorded closing); none of the A/B/C bridge phrases; no listed advice,
    suggestion, reassurance or evaluation marker; the recap form ("You talked about ...", "Sie sprachen über ...",
    "...dan/den söz ettin"); Turkish ablative before the verb; at least one content word the user said and at most one
    content word the user did not say (and then only next to two that they did).

    Not guaranteed: meaning. A line built from the user's own words can still reverse a negation or join facts wrongly.

    Returns (text, None) or (None, reason). Never trims words or characters to make a text fit: an invalid line is
    rejected, the written summary stays, and the caller does not speak a longer text instead.
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
    if language not in _RECAP_FORM:
        return None, 'unsupported-language'
    words = _words(text, language)
    if any(ch in _FOREIGN_LETTERS[language] for ch in text) or any(w in other for w in words for l, other in _EXCLUSIVE.items() if l != language):
        return None, 'wrong-language'
    lowered = _fold(text, language)
    if _ADDRESS[language] and re.search(_ADDRESS[language], lowered):
        return None, 'address-mismatch'
    if any(re.search(pattern, lowered) for pattern in _BRIDGE_PHRASES[language]):
        return None, 'repeats-bridge-phrase'
    if any(re.search(pattern, lowered) for pattern in _ADVICE_OR_EVALUATION[language]):
        return None, 'advice-or-evaluation'
    form = re.match(_RECAP_FORM[language], lowered.rstrip('.').strip())
    if not form or not text.endswith('.'):
        return None, 'not-recap-form'
    body = form.group('body') or form.groupdict().get('body2') or ''
    if language == 'tr' and not re.search(r"(d|t)(a|e)n$", body.split(' ')[-1]):
        return None, 'tr-ablative-required'
    said = [w for w in _words(' '.join(m.get('content', '') for m in messages if m.get('role') == 'user'), language) if len(w) >= 4]
    content = [w for w in _words(body, language) if len(w) >= 4 and w not in _FUNCTION_WORDS[language] and w not in _NEUTRAL[language]]
    grounded = sum(_grounded(w, said, language) for w in content)
    unsaid = len(content) - grounded
    if grounded == 0:
        return None, 'not-grounded-in-user-words'
    if unsaid >= 2 or (unsaid == 1 and grounded < 2):
        return None, 'adds-unsaid-content'
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
