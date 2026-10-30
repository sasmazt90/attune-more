"""Authored, synthetic routing/contract tests; no paid requests or clinical claims."""
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace
import wave

import pytest
from fastapi.testclient import TestClient

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'services/core-api'))
import main
from localization import request_language
from mental_structured import FlowState, route, classify, content, select, NODES, require_approved_library
from mental_provider import OpenAICompatibleSessionAnalyzer
from mental_analysis import validate_analysis, relevant_history


@pytest.mark.parametrize('language,text',[
 ('tr','Dün işimi kaybettim ve çok üzgünüm.'),
 ('en','I lost my job yesterday and I feel sad.'),
 ('de','Ich habe gestern meinen Job verloren und bin traurig.'),
])
def test_already_supplied_information_is_never_asked(language,text):
    result=route(text,language)
    assert {'B01','B02','B03'}<=set(result['structuredState']['fulfilled'])
    assert result['structuredState']['lastNode']=='B07'
    assert result['metrics']=={'conversationalOpenAICalls':0,'dynamicTTSCalls':0}


@pytest.mark.parametrize('language,unknown,advice,skip',[
 ('tr','Bilmiyorum','Sadece konuşmak istiyorum, tavsiye istemiyorum','geçelim'),
 ('en',"I don't know",'I just want to talk, no advice','skip'),
 ('de','Ich weiß nicht','Ich möchte nur reden, keine Ratschläge','überspringen'),
])
def test_clarification_skip_and_user_direction(language,unknown,advice,skip):
    state=FlowState(language=language,lastNode='B05',asked=['B05'])
    a=route(unknown,language,state);assert a['structuredState']['lastNode']=='C01'
    b=route(unknown,language,FlowState(**a['structuredState']));assert b['structuredState']['lastNode']=='C02'
    assert 'B05' in b['structuredState']['skipped']
    c=route(advice,language,state);assert c['structuredState']['lastNode']=='L01' and c['structuredState']['listenOnly']
    d=route(skip,language,state);assert 'B05' in d['structuredState']['skipped'] and d['structuredState']['lastNode']!='B05'


@pytest.mark.parametrize('language,text',[
 ('en','I am not happy but I do not know what I feel'),
 ('de','Ich bin nicht glücklich aber ich weiß nicht was ich fühle'),
 ('tr','Mutlu değilim ama ne hissettiğimi bilmiyorum'),
])
def test_negation_contradiction_does_not_invent_emotion(language,text):
    state=FlowState(language=language,lastNode='B02',asked=['B02'])
    result=classify(text,state)
    assert result['sentiment']=='unspecified' and result['uncertain']
    assert not result['fulfilled']
    assert route(text,language,state)['structuredState']['lastNode']=='C01'


@pytest.mark.parametrize('language,text',[
 ('en','I am happy and proud of myself'),('tr','Bugün mutlu ve huzurluyum'),('de','Ich bin glücklich und stolz')])
def test_positive_path_and_no_forced_action(language,text):
    result=route(text,language)
    assert result['structuredState']['topic']=='positive'
    assert result['structuredState']['lastNode']=='B10'
    assert not result['structuredState']['wantsSteps']


def test_dialogue_objective_answer_and_no_repeat():
    state=FlowState(language='en',lastNode='B05',asked=['B05'],fulfilled=['B01','B02','B03'])
    answer=route('It would all go wrong', 'en',state)
    assert 'B05' in answer['structuredState']['fulfilled']
    # Repeatedly supplying valid contextual answers never re-asks a B node.
    state=FlowState(**answer['structuredState'])
    for _ in range(15):
        result=route('There is something meaningful for me here','en',state)
        state=FlowState(**result['structuredState'])
        if state.lastNode=='F01':break
    asked=[n for n in state.asked if n in NODES]
    assert len(set(asked))==len(asked)
    assert state.lastNode=='F01'
    with pytest.raises(Exception):route('continue','en',state)


