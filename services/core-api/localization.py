"""Request-scoped presentation localization; IDs, values and stored data stay raw."""
from contextvars import ContextVar
import json
from pathlib import Path
import re
import unicodedata
from starlette.responses import JSONResponse

LANGUAGES = {'tr': 'tr-TR', 'en': 'en-US', 'de': 'de-DE'}
request_language = ContextVar('attune_request_language', default='tr')
_catalog_path = Path(__file__).resolve().parents[2] / 'shared/localization/messages.json'
_messages = list(json.loads(_catalog_path.read_text('utf-8')).values())
_normal = lambda value: ' '.join(unicodedata.normalize('NFC',value).split())
_by_source = {_normal(row['tr']): row for row in _messages}
_templates = []
def _template_literal(value):
    if not value.strip(' '):
        return r'\s*' if value else ''
    return (r'\s*' if value.startswith(' ') else '') + re.escape(value.strip(' ')) + (r'\s*' if value.endswith(' ') else '')
for _row in _messages:
    if re.search(r'\{\d+\}', _row['tr']):
        _fields = [int(v) for v in re.findall(r'\{(\d+)\}', _row['tr'])]
        _parts = re.split(r'\{\d+\}', _row['tr'])
        _templates.append((_row, _fields, re.compile('^' + '(.*?)'.join(map(_template_literal, _parts)) + '$')))
_templates.sort(key=lambda item:len(re.sub(r'\{\d+\}','',item[0]['tr'])),reverse=True)

def current_language():
    return request_language.get()

def translate(value, language=None, depth=0):
    language = language or current_language()
    if language == 'tr' or not isinstance(value, str):
        return value
    normalized = _normal(value)
    direct = _by_source.get(normalized)
    if direct and direct.get(language):
        return direct[language]
    if depth < 3 and len(normalized) <= 6000:
        for row, fields, pattern in _templates:
            match = pattern.fullmatch(normalized)
            if match and row.get(language):
                values = {field: translate(match[i+1], language, depth+1) for i,field in enumerate(fields)}
                return re.sub(r'\{(\d+)\}', lambda m: values[int(m[1])], row[language])
    return value

DISPLAY_FIELDS = frozenset(('reply','message','displayMessage','detail','summaryText','description','label','title',
    'note','recommendation','suggestedAction','baselineDiffNote',
    'professionalSupportReason','reason','warning','warnings','providerLabel','sourceBadge',
    'specialty','locationLabel','displayTime','clinicalDisclaimer','disclaimer','emergencyContact',
    'handoffNote','suggestedActionNote','nameTr'))
PROTECTED_FIELDS = frozenset(('userMessage','content','transcript','displayName','driverName','name','id','themeId',
    'recordId','sessionId','providerType','model','url','dateTime','timeZone','themes','detectedThemes','recurringThemes'))

def localize_payload(value, field=None):
    if current_language() == 'tr' or field in PROTECTED_FIELDS:
        return value
    if isinstance(value, dict):
        return {key: localize_payload(item,key) for key,item in value.items()}
    if isinstance(value, list):
        return [localize_payload(item,field) for item in value]
    if field in DISPLAY_FIELDS and isinstance(value,str):
        return translate(value)
    return value

class LocalizedJSONResponse(JSONResponse):
    def render(self, content):
        return super().render(localize_payload(content))

LANGUAGE_NAMES = {'tr':'Turkish','en':'English','de':'German'}

def normalized_mental_input(value):
    """Map translated theme vocabulary to the unchanged deterministic TR rules.

    This transient search representation is never stored as the user's utterance.
    The original message remains the conversation/context record.
    """
    if current_language() == 'tr':
        return value.lower()
    text = value.casefold()
    vocabulary = {
        'sleep':'uyku','schlaf':'uyku','night':'gece','nacht':'gece',
        'stress':'stres','work':'iş','arbeit':'iş','pressure':'baskı','druck':'baskı',
        'project':'proje','projekt':'proje','meeting':'toplantı','besprechung':'toplantı',
        'tired':'yorgun','müde':'yorgun','exhausted':'tüken','erschöpft':'tüken',
        'energy':'enerji','energie':'enerji','family':'aile','familie':'aile',
        'friend':'arkadaş','freund':'arkadaş','anxiety':'kaygı','angst':'kaygı',
        'worry':'endişe','sorge':'endişe','panic':'panik','traffic':'trafik','verkehr':'trafik',
        'relaxed':'rahat','entspannt':'rahat','calm':'sakin','ruhig':'sakin',
        'happy':'mutlu','glücklich':'mutlu','rest':'dinlen','ausruhen':'dinlen',
    }
    for source,target in vocabulary.items():
        text = re.sub(r'(?<!\w)'+re.escape(source)+r'(?!\w)',target,text)
    return text
