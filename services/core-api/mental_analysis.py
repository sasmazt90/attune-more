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