def test_topic_change_preserves_completed_nodes_and_no_advice_can_be_reversed():
    state=FlowState(language='en',fulfilled=['B01','B02'],lastNode='B03',asked=['B03'])
    result=route('I want to change the topic','en',state)
    assert result['structuredState']['lastNode']=='L01'
    assert result['structuredState']['fulfilled']==['B01','B02']
    state=FlowState(language='en',listenOnly=True)
    result=route('I want advice about my next step','en',state)
    assert result['structuredState']['wantsSteps'] and not result['structuredState']['listenOnly']


def test_unreported_feelings_are_not_presupposed_and_pause_preserves_clarification():
    state=FlowState(language='en',lastNode='B07',asked=['B02','B07'],skipped=['B02'],fulfilled=['B01','B03'])
    result=route('It takes longer to get through my day','en',state)
    assert result['structuredState']['lastNode'] not in ('B04','B06','B08')
    state=FlowState(language='en',lastNode='C01',clarifyFor='B05',asked=['B05','C01'])
    paused=route('pause','en',state,control={'sessionAction':'pause'})
    assert paused['structuredState']['clarifyFor']=='B05'


@pytest.mark.parametrize('language',['tr','en','de'])
def test_limit_closes_after_current_turn_without_another_question(language):
    state=FlowState(language=language,turn=38)
    result=route('A synthetic statement',language,state)
    assert result['structuredState']['lastNode']=='F01' and result['sessionAction']=='finish'
    result=route('A synthetic statement',language,finish_after_reply=True)
    assert result['structuredState']['lastNode']=='F01'
    # Explicit pause and the driving restriction keep their precedence.
    assert route('pause',language,state,control={'sessionAction':'pause'})['structuredState']['lastNode']=='P01'
    assert route('hello',language,state,is_driving=True)['structuredState']['lastNode']=='D01'


def test_question_scope_compatibility_and_grouped_benchmark_corpus():
    rows=content()['rows']
    for row in rows:
        if row['questionNodeId'] in NODES:
            assert row['exactText'].count('?')==1
            assert row['compatibleAPhrases']
        if row['questionNodeId'] in ('B01','B12'):
            assert not {'A-V04','A-V07','A-V11'}&set(row['compatibleAPhrases'])
    corpus=json.loads((ROOT/'tests/fixtures/mental-routing-v2.json').read_text())
    assert len(corpus['rows'])==180
    groups={split:{r['scenarioId'] for r in corpus['rows'] if r['split']==split} for split in ('train','dev','test')}
    assert not groups['train']&groups['dev'] and not groups['train']&groups['test'] and not groups['dev']&groups['test']
    assert all(sum(r['language']==language for r in corpus['rows'])==60 for language in ('tr','en','de'))


def test_listening_varies_global_acknowledgments_and_uncertainty_cannot_loop():
    state=FlowState(language='en',listenOnly=True,lastNode='L01')
    previous=None
    for _ in range(15):
        result=route('I just want to talk, no advice','en',state)
        assert len(result['audioAssetIds'])==1 and '/A/' in result['audioAssetIds'][0]
        assert result['audioAssetIds'][0]!=previous
        assert '?' not in result['reply']
        previous=result['audioAssetIds'][0];state=FlowState(**result['structuredState'])
    state=FlowState(language='en',lastNode='B05',asked=['B05'])
    nodes=[]
    for _ in range(7):
        result=route("I don't know",'en',state);state=FlowState(**result['structuredState']);nodes.append(state.lastNode)
    assert nodes==['C01','C02','L01','L01','L01','L01','L01']


def test_variations_are_seeded_compatible_and_balanced():
    for lang in ('tr','en','de'):
        a,b=FlowState(language=lang,seed=45),FlowState(language=lang,seed=45)
        for turn in range(30):
            a.turn=b.turn=turn
            one,two=select('B02',a),select('B02',b)
            assert one['responseId']==two['responseId']
            row=next(r for r in content()['rows'] if r['audioAssetId']==one['audioAssetIds'][-1])
            assert a.aHistory[-1] in row['compatibleAPhrases']
        assert all(x!=y for x,y in zip(a.aHistory,a.aHistory[1:]))
        assert len(set(a.selections))==30
        assert len(set(a.aHistory[:12]))==12


