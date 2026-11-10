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
              'which who do does did have has had can could will would may might must talked spoke through during between '
              'because since until around against toward towards without'.split()),
    'de': set('der die das den dem des ein eine einen einem einer eines und oder aber von zu zum zur in im an am auf für mit '
              'bei über unter nach vor aus als ist sind war waren sein bin bist hat haben hatte ich mich mir mein meine '
              'meinen meinem meiner sie ihr ihre ihren ihrem ihrer ihres ihnen es sich nicht kein keine sehr viel viele '
              'auch noch so wie was wer wenn dass da dann seit sprachen gesprochen durch gegen wegen während zwischen ohne '
              'beim vom ins'.split()),
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

# Negation markers. Lexical only: they show that a negation is present near a word, not what it means.
_NEGATION = {
    # Contractions need the apostrophe, except a closed list typed without one ("dont"); a bare "-nt" ending is not a
    # negation ("recent", "different", "want").
    'en': r"^(?:not|no|never|without|nor|neither|cannot|nothing|nobody|none|\w+n['’]t|"
          r"(?:do|does|did|is|are|was|were|has|have|had|could|should|would|must|might|need|ca|wo|ai)nt)$",
    'de': r'^(?:nicht|nichts|nie|niemals|niemand\w*|ohne|weder|kein\w*)$',
    'tr': r'^(?:yok\w*|değil\w*|hiç|hiçbir|asla|olmadan|kimse\w*|\w+m[ıiuü]yor\w*|\w+m[ae]d[ıiğ]\w*|\w+m[ae]z\w*|\w+m[ae]mak\w*|\w+m[ae]mek\w*|\w+m[ae]m[ae]\w*|\w+m[ae]yan\w*|\w+m[ae]yen\w*|\w+s[ıiuü]z\w*)$',
}
_NEGATION_EXCEPT = {'en': set(), 'de': set(), 'tr': {'tamam', 'tamamen', 'yalnız', 'yalnızca', 'komedi', 'namaz', 'temiz'}}
# A negation in the user's words counts for its whole clause (up to punctuation or a clause break): "I do not believe
# my manager will really support me" negates "support" as well, however far it stands from "not".
_CLAUSE_BREAK = {'en': {'but', 'only', 'though', 'although', 'however', 'yet', 'and', 'or'},
                 'de': {'aber', 'sondern', 'nur', 'doch', 'jedoch', 'und', 'oder'},
                 'tr': {'ama', 'fakat', 'ancak', 'sadece', 'yalnızca', 'oysa', 've', 'veya'}}
# The line's coordinated parts ("... and ...", "... ve ...", "... und ..."): each must rest on the user's words.
_ITEM_BREAK = {'en': r',|\band\b|\bor\b', 'de': r',|\bund\b|\boder\b|\bsowie\b', 'tr': r',|\bve\b|\bveya\b'}
# First person in a line addressed to the user is a copied user phrase ("my job", "kiramı"), not a recap.
_FIRST_PERSON = {
    'en': r"\b(i|me|my|mine|myself|i['’]m|i['’]ve|i['’]d|i['’]ll)\b",
    'de': r'\b(ich|mich|mir|mein|meine|meinen|meinem|meiner|meines)\b',
    'tr': r'\b(ben|beni|bana|benim|bende|benden|benimle|kendim\w*|biz|bizi|bize|bizim|bizde|bizden)\b|\w+[ıiuü]m[ıiuü]z\w*',
}
# Turkish: a word ending in a vowel + m (+ case) is read as "my ..." (işim, kiramı, annemden) unless it is one of these
# nouns whose own stem ends in m. The list is closed: an unlisted noun of that shape is rejected, not spoken.
_TR_M_STEMS = set('durum yorum ölüm doğum eğitim öğretim öğrenim iletişim etkileşim değişim gelişim dönüşüm geçim bölüm dönem sistem '
                  'problem program akşam yardım bakım takım kısım adam yöntem gündem bayram yaşam anlam ortam önem çözüm gerilim uyum '
                  'tutum sunum konum kavram gözlem eylem işlem söylem bağlam toplam tamam tüm film özlem sitem ilham hüküm tüketim '
                  'üretim yönetim denetim seçim biçim giyim yatırım tasarım anlatım katılım resim isim mevsim verim kurum toplum '
                  'bilim iklim takvim hanım hekim yıkım dilim kalem madem hem kim ekim kasım'.split())
