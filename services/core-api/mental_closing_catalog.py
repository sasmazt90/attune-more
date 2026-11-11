"""Catalog closing line: the provider chooses a generic, version-controlled line; the server checks the choice.

The written summary stays personal and is untouched. The spoken closing line after C is one of the catalog's fixed
lines (shared/mental/closing-catalog/v1/catalog.json), prerecorded per language, so nothing the user did not say can
be spoken as a new sentence. The provider returns up to three candidates: catalog id, the index of the user message
it rests on and a verbatim quote from it. The server accepts a candidate only when every check passes:

- the id exists; the message exists, is the user's (an assistant suggestion is not the user's statement) and contains
  the quote verbatim (whitespace and case folded);
- one of the pattern's cues occurs inside the quote (a cue is necessary, never sufficient);
- the cue's clause has no negation outside the cue itself ("Stresli değilim", "I am not stressed");
- the clause is about the user: a first-person marker, not a third person alone ("Arkadaşım stresli", "My friend is
  stressed"); a possessed person ("my mother", "annem") is not the user;
- not past and over ("Eskiden stresliydim, artık değilim", "I used to be ...", "nicht mehr"), unless the change is the
  pattern's own topic (lost interest, relief);
- no later user message corrects it (the same cue negated, or a correction marker with a negation);
- the cue states the user's own state, not something else the sentence carries (round 7): not the topic of something
  ("a book about stress", "Stres hakkında bir kitap", "ein Buch über Stress") unless the user's own words in that
  phrase make it theirs ("about my stress", "stresim hakkında"); not a condition ("If I feel stressed, ...", "Stresli
  olursam", "Falls ich gestresst bin"); not a past state the same message then sets against the present ("I was
  stressed, but now I feel fine", "Stresliydim ama artık iyiyim"). Without such a statement the check abstains.

Among accepted candidates the one the user stressed is preferred (emphasis words, how many user messages carry the
pattern), then the provider's order; never a random choice. Nothing accepted: no catalog line, the written summary
stays and the existing honest closing runs. These checks reduce wrong lines; they do not prove meaning.
"""
from functools import lru_cache
import json
from pathlib import Path
import re
import unicodedata

from mental_analysis import _TR_M_STEMS, _fold, _is_negation, _is_person, _words

CATALOG_PATH = Path(__file__).resolve().parents[2] / 'shared/mental/closing-catalog/v1/catalog.json'
MAX_CANDIDATES = 3

_FIRST_PERSON = {
    'en': {'i', "i'm", "i've", "i'd", "i'll", 'im', 'me', 'my', 'mine', 'myself', 'we', 'us', 'our', "we're"},
    'de': {'ich', 'mich', 'mir', 'mein', 'meine', 'meinen', 'meinem', 'meiner', 'meines', 'wir', 'uns', 'unser', 'unsere', 'unseren'},
    'tr': {'ben', 'bana', 'beni', 'benim', 'bende', 'benden', 'kendim', 'kendime', 'kendimi', 'biz', 'bize', 'bizi', 'bizim'},
}
# Objects that do not make the user the subject ("My sister is proud of me"): excluded for subject-only patterns.
_OBJECT_ONLY = {'en': {'me', 'us', 'myself'}, 'de': {'mich', 'uns'}, 'tr': {'beni', 'bana', 'bizi', 'bize'}}
_THIRD_PERSON = {'en': {'he', 'she', 'they', 'him', 'her', 'them', 'his', 'their', "he's", "she's", "they're"},
                 'de': {'er', 'sie', 'ihm', 'ihn'}, 'tr': {'o', 'onlar', 'ona', 'onu', 'onun', 'onlara'}}