def test_catalog_semantic_parity_and_truthful_pending_manifest():
    rows=content()['rows'];keys=[r['audioAssetId'] for r in rows]
    assert len(set(keys))==414
    manifest=json.loads((ROOT/'apps/vehicle-app/public/audio/mental/v1/female-calm-v1-manifest.json').read_text())
    entries={e['assetId']:e for e in manifest['entries']}
    for lang in ('tr','en','de'):
        assert sum(r['language']==lang and r['questionNodeId']=='A' for r in rows)==12
        for node in NODES:
            variants=[r for r in rows if r['language']==lang and r['questionNodeId']==node]
            assert len(variants)==10 and len({r['exactText'] for r in variants})==10
            assert len({r['semanticSubtype'] for r in rows if r['questionNodeId']==node})==1
    for row in rows:
        entry=entries[row['audioAssetId']]
        assert row['exactText']==entry['exactScript']
        assert entry['speakerProfile']=='female-calm-v1'
        assert entry['approvalStatus'] in ('pending-generation','synthesized-awaiting-validation','validated','approved')
        if entry['approvalStatus']=='pending-generation':assert entry.get('sha256') is None
        else:
            import hashlib
            path=ROOT/'apps/vehicle-app/public'/entry['audioPath'].lstrip('/')
            assert hashlib.sha256(path.read_bytes()).hexdigest()==entry['sha256']
            assert entry['durationMs']>0 and entry['sampleRate']==24000
    if content()['reviewStatus']=='approved' and all(e['approvalStatus']=='approved' for e in manifest['entries'] if e['language']=='tr'):
        require_approved_library('tr')
    else:
        with pytest.raises(Exception) as caught:require_approved_library('tr')
        assert caught.value.status_code==503


def test_library_gate_refuses_one_unapproved_asset_after_content_review(monkeypatch):
    import copy
    import mental_structured
    library=copy.deepcopy(mental_structured.audio_manifest())
    for entry in library['entries']:
        entry['approvalStatus']='approved'
        entry.setdefault('sha256','a'*64);entry.setdefault('durationMs',1000);entry.setdefault('bytes',48044)
    next(e for e in library['entries'] if e['language']=='tr')['approvalStatus']='synthesized-awaiting-validation'
    reviewed={**content(),'reviewStatus':'approved'}
    monkeypatch.setattr(mental_structured,'content',lambda:reviewed)
    monkeypatch.setattr(mental_structured,'audio_manifest',lambda:library)
    with pytest.raises(Exception) as caught:require_approved_library('tr')
    assert caught.value.status_code==503


def forbidden(*args,**kwargs):raise AssertionError('External provider invoked')


def test_backend_flag_audio_gate_controls_and_crisis_precedence(monkeypatch):
    monkeypatch.setattr(main,'get_active_mental_provider',forbidden)
    client=TestClient(main.app)
    normal={'userMessage':'I feel sad','engine':'structured-v1','cloudConsent':True}
    monkeypatch.delenv('ATTUNE_MENTAL_STRUCTURED_ENABLED',raising=False)
    assert client.post('/api/mental/converse',json=normal).status_code==409
    crisis={**normal,'userMessage':'I want to kill myself'}
    assert client.post('/api/mental/converse',json=crisis).json()['isCrisis']
    monkeypatch.setenv('ATTUNE_MENTAL_STRUCTURED_ENABLED','1')
    import mental_structured
    import copy
    # Exercise the real API gate with an explicit unapproved fixture even after
    # the checked-in production catalog has completed its authorized validation.
    library=copy.deepcopy(mental_structured.audio_manifest())
    for entry in library['entries']:entry['approvalStatus']='approved'
    next(e for e in library['entries'] if e['language']=='tr')['approvalStatus']='synthesized-awaiting-validation'
    reviewed={**mental_structured.content(),'reviewStatus':'approved'}
    monkeypatch.setattr(mental_structured,'content',lambda:reviewed)
    monkeypatch.setattr(mental_structured,'audio_manifest',lambda:library)
    blocked=client.post('/api/mental/converse',json=normal)
    assert blocked.status_code==503 and blocked.json()['detail']=='STRUCTURED_AUDIO_UNAPPROVED'
    monkeypatch.setattr(mental_structured,'require_approved_library',lambda language:None)
    assert client.post('/api/mental/converse?language=en',json=normal).json()['providerType']=='STRUCTURED_LOCAL'
    for word,action in [('finish','finish'),('pause','pause')]:
        response=client.post('/api/mental/converse?language=en',json={**normal,'userMessage':word}).json()
        assert response['sessionAction']==action and response['audioAssetIds']
    monkeypatch.setitem(main.vehicle_state,'vehicleMoving',True)
    response=client.post('/api/mental/converse',json=normal).json()
    assert response['structuredState']['lastNode']=='D01' and response['sessionAction']=='pause'
    assert '112' in client.post('/api/mental/converse',json=crisis).json()['reply']


