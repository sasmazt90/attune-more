"""Stateless hybrid candidates. Only the client winner commits the returned flow state.

The personal acknowledgement is grounded in the live conversation; its exact
catalog follow-up keeps the objective state tied to the question actually heard.
No model, voice, catalogue or worker settings are changed here.
"""
import re
from fastapi import HTTPException
from mental_structured import require_approved_library, route, content


def candidate(text, language, state, control=None, finish_after_reply=False):
    require_approved_library(language)
    return route(text, language, state, control, False, finish_after_reply)


def personalize(provider, text, history, prepared, previous):
    provider.hybrid_acknowledgement = True
    reply = provider.generate_reply(text, False, history)
    acknowledgement = reply.get('reply','').strip()
    # Never truncate meaning or silently play a partial answer.
    if (reply.get('providerType') != 'LIVE_OPENAI' or not acknowledgement
            or len(acknowledgement.split()) > 12 or re.search(r'[?？\n*#]',acknowledgement)):
        raise HTTPException(503,'HYBRID_PERSONAL_UNAVAILABLE')
    selected = [row for row in content()['rows'] if row['audioAssetId'] in prepared['audioAssetIds']]
    # A-only listening acknowledgements have no question. C/L retain their exact neutral invitation.
    follow_up = ' '.join(row['exactText'] for row in selected if row['questionNodeId'] != 'A')
    text = ' '.join(x for x in [acknowledgement,follow_up] if x)
    if len(text.split()) > 25:
        raise HTTPException(503,'HYBRID_PERSONAL_UNAVAILABLE')
    state = dict(prepared['structuredState'])
    state['selections'] = [*state['selections'][:-1], 'personal:'+prepared['responseId']]
    state['aHistory'] = list(previous.aHistory) if previous else []
    return {**prepared,'reply':text,'providerType':'LIVE_OPENAI','audioAssetIds':[],
            'structuredState':state,'metrics':{'conversationalOpenAICalls':1,'dynamicTTSCalls':1}}