# A negated pattern's own intensifier is part of it ("hiç dinlenemiyorum", "I never get enough rest").
_INTENSIFIER = {'tr': {'hiç', 'hiçbir', 'asla', 'kimse', 'kimsenin', 'kimseye'}, 'en': {'never', 'hardly'}, 'de': {'nie', 'niemals', 'kaum', 'gar'}}
# Subject pronouns: after a third-person subject only these still make the user the experiencer.
_SUBJECT_PRONOUN = {'en': {'i', "i'm", "i've", "i'd", "i'll", 'im', 'we', "we're"}, 'de': {'ich', 'wir'}, 'tr': {'ben', 'biz'}}
_POSSESSIVE = {'en': {'my', 'our'}, 'de': {'mein', 'meine', 'meinen', 'meinem', 'meiner', 'meines', 'unser', 'unsere', 'unseren'}, 'tr': set()}
# Turkish first person: verb or possessive ending, also with a case ("yanımda", "işimde"); person nouns excluded.
_TR_FIRST_PERSON_ENDING = re.compile(r'(?:ım|im|um|üm|ız|iz|uz|üz)(?:da|de|ta|te|dan|den|a|e|ı|i|la|le)?$')
_BREAKS = {'en': {'but', 'though', 'although', 'however', 'yet', 'and', 'or'},
           'de': {'aber', 'sondern', 'doch', 'jedoch', 'und', 'oder'}, 'tr': {'ama', 'fakat', 'ancak', 'oysa', 've', 'veya'}}
_PAST = {
    'tr': re.compile(r'\b(eskiden|önceden|geçmişte|bir zamanlar)\b'),
    'en': re.compile(r"\b((?<!get )(?<!got )(?<!getting )(?<!be )used to|in the past|back then|years ago)\b"),
    'de': re.compile(r'\b(früher|damals|einst)\b'),
}
_NO_LONGER = {
    'tr': re.compile(r'\bartık\b[^.!?]{0,30}\b(değil\w*|yok\w*|\w+m[ıiuü]yor\w*)'),
    'en': re.compile(r"\b(no longer|not anymore|anymore)\b"),
    'de': re.compile(r'\b(nicht mehr|kein\w* \w+ mehr)\b'),
}
_CORRECTION = {
    'tr': re.compile(r'\b(aslında|yanlış anla\w*|öyle değil|hayır)\b'),
    'en': re.compile(r"\b(actually|i mean|not really|that's not|no,)"),
    'de': re.compile(r'\b(eigentlich|nein|stimmt nicht|nicht wirklich)\b'),
}
_EMPHASIS = {
    'tr': re.compile(r'\b(en çok|özellikle|asıl|en büyük|en fazla)\b'),
    'en': re.compile(r'\b(most|especially|mainly|biggest|above all)\b'),
    'de': re.compile(r'\b(vor allem|besonders|am meisten|hauptsächlich)\b'),
}
# Round 7: constructions that carry a cue without stating the user's own current state. They are grammatical markers
# (a preposition or postposition of topic, a conditional, a present-time adverb), never topic nouns such as "book".
# Topic: the cue is what something is about. English and German put the marker before the cue, Turkish after it.
_TOPIC = {
    'en': {'about', 'regarding', 'concerning', 'on', 'topic', 'subject'},
    'de': {'über', 'bezüglich', 'betreffend', 'hinsichtlich', 'thema'},
    'tr': {'hakkında', 'hakkındaki', 'ilgili', 'konusunda', 'konusundaki', 'konulu', 'üzerine', 'dair', 'alakalı'},
}
TOPIC_WINDOW = 4  # words between the marker and the cue, nearest first ("a book about anxiety and stress")
# A pronoun between the marker and the cue is the marker's object; the cue then starts its own statement ("Talking
# about it helps me", "Bunun hakkında konuşmak").
_ANAPHOR = {'en': {'it', 'this', 'that', 'these', 'those', 'them', 'him', 'her', 'you', 'everything', 'something', 'anything', 'things'},
            'de': {'es', 'das', 'dies', 'dieses', 'alles', 'ihn', 'ihm', 'ihnen'},
            'tr': {'bu', 'bunun', 'bunu', 'bunlar', 'bunların', 'şu', 'şunun', 'şunu', 'o', 'onun', 'onu'}}