def test_state_bounds_and_locale_restart(monkeypatch):
    monkeypatch.setenv('ATTUNE_MENTAL_STRUCTURED_ENABLED','1')
    import mental_structured
    monkeypatch.setattr(mental_structured,'require_approved_library',lambda language:None)
    client=TestClient(main.app)
    for state in [{'language':'en','turn':41},{'language':'en','asked':['invented']},{'language':'en','speakerProfile':'different'}]:
        assert client.post('/api/mental/converse',json={'userMessage':'Hello','engine':'structured-v1','structuredState':state}).status_code==422
    assert client.post('/api/mental/converse',json={'userMessage':'Hello','engine':'structured-v1','structuredState':{'language':'en'}}).status_code==409


@pytest.mark.parametrize('text,action',[
 ('I want to end the conversation','finish'),('I would like to pause our conversation','pause'),
 ('Ich möchte eine Pause machen','pause'),('Ich möchte das Gespräch beenden','finish'),
 ('Görüşmeyi bitirmek istiyorum','finish'),('Biraz ara vermek istiyorum','pause')])
def test_explicit_natural_controls_use_existing_parser(text,action):
    from conversation_control import conversation_control
    result=conversation_control(text)
    assert result['sessionAction']==action
    assert conversation_control("I do not want to end the conversation") is None


def analysis_fixture():
    return dict(summaryText='You described work stress.',themes=['iş yaşamı'],moodTrend='STRESSED',professionalSupportSuggested=False,
                professionalSupportReason=None,recommendations=['Your chosen break.'],relatedSessionIds=['permitted','invented'],recurringThemes=['iş yaşamı'],spokenSummary='You described work stress and chose a break.')


def test_one_analysis_no_rewrite_and_uninvented_history(monkeypatch):
    calls=[]
    class Chat:
        def create(self,**kw):
            calls.append(kw);return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(analysis_fixture())))])
    import mental_provider
    monkeypatch.setattr(mental_provider,'get_openai_client',lambda *args:SimpleNamespace(chat=SimpleNamespace(completions=Chat())))
    analyzer=OpenAICompatibleSessionAnalyzer('mock');analyzer.structured=True
    analyzer.prior_sessions=[{'id':'permitted','summaryText':'Work pressure','themes':['iş yaşamı']}]
    result=analyzer.analyze_session([{'role':'user','content':'I feel stressed at work'}])
    assert len(calls)==1 and result['metrics']['analysisOpenAICalls']==1
    assert result['relatedSessionIds']==['permitted'] and result['recurringThemes']==['iş yaşamı']
    assert 'spokenSummary' in calls[0]['messages'][-1]['content']
    assert 'at most 12 words and 100 characters' in calls[0]['messages'][-1]['content']
    assert 'keep full detail in summaryText' in calls[0]['messages'][-1]['content']
    result=validate_analysis(analysis_fixture(),[],no_advice=True)
    assert not result['recommendations'] and not result['relatedSessionIds'] and not result['recurringThemes']
    with pytest.raises(ValueError):validate_analysis({**analysis_fixture(),'spokenSummary':''},[])