_TR_M_SHAPE = r'^(?P<stem>\w+[aeıioöuü]m)(?:dan|den|a|e|ı|i|u|ü|da|de|daki|deki|la|le|ın|in|un|ün|ları|leri|lar|ler|lardan|lerden)?$'
# Turkish three-letter roots (yol, gün): the line's word is that root plus a case or possessive ending.
_TR_SHORT_ROOT_ENDING = r'^(?:[ıiuü]n|[ıiuü]|[ae]|[dt][ae]n|[dt][ae]|l[ae]|l[ae]r\w{0,6}|[ıiuü]n(?:d[ae]n|[ae]|[ıiuü]|d[ae]|l[ae])|s[ıiuü](?:n(?:d[ae]n|[ae]|[ıiuü]|d[ae]))?)$'
# English inflection: the same stem with -s/-es/-ed/-ing and a dropped final e or y ("moved" / "moving", "worry" /
# "worried") is the same word.
_EN_INFLECTION = r'(?:ies|ied|ying|ing|ed|es|s|e|y)$'
# German nouns or adjective forms whose stem differs from the verb or adjective the user said: strong-verb nouns
# ("Umzug" for "ich ziehe", "Gespräch" for "sprechen") and hoch -> hohe/hohen. Closed list, after at most one listed
# prefix; any other derivation is still not grounded (the line is refused and nothing is spoken).
_DE_STEM_VARIANTS = (('zug', 'zieh'), ('züg', 'zieh'), ('flug', 'flieg'), ('flüg', 'flieg'), ('gang', 'geh'), ('gäng', 'geh'),
                     ('fahrt', 'fahr'), ('verlust', 'verlier'), ('hilf', 'helf'), ('spräch', 'sprech'), ('schluss', 'schließ'),
                     ('schlüss', 'schließ'), ('bruch', 'brech'), ('brüch', 'brech'), ('hoh', 'hoch'))
_DE_VARIANT_SHAPE = (r'^(?:um|aus|ein|an|ab|auf|zu|ge|weg)?(?P<variant>' + '|'.join(v for v, _ in _DE_STEM_VARIANTS) +
                     r')(?:e|en|er|es|em|s|n|ern)?$')
_DE_VERB_ENDING = r'(?:e|st|t|en|et|end)?$'
# Words that open a noun phrase of their own (article, possessive, preposition). A content word the user did not say
# right after one of them, and not modifying a word the user said, names a new person or thing ("... from your manager").
_PHRASE_OPENER = {
    'en': set('a an the your his her their its our from with by of about for to at in on over after before during between '
              'against without toward towards into through because'.split()),
    'de': set('der die das den dem des ein eine einen einem einer eines ihr ihre ihren ihrem ihrer ihres von vom mit durch bei beim '
              'über für zu zum zur vor nach aus gegen ohne wegen seit unter zwischen im am ins'.split()),
    'tr': set(),
}
# Turkish possessor in the genitive ("patronunun", "ailenin"): a new person or thing when the user did not say it.
_TR_GENITIVE_POSSESSOR = r'^\w+n[ıiuü]n$'
# Turkish nouns with the speaker's possessive (user: annem / annemi / annemin) and the line's (annen / anneni / annenin):
# nominative or genitive marks who acts, accusative whom it is done to. A line that swaps them ("Annem beni hiç
# dinlemiyor" -> "Anneni hiç dinlemediğinden") changes who did what.
_TR_USER_POSSESSED = r'^(?P<root>\w{2,}?)(?:(?<=[aeıioöuü])m|[ıiuü]m)(?P<case>[ıiuü]n|[ıiuü]|)$'
_TR_LINE_POSSESSED = r'^(?P<root>\w{2,}?)(?:(?<=[aeıioöuü])n|[ıiuü]n)(?P<case>[ıiuü]n|[ıiuü]|)$'


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
    token = re.split(r"['’]", token)[0]
    if language == 'de':
        variant = re.match(_DE_VARIANT_SHAPE, token)
        if variant:
            stems = [verb for noun, verb in _DE_STEM_VARIANTS if noun == variant.group('variant')]
            if any(word.startswith(stem) and re.match(_DE_VERB_ENDING, word[len(stem):]) for stem in stems for word in said):
                return True
    if language == 'en':
        stem = re.sub(_EN_INFLECTION, '', token)
        if len(stem) >= 3 and any(re.sub(_EN_INFLECTION, '', word) == stem for word in said):
            return True
    for word in said:
        if len(word) == 3:
            if language == 'tr' and token.startswith(word) and re.match(_TR_SHORT_ROOT_ENDING, token[3:]):
                return True
            continue
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