_CONTRAST = {lang: words - {'and', 'or', 'und', 'oder', 've', 'veya'} for lang, words in _BREAKS.items()}
# Conditional: a subordinator before the cue in the same part of the sentence (up to a comma or a contrast); in
# Turkish also the conditional or "when" suffix on the cue's predicate ("stresli olursam", "gerginsem", "stresli
# olduğumda").
_CONDITIONAL = {
    'en': re.compile(r'\b(if|unless|when|whenever|in case|suppose|supposing)\b'),
    'de': re.compile(r'\b(falls|wenn|sofern|sobald|angenommen|im falle?)\b'),
    'tr': re.compile(r'\b(eğer|şayet)\b'),
}
_TR_CONDITIONAL_ENDING = re.compile(r'(?:[^\Waeıioöuüsy]s[ae](?:m|n|n[ıi]z|l[ae]r)?|[aeıioöuü]ys[ae](?:m|n|k|n[ıi]z|l[ae]r)?|[rz]s[ae]k)$')
_TR_CONDITIONAL_WORDS = {'ise', 'isem', 'isen', 'isek'}
_TR_WHEN_ENDING = re.compile(r'[dt][ıiuü]ğ[ıiuü](?:m|n|m[ıiuü]z|n[ıiuü]z)?n?d[ae]$')
# Past, then present in the same message: the cue's clause is in the past and a later clause of that message speaks
# of now without the cue ("I was stressed, but now I feel fine"). A later clause that repeats the cue keeps it current.
_PAST_WORDS = {'en': {'was', 'were', "wasn't", "weren't", 'had', 'felt', 'got', 'became'},
               'de': {'war', 'waren', 'warst', 'wart', 'hatte', 'hatten', 'hattest', 'fühlte', 'fühlten', 'wurde', 'wurden', 'gewesen'}}
_TR_PAST_ENDING = re.compile(r'(?:[dt][ıiuü](?:m|n|k|n[ıi]z|l[ae]r)?|m[ıiuü]ş(?:[ıiuü]m|s[ıiuü]n|[ıiuü]z|l[ae]r)?)$')
_NOW = {
    'en': re.compile(r'\b(now|nowadays|today|these days|currently|at the moment|at present)\b'),
    'de': re.compile(r'\b(jetzt|nun|inzwischen|mittlerweile|heute|derzeit|momentan|aktuell|zurzeit)\b'),
    'tr': re.compile(r'\b(şimdi|artık|şu an(?:da)?|bugün\w*|günümüzde)\b'),
}
_TR_NOT_PAST = {'şimdi', 'kendi', 'altı', 'üstü', 'yedi'}


@lru_cache(maxsize=1)
def catalog():
    return json.loads(CATALOG_PATH.read_text('utf-8'))


def patterns():
    return {p['id']: p for p in catalog()['patterns']}


def _norm(text, language):
    return re.sub(r'\s+', ' ', _fold(unicodedata.normalize('NFC', str(text)), language)).strip()


def _clause_spans(text, language):
    """(start, end) of clauses: split at punctuation and at clause-break words (but, ama, aber, ...)."""
    spans, start = [], 0
    # Contrast and coordination split clauses ("My friend is stressed and I am worried" holds two subjects); "only"
    # / "nur" / "sadece" do not ("ich schlafe nur schlecht").
    breaks = '|'.join(sorted((re.escape(w) for w in _BREAKS[language]), key=len, reverse=True))
    for match in re.finditer(r'[.!?;,…]+|\b(?:' + breaks + r')\b', text):
        spans.append((start, match.start()))
        start = match.end()
    spans.append((start, len(text)))
    return [(a, b) for a, b in spans if text[a:b].strip()]


def _sentence_spans(text):
    spans, start = [], 0
    for match in re.finditer(r'[.!?…]+', text):
        spans.append((start, match.end()))
        start = match.end()
    spans.append((start, len(text)))
    return spans


def _cue(pattern, text, language):
    for cue in pattern['cues'].get(language, []):
        found = re.search(cue, text)
        if found:
            return found
    return None