def test_history_consent_is_distinct_and_relevance_is_bounded(monkeypatch):
    client=TestClient(main.app)
    payload={'messages':[{'role':'user','content':'İş stresi yaşıyorum'}], 'priorSessions':[{'id':'p','summaryText':'old work stress','themes':['iş yaşamı']}], 'engine':'structured-v1'}
    for cloud,history in [(False,False),(True,False),(False,True)]:
        assert client.post('/api/mental/analyze-session',json={**payload,'cloudConsent':cloud,'historyConsent':history}).status_code==422
    records=[main.HistoricalMentalSummary(**r) for r in payload['priorSessions']]+[main.HistoricalMentalSummary(id='irrelevant',summaryText='Sleep',themes=['uyku düzeni'])]
    assert [r['id'] for r in relevant_history(payload['messages'],records)]==['p']


def test_offline_audio_plan_wave_metrics_and_recipe(tmp_path):
    spec=importlib.util.spec_from_file_location('mental_batch',ROOT/'scripts/mental_audio_batch.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    manifest=json.loads(module.MANIFEST.read_text())
    samples=module.sample_entries(manifest['entries']);assert len(samples)==9
    a,b=module.recipe(samples[0],{'revision':'fixed'},'speaker'),module.recipe(samples[0],{'revision':'fixed'},'speaker')
    assert a==b
    buf=io.BytesIO()
    with wave.open(buf,'wb') as wav:
        wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(24000);wav.writeframes(b'\x00\x00'*2400)
    metrics=module.inspect_pcm(buf.getvalue());assert metrics['durationMs']==100 and metrics['clippedSamples']==0
    bad=tmp_path/'bad.json';bad.write_text('{}')
    with pytest.raises((KeyError,ValueError)):module.produce(manifest,samples,str(bad),sys.executable)
    assert all(e['approvalStatus'] in ('pending-generation','synthesized-awaiting-listening-review') for e in samples)


def test_speaker_contract_blocks_missing_conditioning_before_generation(monkeypatch, tmp_path):
    import mental_neural_tts
    monkeypatch.setenv('ATTUNE_MENTAL_TTS_TOKEN','m'*32)
    monkeypatch.delenv('ATTUNE_MENTAL_TTS_CONFIG',raising=False)
    # Exercise the real async validation path; prohibit only worker creation.
    monkeypatch.setattr(mental_neural_tts.asyncio,'create_subprocess_exec',forbidden)
    monkeypatch.setitem(main.vehicle_state,'driverAuthenticated',True)
    monkeypatch.setitem(main.vehicle_state,'vehicleMoving',False)
    monkeypatch.setitem(main.vehicle_state,'vehicleParked',True)
    client=TestClient(main.app)
    payload={'text':'Your closing summary','language':'en','speechConsent':True,'speakerProfile':'official-default'}
    assert client.post('/api/mental/neural-speech?language=en',json=payload).status_code==401
    headers={'Authorization':'Bearer '+'m'*32}
    response=client.post('/api/mental/neural-speech?language=en',json=payload,headers=headers)
    assert response.status_code==503 and response.json()['detail']=='NEURAL_TTS_MODEL_BUNDLE_UNAVAILABLE'
    config=tmp_path/'missing-conditioning.json'
    config.write_text('{}',encoding='utf-8')
    monkeypatch.setenv('ATTUNE_MENTAL_TTS_CONFIG',str(config))
    response=client.post('/api/mental/neural-speech?language=en',json=payload,headers=headers)
    assert response.status_code==503 and response.json()['detail']=='STRUCTURED_SPEAKER_UNAVAILABLE'
    assert client.post('/api/mental/neural-speech?language=en',json={**payload,'speakerProfile':'other'},headers=headers).status_code==422


@pytest.mark.parametrize('script',['mental_structured_runtime.cjs','mental_prepared_audio_runtime.cjs','mental_prepared_gesture_runtime.cjs','mental_limits_runtime.cjs'])
def test_actual_frontend_closures(script):
    result=subprocess.run(['node','tests/unit/'+script],cwd=ROOT,text=True,capture_output=True,timeout=30)
    assert result.returncode==0,result.stdout+result.stderr