def _is_negation(word, language):
    import re
    return word not in _NEGATION_EXCEPT[language] and re.match(_NEGATION[language], word) is not None


def _negated_user_words(messages, language):
    """Per user word: was it ever said in a clause without a negation (plain), and in a clause with one (negated)?
    A clause ends at punctuation or a clause break (but, only, and, ama, ve, aber, nur, ...)."""
    import re
    plain, negated = set(), set()
    for message in messages:
        if message.get('role') != 'user':
            continue
        for part in re.split(r'[.!?;:,…\n]+', _fold(message.get('content', ''), language)):
            clause = []
            for word in _words(part, language) + [None]:
                if word is None or word in _CLAUSE_BREAK[language]:
                    (negated if any(_is_negation(w, language) for w in clause) else plain).update(clause)
                    clause = []
                else:
                    clause.append(word)
    return plain, negated


def _tr_role_changed(line_words, messages):
    """Turkish: a noun the user said with their possessive as the one who acts (annem, annemin) now stands in the line as
    the one acted on (anneni), or the reverse. Only nominative/genitive versus accusative of possessed nouns."""
    import re
    user_roles = {}
    for word in _words(' '.join(m.get('content', '') for m in messages if m.get('role') == 'user'), 'tr'):
        shape = re.match(_TR_USER_POSSESSED, word)
        if shape and word not in _TR_M_STEMS:
            user_roles.setdefault(shape.group('root'), set()).add('object' if len(shape.group('case')) == 1 else 'actor')
    for word in line_words:
        shape = re.match(_TR_LINE_POSSESSED, word)
        if shape and shape.group('root') in user_roles:
            role = 'object' if len(shape.group('case')) == 1 else 'actor'
            if role not in user_roles[shape.group('root')]:
                return True
    return False


def _tr_first_person(word):
    import re
    shape = re.match(_TR_M_SHAPE, word)
    return bool(shape) and shape.group('stem') not in _TR_M_STEMS and word not in _TR_M_STEMS

