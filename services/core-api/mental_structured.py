"""Offline wellbeing routing. No provider, TTS, disk writes or transcript logging.

Request-scoped state stays in the active browser session. Scores describe routing
confidence, not mental health, and are not calibrated clinical probabilities.
"""
import json
import math
import random
import re
import unicodedata
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[2]
OBJECTIVE_CONFIDENCE_THRESHOLD = .75
NODES = tuple(f'B{i:02}' for i in range(1, 13))
SPECIAL = ('C01', 'C02', 'L01', 'F01', 'P01', 'D01')
Node = Literal['B01','B02','B03','B04','B05','B06','B07','B08','B09','B10','B11','B12','C01','C02','L01','F01','P01','D01']


class FlowState(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: Literal['v1'] = 'v1'
    language: Literal['tr','en','de']
    speakerProfile: Literal['official-default'] = 'official-default'
    seed: int = Field(default=1, ge=0, le=2**32-1)
    turn: int = Field(default=0, ge=0, le=40)
    asked: list[Node] = Field(default_factory=list, max_length=40)
    fulfilled: list[Node] = Field(default_factory=list, max_length=20)
    skipped: list[Node] = Field(default_factory=list, max_length=20)
    selections: list[str] = Field(default_factory=list, max_length=40)
    aHistory: list[str] = Field(default_factory=list, max_length=40)
    lastNode: Node | None = None
    clarifyFor: Node | None = None
    uncertainTurns: int = Field(default=0, ge=0, le=40)
    listenOnly: bool = False
    wantsSteps: bool = False
    topic: str | None = Field(default=None, max_length=32)


@lru_cache(maxsize=1)
def content():
    return json.loads((ROOT/'shared/mental/v1/content.json').read_text('utf-8'))


@lru_cache(maxsize=1)
def flow_spec():
    return json.loads((ROOT/'shared/mental/v1/flow.json').read_text('utf-8'))


def normalize(text):
    return unicodedata.normalize('NFC', text).casefold().replace('i\u0307','i').replace('’', "'")


# Character n-gram retrieval tolerates small ASR/spelling errors. These authored
# prototypes are development examples, never production user transcripts.
PROTOTYPES = {
    'stress': ['I feel anxious and overwhelmed by pressure', 'I am stressed about work', 'İş baskısı beni çok kaygılandırıyor', 'Kendimi stresli hissediyorum', 'Ich fühle mich gestresst und überfordert', 'Ich mache mir Sorgen wegen der Arbeit'],
    'sadness': ['I feel sad after losing my job', 'I miss someone I lost', 'İşimi kaybettim çok üzgünüm', 'Kaybettiğim kişiyi özlüyorum', 'Ich bin traurig nach dem Verlust', 'Ich vermisse meine Familie'],
    'anger': ['I am angry after an argument with my friend', 'I feel furious about our conflict', 'Arkadaşımla tartıştım ve öfkeliyim', 'Çok kızgınım', 'Ich bin wütend nach unserem Streit', 'Ich ärgere mich über den Konflikt'],
    'positive': ['I am happy and proud of myself', 'I feel good and peaceful today', 'Bugün mutlu ve huzurluyum', 'Kendimle gurur duyuyorum', 'Ich bin glücklich und stolz', 'Heute fühle ich mich gut und entspannt'],
    'uncertainty': ['I cannot decide what to do', 'I am unsure about my choice', 'Ne yapacağıma karar veremiyorum', 'Seçimim konusunda kararsızım', 'Ich kann mich nicht entscheiden', 'Ich bin unsicher wegen meiner Entscheidung'],
}


def grams(text):
    value = ' '+re.sub(r'\s+', ' ', normalize(text))+' '
    return Counter(value[i:i+n] for n in (3,4) for i in range(len(value)-n+1))


def similarity(a,b):
    return sum(v*b.get(k,0) for k,v in a.items()) / (math.sqrt(sum(v*v for v in a.values())*sum(v*v for v in b.values())) or 1)


@lru_cache(maxsize=1)
def prototype_vectors():
    return {label:[grams(s) for s in samples] for label,samples in PROTOTYPES.items()}


PATTERNS = {
 'B02': r'\b(feel|felt|sad|happy|angry|anxious|worried|üzgün\w*|mutlu\w*|öfke\w*|kızgın\w*|kaygı\w*|hisset\w*|traurig\w*|glücklich\w*|wütend\w*|ängstlich\w*|fühl\w*)\b',
 'B03': r'\b(lost my job|fired|happened|argued|died|broke up|işimi kaybettim|işten çıkarıldım|tartıştık|tartıştım|vefat|ayrıldık|verloren|gekündigt|gestorben|gestritten|getrennt)\b',
 'B04': r'\b(whenever|every time|trigger\w*|her seferinde|tetikl\w*|ne zaman .* olsa|jedes mal|immer wenn|auslös\w*)\b',
 'B05': r'\b(i thought|i think|i told myself|aklımdan|düşün\w*|kendime .* dedi\w*|ich dachte|ich denke|durch den kopf)\b',
 'B06': r'\b(every day|daily|once a week|twice|often|her gün|her gece|haftada|sık sık|jeden tag|täglich|jede woche|häufig)\b',
 'B07': r'\b(cannot sleep|can\x27t sleep|affects my|cannot concentrate|can\x27t concentrate|uyuyam\w*|odaklanam\w*|günlük .* etkil\w*|nicht schlafen|nicht konzentrieren|alltag .* beeinträchtigt)\b',
 'B08': r'\b(i usually|i tend to|genellikle .* yap\w*|genelde|ich reagiere|meistens mache ich)\b',
 'B09': r'\b(helped|used to help|işe yaradı|yardımcı oldu|iyi gelmişti|geholfen|hat mir gutgetan)\b',
 'B10': r'\b(i need|i want support|ihtiyacım|destek istiyorum|ich brauche|ich wünsche mir unterstützung)\b',
 'B11': r'\b(i will try|my next step|deneyeceğim|sonraki adımım|ich werde .* versuchen|mein nächster schritt)\b',
}
UNKNOWN = r'\b(i don\x27t know|do not know|no idea|not sure|bilmiyorum|bilemedim|emin değilim|weiß nicht|weiss nicht|keine ahnung|nicht sicher)\b'
NO_ADVICE = r'\b(no advice|don\x27t want advice|do not want advice|just (?:want to )?talk|only (?:want to )?talk|tavsiye istemiyorum|öneri istemiyorum|sadece konuşmak|yalnızca konuşmak|keine ratschläge|keinen rat|nur reden|nur erzählen)\b'
STEPS = r'\b(want advice|what can i do|next step|öneri istiyorum|ne yapabilirim|bir adım|was kann ich tun|möchte einen rat|nächsten schritt)\b'
SKIP = r'^(?:skip(?: this)?|pass|geç(?:elim)?|atla|bunu geçelim|überspringen|weiter)[.! ]*$'
TOPIC_CHANGE = r'\b(change (?:the )?topic|something else|başka bir konu|konuyu değişt|anderes thema|thema wechseln)\w*'


def classify(text, state):
    value=normalize(text)
    vector=grams(value)
    scores=sorted(((label,max(similarity(vector,p) for p in ps)) for label,ps in prototype_vectors().items()),key=lambda x:-x[1])
    topic,score=scores[0]
    # Topic retrieval abstains on weak/close scores or explicit negation. We do
    # not turn a negated emotion into its opposite, or infer a user's mood.
    negation=bool(re.search(r'\b(not|never|nicht|kein\w*|değil\w*|yok)\b',value))
    if score < .30 or score-scores[1][1] < .06 or negation: topic=None
    unknown=bool(re.search(UNKNOWN,value))
    objectives={node for node,pattern in PATTERNS.items() if re.search(pattern,value)}
    # Negated feelings still supply emotional information; no sentiment is
    # assigned. Ambiguous and contradictory language asks for clarification.
    contradictory=bool(re.search(r'\b(but|ama|fakat|aber)\b',value) and negation)
    if unknown or contradictory:objectives=set()
    confident=bool(objectives) and not unknown and not contradictory
    target=state.clarifyFor if state.lastNode in ('C01','P01') else state.lastNode
    if target and target.startswith('B') and not unknown and not contradictory and not re.search(TOPIC_CHANGE,value):
        # Contextual answers can be brief. Bare yes/no is insufficient for an
        # open objective and never silently fulfills a node.
        if len(value.split())>=3 and not re.fullmatch(r'(yes|no|okay|evet|hayır|tamam|ja|nein|gut)[.! ]*',value):
            objectives.add(target);confident=True
    if confident:objectives.add('B01')
    return dict(topic=topic,confidence=.85 if confident else .25,fulfilled=sorted(objectives),
                uncertain=unknown or contradictory or not confident,
                listenOnly=bool(re.search(NO_ADVICE,value)),wantsSteps=bool(re.search(STEPS,value)) and not bool(re.search(NO_ADVICE,value)),
                skip=bool(re.fullmatch(SKIP,value)),topicChange=bool(re.search(TOPIC_CHANGE,value)),
                sentiment='unspecified' if negation else topic,method='char-ngram-dialogue-grammar-v1')


def select(node,state):
    rows=[r for r in content()['rows'] if r['language']==state.language and r['questionNodeId']==node]
    rng=random.Random(state.seed+state.turn*104729)
    choices=[]
    for b in rows:
        for aid in b['compatibleAPhrases'] or [None]:
            response_id=f"{state.language}-{aid or 'none'}-{b['variantId']}"
            score=(response_id in state.selections, aid== (state.aHistory[-1] if state.aHistory else None) if aid else False,state.aHistory.count(aid) if aid else 0)
            choices.append((score,rng.random(),b,aid,response_id))
    _,_,b,aid,response_id=min(choices,key=lambda c:(c[0],c[1]))
    a=next((r for r in content()['rows'] if r['language']==state.language and r['variantId']==aid),None)
    state.selections.append(response_id)
    if aid:state.aHistory.append(aid)
    state.asked.append(node);state.lastNode=node
    selected=([a] if a else [])+[b]
    return dict(reply=' '.join(r['exactText'] for r in selected),providerType='STRUCTURED_LOCAL',isCrisis=False,
                structuredState=state.model_dump(),audioAssetIds=[r['audioAssetId'] for r in selected],
                responseId=response_id,speakerProfile=state.speakerProfile,
                metrics={'conversationalOpenAICalls':0,'dynamicTTSCalls':0})


def route(text,language,state=None,control=None,is_driving=False):
    state=FlowState(language=language) if state is None else state.model_copy(deep=True)
    if state.language != language:raise HTTPException(409,'STRUCTURED_LANGUAGE_CHANGED_RESTART_REQUIRED')
    if state.turn>=40:raise HTTPException(409,'STRUCTURED_SESSION_LIMIT')
    if state.lastNode=='F01':raise HTTPException(409,'STRUCTURED_SESSION_COMPLETED')
    state.turn+=1
    if is_driving:node='D01'
    elif control:
        if control.get('sessionAction')=='pause':state.clarifyFor=state.lastNode
        node={'finish':'F01','pause':'P01'}.get(control.get('sessionAction'),'C02')
    else:
        result=classify(text,state)
        if result['wantsSteps']:state.listenOnly=False
        state.listenOnly |= result['listenOnly'];state.wantsSteps |= result['wantsSteps']
        state.fulfilled=sorted(set(state.fulfilled)|set(result['fulfilled']))
        if result['topic']:state.topic=result['topic']
        if result['skip']:
            target=state.clarifyFor or state.lastNode
            if target in NODES:state.skipped=sorted(set(state.skipped)|{target})
            state.clarifyFor=None
        if state.lastNode=='B12' and not result['uncertain']:node='F01'
        elif state.listenOnly:node='L01'
        elif result['topicChange']:
            # Completed objectives remain complete; let the user lead instead
            # of re-running the interview under a guessed new topic.
            node='L01';state.clarifyFor=None
        elif state.turn==1 and re.fullmatch(r'(hello|hi|hey|merhaba|selam|hallo|guten tag)[.! ]*',normalize(text)):
            node='B01'
        elif result['confidence']<OBJECTIVE_CONFIDENCE_THRESHOLD and not result['skip']:
            state.uncertainTurns+=1
            if state.lastNode not in ('C01','C02'):
                state.clarifyFor=state.lastNode;node='C01'
            else:
                if state.clarifyFor in NODES:state.skipped=sorted(set(state.skipped)|{state.clarifyFor})
                state.clarifyFor=None;node='C02' if state.lastNode=='C01' else 'L01'
        else:
            state.clarifyFor=None
            excluded=set(state.fulfilled+state.skipped+state.asked)
            # Positive wellbeing does not require a problem exploration. Action
            # questions require the user's explicit interest, even in this mode.
            order=flow_spec()['positiveOrder'] if state.topic=='positive' else flow_spec()['defaultOrder']
            node=next((n for n in order if n not in excluded and (n!='B11' or state.wantsSteps)),'F01')
    output=select(node,state)
    output['decision']={'node':node,'classifier':'char-ngram-dialogue-grammar-v1','objectiveThreshold':OBJECTIVE_CONFIDENCE_THRESHOLD,'turn':state.turn}
    if node in ('F01','P01','D01'):output['sessionAction']='finish' if node=='F01' else 'pause'
    return output


def require_approved_library(language):
    """No draft/silent dynamic fallback, and no externally supplied asset URLs."""
    manifest=json.loads((ROOT/'apps/vehicle-app/public/audio/mental/v1/manifest.json').read_text('utf-8'))
    if content()['reviewStatus']!='approved' or manifest.get('joinApprovalStatus')!='approved':
        raise HTTPException(503,'STRUCTURED_CONTENT_AND_AUDIO_REVIEW_REQUIRED')
    expected={r['audioAssetId']:r for r in content()['rows'] if r['language']==language}
    entries={e['assetId']:e for e in manifest['entries'] if e['language']==language}
    if set(entries)!=set(expected):raise HTTPException(503,'STRUCTURED_AUDIO_INCOMPLETE')
    for key,row in expected.items():
        e=entries[key]
        if (e['approvalStatus']!='approved' or e['exactScript']!=row['exactText'] or e['speakerProfile']!=row['speakerProfile']
            or not re.fullmatch(r'[0-9a-f]{64}',e.get('sha256') or '') or not e.get('durationMs') or not e.get('bytes')):
            raise HTTPException(503,'STRUCTURED_AUDIO_UNAPPROVED')