def _about_user(clause, language, subject_only=False, object_ok=False):
    """First person in the clause, or (unless the pattern needs the user as subject) an impersonal clause without a
    third person ("Kurze Spaziergänge helfen etwas"). A possessed person ("my mother", "my father's", "annem") is a third
    person. After a third person, a possessive or object form ("My mother is worried about me") no longer makes the
    user the experiencer, except for patterns where others act on the user (object_ok: attention, listening,
    understanding, support)."""
    words = _words(clause, language)
    third = False
    for i, word in enumerate(words):
        nxt = re.sub(r"['’]s$", '', words[i + 1]) if i + 1 < len(words) else ''
        if word in _POSSESSIVE[language] and nxt and _is_person(nxt, language):
            third = True
            continue
        if word in _FIRST_PERSON[language] and not (subject_only and word in _OBJECT_ONLY[language]):
            if third and not object_ok and word not in _SUBJECT_PRONOUN[language]:
                continue
            return True
        if language == 'tr' and _tr_first_person(word):
            return True
        if word in _THIRD_PERSON[language] or _is_person(word, language):
            third = True
    return not third and not subject_only


def _tr_first_person(word):
    return len(word) > 3 and bool(_TR_FIRST_PERSON_ENDING.search(word)) and not _is_person(word, 'tr') \
        and word not in _TR_M_STEMS and not any(word.startswith(s) for s in _TR_M_STEMS)


def _own(word, language):
    return word in _FIRST_PERSON[language] or (language == 'tr' and _tr_first_person(word))


def _word_end(text, at):
    while at < len(text) and (text[at].isalnum() or text[at] in "'’"):
        at += 1
    return at


def _predicate(text, clause, cue_start, cue_end, language):
    """Turkish: the cue's last word and the two words after it in its clause, where the predicate carries tense and
    condition ("stresli olursam", "stresliydim", "kimse beni anlamıyor" -> "anlamıyor")."""
    cue_words = len(_words(text[cue_start:_word_end(text, cue_end)], language))
    return _words(text[cue_start:clause[1]], language)[max(cue_words - 1, 0):][:3]


def _topic(text, sentence, cue_start, cue_end, language):
    """The cue is what something is about, not the user's state: a topic marker within TOPIC_WINDOW words before the
    cue (after it in Turkish), with no first-person word in the cue or in between ("about my stress", "stresim
    hakkında" are the user's own) and no pronoun in between (the marker's object; the cue then starts its own clause)."""
    own_cue = _words(text[cue_start:_word_end(text, cue_end)], language)
    if any(_own(w, language) for w in own_cue):
        return False
    if language == 'tr':
        window = _words(text[_word_end(text, cue_end):sentence[1]], language)[:TOPIC_WINDOW]
    else:
        window = _words(text[sentence[0]:cue_start], language)[::-1][:TOPIC_WINDOW]
    for word in window:
        if word in _TOPIC[language]:
            return True
        if _own(word, language) or word in _ANAPHOR[language] or word in _CONTRAST[language]:
            return False
    return False


def _conditional(text, sentence, clause, cue_start, cue_end, language):
    """The cue is inside a condition: a conditional subordinator before it in the same part of the sentence, or in
    Turkish a conditional / "when" suffix on the cue's predicate (_predicate)."""
    part = re.split(r'[,;:]', text[sentence[0]:cue_start])[-1]
    words = _words(part, language)
    cut = max((i for i, w in enumerate(words) if w in _CONTRAST[language]), default=-1)
    if _CONDITIONAL[language].search(' '.join(words[cut + 1:])):
        return True
    if language != 'tr':
        return False
    after = _predicate(text, clause, cue_start, cue_end, language)
    return any(w in _TR_CONDITIONAL_WORDS or (len(w) > 3 and (_TR_CONDITIONAL_ENDING.search(w) or _TR_WHEN_ENDING.search(w)))
               for w in after)


def _past_then_now(text, clause, cue_start, cue_end, pattern, language):
    """The cue's clause is in the past and a later clause of the same message speaks of now without repeating the cue
    ("I was stressed, but now I feel fine", "Stresliydim ama artık iyiyim", "Ich war gestresst, aber jetzt geht es
    mir gut"). Turkish marks the past on the cue's predicate (_predicate); English and German with a past verb."""
    if language == 'tr':
        after = _predicate(text, clause, cue_start, cue_end, language)
        past = any(len(w) > 3 and w not in _TR_NOT_PAST and _TR_PAST_ENDING.search(w) for w in after)
    else:
        past = any(w in _PAST_WORDS[language] for w in _words(text[clause[0]:clause[1]], language))
    if not past:
        return False
    for a, b in _clause_spans(text, language):
        if a < clause[1] or not _NOW[language].search(text[a:b]):
            continue
        again = _cue(pattern, text[a:b], language)
        if again and not _negated(text[a:b], again.span(), language, pattern.get('negatedCue'), pattern):
            return False
        return True
    return False