def validate_spoken_summary(value, language, messages):
    """Short closing line for the normal conversation. Formal checks only, applied to every provider response.

    Enforced: one sentence, <= 12 words and <= 100 characters; letters and function words of the session language;
    Turkish sen / German Sie (matching the recorded closing); none of the A/B/C bridge phrases; no listed advice,
    suggestion, reassurance or evaluation marker; the recap form ("You talked about ...", "Sie sprachen über ...",
    "...dan/den söz ettin"); Turkish ablative before the verb; no first person (a copied "my ..."/"kiramı"); at least
    one content word the user said, at most one the user did not say (only next to two that they did, only describing
    a word the user said, never a new noun phrase or possessor of its own), and every coordinated part of the line
    resting on a word the user said; Turkish possessed nouns keep their role (who acts / who is acted on); negation
    parity per part: a negation in the user's words covers its whole clause, a part built only from negated words needs
    a negation, a negated part may only use words the user said in a negated clause, and the line may not negate when
    the user never did.

    Not guaranteed: meaning. These are word-level checks. A line can still add a fact as a modifier of a word the user
    said ("manager pressure"), swap roles in English or German word order, or carry a negation the user expressed
    without a negation word. The checks err towards rejection: correct paraphrases outside the listed forms
    ("odaklanma zorluğu" for "odaklanamıyorum") are refused.

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
    if re.search(_FIRST_PERSON[language], lowered) or (language == 'tr' and any(_tr_first_person(w) for w in words)):
        return None, 'first-person'
    said = [w for w in _words(' '.join(m.get('content', '') for m in messages if m.get('role') == 'user'), language)
            if len(w) >= 4 or (language == 'tr' and len(w) == 3 and w not in _FUNCTION_WORDS['tr'])]
    is_content = lambda w: len(w) >= 4 and w not in _FUNCTION_WORDS[language] and w not in _NEUTRAL[language]
    content = [w for w in _words(body, language) if is_content(w)]
    grounded = sum(_grounded(w, said, language) for w in content)
    unsaid = len(content) - grounded
    if grounded == 0:
        return None, 'not-grounded-in-user-words'
    # At most one content word the user did not say, only next to two that they did, and never a coordinated part of
    # its own ("... and your boss"): every part of the line must contain a word the user said.
    items = [[w for w in _words(part, language) if is_content(w)] for part in re.split(_ITEM_BREAK[language], body)]
    items = [item for item in items if item]
    if unsaid >= 2 or (unsaid == 1 and grounded < 2) or any(not any(_grounded(w, said, language) for w in item) for item in items):
        return None, 'adds-unsaid-content'
    # The one unsaid word may describe a word the user said ("interrupted sleep", "work pressure"), not name a new person
    # or thing: not right after an article, possessive or preposition unless a word the user said follows it, never a
    # possessor ("manager's", Turkish genitive "patronunun").
    body_words = [w.strip("'’") for w in re.findall(r"[^\W\d_]+(?:['’][^\W\d_]+)?", _fold(body, language))]
    for i, word in enumerate(body_words):
        if not is_content(word) or _grounded(word, said, language):
            continue
        follows = body_words[i + 1] if i + 1 < len(body_words) else None
        describes_said = follows is not None and is_content(follows) and _grounded(follows, said, language)
        possessor = re.search(r"['’]s$", word) or (language == 'tr' and re.match(_TR_GENITIVE_POSSESSOR, word))
        opens_phrase = language != 'tr' and (i == 0 or body_words[i - 1] in _PHRASE_OPENER[language])
        if possessor or (opens_phrase and not describes_said):
            return None, 'adds-unsaid-content'
    if language == 'tr' and _tr_role_changed(words, messages):
        return None, 'role-changed'
    # Negation parity (lexical), per coordinated part of the line. A part that rests only on words the user said in a
    # negated clause ("not worried about my health") needs a negation of its own; a part that negates may only use
    # words the user also said in a negated clause (the line may not move the negation onto "job" or "Ergebnis");
    # a line may not negate when the user never did.
    plain, negated = _negated_user_words(messages, language)
    negated_only = [n for n in negated if len(n) >= 3 and n not in plain]
    plain_said = [p for p in plain if len(p) >= 3]
    negated_said = [n for n in negated if len(n) >= 3]
    line_negates = any(_is_negation(w, language) for w in _words(body, language))
    if line_negates and not negated:
        return None, 'negation-added'
    for part in re.split(_ITEM_BREAK[language], body):
        part_words = _words(part, language)
        from_user = [w for w in part_words if is_content(w) and _grounded(w, said, language)]
        # Short words (job, son, Weg) are not content words above, but one the user said anchors the part.
        short = [w for w in part_words if len(w) == 3 and w not in _FUNCTION_WORDS[language] and (w in plain or w in negated)]
        if any(_is_negation(w, language) for w in part_words):
            if any(not _grounded(w, negated_said, language) for w in from_user) or any(w not in negated for w in short):
                return None, 'negation-moved'
        elif from_user and not any(w in plain for w in short) and all(
                _grounded(w, negated_only, language) and not _grounded(w, plain_said, language) for w in from_user):
            return None, 'negation-not-kept'
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