def _third(clause, language):
    words = _words(clause, language)
    return any(w in _THIRD_PERSON[language] or _is_person(w, language) for w in words)


# Verbal negation in Turkish (-mıyor, -madı, -maz, -mamak, -mama, -mayan); the privative -sız/-suz ("uykusuzluk") is
# part of a noun, not a negation the user could drop.
_TR_NEGATIVE_MORPHEME = re.compile(r'(m[ıiuü]yor|m[ae]d[ıiğ]|m[ae]z|m[ae]mak|m[ae]mek|m[ae]m[ae]|m[ae]yan|m[ae]yen)\w*$')


def _without_negation(word, language):
    """The word with its negation removed: a negation word disappears; a Turkish verb loses its negative suffix; a
    word whose negation is part of the word itself stays unchanged."""
    if language == 'tr' and not word.startswith(('yok', 'değil', 'hiç', 'asla', 'kimse')):
        return _TR_NEGATIVE_MORPHEME.sub('', word, count=1)
    return ''


def _negated(clause, cue_span, language, negated_cue=False, pattern=None):
    """Negation of the cue in its clause. Outside the cue: any negation word. Inside the cue (round 6): when the cue
    still matches with every removable negation inside it removed, the user negated it ("uykum hiç bölünmüyor", "my
    sleep is not disrupted", "karar vermekte zorlanmıyorum"); otherwise the cue itself is negative ("uyuyamıyorum",
    "I can't sleep", "kimse beni anlamıyor") and an intensifier around it ("hiç", "never", "nie") is emphasis."""
    a, b = cue_span
    inherent = negated_cue
    if pattern is not None:
        inside = clause[a:b]
        negations = [w for w in _words(inside, language) if _is_negation(w, language)]
        removable = [w for w in negations if _without_negation(w, language) != w]
        if removable:
            probe = inside
            for word in removable:
                probe = re.sub(r'(?<!\w)' + re.escape(word) + r'(?!\w)', _without_negation(word, language), probe, count=1)
            if _cue(pattern, probe, language):
                return True
        inherent = inherent or bool(negations)
    outside = clause[:a] + ' ' + clause[b:]
    skip = _INTENSIFIER[language] if inherent else set()
    return any(_is_negation(w, language) and w not in skip for w in _words(outside, language))


def check(candidate, language, messages):
    """None when the candidate passes every check, else the first failed check's name."""
    if not isinstance(candidate, dict):
        return 'malformed'
    pattern = patterns().get(candidate.get('id'))
    if not pattern:
        return 'unknown-id'
    index, quote = candidate.get('messageIndex'), candidate.get('quote')
    if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < len(messages):
        return 'unknown-message'
    message = messages[index]
    if message.get('role') != 'user':
        return 'not-a-user-message'
    if not isinstance(quote, str) or len(quote.strip()) < 3:
        return 'no-quote'
    text, q = _norm(message.get('content', ''), language), _norm(quote, language)
    at = text.find(q)
    if at < 0:
        return 'quote-not-in-message'
    cue = _cue(pattern, q, language)
    if not cue:
        return 'no-cue-in-quote'
    cue_start, cue_end = at + cue.start(), at + cue.end()
    clause = next(((a, b) for a, b in _clause_spans(text, language) if a <= cue_start < b), (0, len(text)))
    body = text[clause[0]:clause[1]]
    if _negated(body, (cue_start - clause[0], min(cue_end, clause[1]) - clause[0]), language, pattern.get('negatedCue'), pattern):
        return 'negated'
    sentence_span = next(((a, b) for a, b in _sentence_spans(text) if a <= cue_start < b), (0, len(text)))
    sentence = text[sentence_span[0]:sentence_span[1]]
    # A subject shared over "and" ("I'm very happy and proud of myself") counts when the clause names no other person.
    shared = pattern.get('subjectOnly') and not _third(body, language) and _about_user(sentence, language, True)
    if not _about_user(body, language, pattern.get('subjectOnly'), pattern.get('objectOk')) and not shared:
        return 'not-about-the-user'
    if any(re.search(rule, body) for rule in pattern.get('exclude', {}).get(language, [])):
        return 'excluded-use'
    if _PAST[language].search(body):
        return 'past'
    if not pattern.get('changeIsTopic') and _NO_LONGER[language].search(sentence):
        return 'no-longer'
    if _topic(text, sentence_span, cue_start, cue_end, language):
        return 'topic-only'
    if _conditional(text, sentence_span, clause, cue_start, cue_end, language):
        return 'conditional'
    if not pattern.get('changeIsTopic') and _past_then_now(text, clause, cue_start, cue_end, pattern, language):
        return 'past-then-now'
    for later in messages[index + 1:]:
        if later.get('role') != 'user':
            continue
        later_text = _norm(later.get('content', ''), language)
        for a, b in _clause_spans(later_text, language):
            part = later_text[a:b]
            again = _cue(pattern, part, language)
            negation = any(_is_negation(w, language) for w in _words(part, language))
            if (again and _negated(part, again.span(), language, pattern.get('negatedCue'), pattern)) or (_CORRECTION[language].search(part) and negation):
                return 'corrected-later'
    return None


def _support(pattern, language, messages):
    count = 0
    for message in messages:
        if message.get('role') != 'user':
            continue
        text = _norm(message.get('content', ''), language)
        for a, b in _clause_spans(text, language):
            found = _cue(pattern, text[a:b], language)
            if found and not _negated(text[a:b], found.span(), language, pattern.get('negatedCue'), pattern) and _about_user(text[a:b], language, pattern.get('subjectOnly'), pattern.get('objectOk')):
                count += 1
    return count


def select(candidates, language, messages):
    """(pattern id or None, status, checks): the first checked candidate the user stressed most, else None."""
    if not isinstance(candidates, list) or not candidates:
        return None, 'no-candidate', []
    checks, accepted = [], []
    for rank, candidate in enumerate(candidates[:MAX_CANDIDATES]):
        reason = check(candidate, language, messages)
        checks.append({'id': candidate.get('id') if isinstance(candidate, dict) else None, 'result': reason or 'accepted'})
        if reason is None:
            pattern = patterns()[candidate['id']]
            quote_clause = _norm(messages[candidate['messageIndex']].get('content', ''), language)
            emphasis = 2 if _EMPHASIS[language].search(quote_clause) else 0
            accepted.append((-(emphasis + _support(pattern, language, messages)), rank, candidate['id']))
    if not accepted:
        return None, 'no-reliable-match', checks
    return sorted(accepted)[0][2], 'catalog', checks


def catalog_version():
    return catalog()['version']


def spoken_text(pattern_id, language):
    return patterns()[pattern_id]['text'][language]


def prompt_rules(language):
    """Inserted into the analysis prompt (normal closing only)."""
    lines = '\n'.join(f"{p['id']}: {p['text'][language]} — use when: {p['condition']}" for p in catalog()['patterns'])
    return ('closingCandidates is required: a list of up to 3 objects with the keys id (a catalog id from the list below, '
            'such as C09), messageIndex (the number in brackets before the user message) and quote (words copied from that '
            'message); fill it with the catalog line(s) that state what the user said about themselves, ordered by what the '
            'user stressed most; never copy an example value. '
            'messageIndex is the number in brackets before a USER message; quote is copied character for character from '
            'that user message (never from the assistant). Choose a line only when the user said it about themselves, now, '
            'without negation; not for someone else, not for something that is over, not from an assistant suggestion, '
            'not when the user later corrected it. Do not infer (living alone is not loneliness; having responsibilities '
            'is not being strained; others not listening is not difficulty expressing oneself; resting is not being '
            'listened to). A conversation about good things gets a positive line, never a problem line. '
            'Return [] when nothing fits.\nCatalog:\n' + lines + '\n')
