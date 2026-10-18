"""Deterministic safety and theme-math regressions; no live-provider capability claims."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'services/core-api'))
import main
from fastapi.testclient import TestClient
from mental_provider import provider_error_category, LocalFallbackSessionAnalyzer


def test_cloud_consent_blocks_live_provider_and_summary(monkeypatch):
    def forbidden():
        raise AssertionError('Cloud invoked without consent')
    monkeypatch.setattr(main, 'get_active_mental_provider', forbidden)
    monkeypatch.setattr(main, 'get_active_session_analyzer', forbidden)
    client = TestClient(main.app)
    assert client.post('/api/mental/converse', json={'userMessage': 'Kitap okudum'}).json()['providerType'] == 'LOCAL_DEMO'
    assert client.post('/api/mental/analyze-session', json={'messages': [{'role': 'user', 'content': 'Kitap okudum'}]}).json()['analyzerType'] == 'LOCAL_FALLBACK'
    assert client.post('/api/mental/speech', json={'text': 'Merhaba'}).status_code == 403
    assert client.post('/api/mental/converse', json={'userMessage': 'Merhaba', 'cloudConsent': 'true'}).status_code == 422


def test_crisis_real_backend_bypasses_provider_even_with_consent(monkeypatch):
    def forbidden():
        raise AssertionError('Normal provider reached in crisis')
    monkeypatch.setattr(main, 'get_active_mental_provider', forbidden)
    response = TestClient(main.app).post('/api/mental/converse', json={'userMessage': 'ÖLMEK İSTİYORUM', 'cloudConsent': True}).json()
    assert response['isCrisis'] and response['providerType'] == 'CRISIS_SAFETY_GUARD'
    assert '112' in response['reply'] and '182' not in response['reply']


def test_empty_summary_is_rejected_and_moods_are_turkish():
    assert TestClient(main.app).post('/api/mental/analyze-session', json={'messages': []}).status_code == 422
    summary = LocalFallbackSessionAnalyzer().analyze_session([{'role': 'user', 'content': 'İş çok yoğun ve stresliyim'}])
    assert summary['moodTrend'] == 'STRESSED'
    assert 'STRESSED' not in summary['summaryText'] and 'gergin' in summary['summaryText']


def test_provider_error_categories_never_echo_secrets():
    for name, expected in [('AuthenticationError', 'PROVIDER_AUTH'), ('RateLimitError', 'PROVIDER_LIMIT'), ('APITimeoutError', 'PROVIDER_TIMEOUT'), ('APIConnectionError', 'PROVIDER_CONNECTION'), ('ValueError', 'PROVIDER_UNAVAILABLE')]:
        error = type(name, (Exception,), {})('private token and internal exception body')
        assert provider_error_category(error) == expected


def test_tts_driving_and_no_configuration(monkeypatch):
    import vision_speech,time
    monkeypatch.setattr(vision_speech,'_catalogue',(time.monotonic(),frozenset(['unrelated-voice'])))
    client = TestClient(main.app)
    monkeypatch.setitem(main.vehicle_state, 'vehicleMoving', True)
    assert client.post('/api/mental/speech', json={'text': 'Merhaba', 'cloudConsent': True}).status_code == 409
    monkeypatch.setitem(main.vehicle_state, 'vehicleMoving', False)
    monkeypatch.setenv('OPENAI_API_KEY', '')
    assert client.post('/api/mental/speech', json={'text': 'Merhaba', 'cloudConsent': True}).json()['detail'] == 'EXACT_MICROSOFT_VOICE_UNAVAILABLE:tr-TR-EmelNeural'


def test_production_theme_math_and_versioned_multiview_rules(tmp_path):
    script = r"""
const fs=require('fs'),ts=require('typescript'),assert=require('assert');
const dir=JSON.parse(fs.readFileSync(0,'utf8')).dir;
const Module=require('module'),original=Module._resolveFilename;
Module._resolveFilename=function(request,parent,...rest){if(request==='@mediapipe/tasks-vision')return original.call(this,request,{paths:module.paths},...rest);return original.call(this,request,parent,...rest);};
function load(name){const file=dir+'/'+name+'.js';fs.writeFileSync(file,ts.transpileModule(fs.readFileSync('apps/vehicle-app/src/utils/'+name+'.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText);return require(file);}
load('attuneMode');load('healthRecords');const H=load('mentalHistory');
const item=(id,themes,extra={})=>({id,date:'2026-10-03T10:00:00Z',summaryText:'Gerçek tamamlanmış paylaşım',themes,schemaVersion:2,completed:true,consented:true,...extra});
assert.deepEqual(H.mentalThemeStats([]),{sessions:0,mentions:0,rows:[]});
const stats=H.mentalThemeStats([item('1',['a','a','b']),item('2',['c']),item('old',['x'],{schemaVersion:undefined}),item('cancelled',['x'],{completed:false}),item('no-consent',['x'],{consented:false})]);
assert.equal(stats.sessions,2);assert.equal(stats.mentions,3);assert.equal(stats.rows.reduce((s,r)=>s+r.percent,0),100);assert.deepEqual(stats.rows.map(r=>r.count),[1,1,1]);assert.deepEqual(stats.rows.map(r=>r.percent).sort(),[33,33,34]);
assert.equal(H.translateMood('STRESSED TIRED RELAXED NEUTRAL'),'Gergin Yorgun Rahat Nötr');
load('skinAnalyzer');const M=load('skinMultiAngle');
const pose={faceDetected:true,isMediaPipeActive:true,yaw:0,pitch:0,roll:0,scaleRatio:.5};
assert(M.matchesSkinAngle(pose,'FRONT'));assert(!M.matchesSkinAngle(pose,'LEFT'));assert(!M.matchesSkinAngle(pose,'RIGHT'));
assert(M.matchesSkinAngle({...pose,yaw:-.4},'RIGHT'));assert(M.matchesSkinAngle({...pose,yaw:.4},'LEFT'));
for(const bad of [{yaw:NaN},{pitch:.23},{roll:.16},{scaleRatio:.27},{isMediaPipeActive:false}])assert(!M.matchesSkinAngle({...pose,...bad},'FRONT'));
const quality={isValid:true,avgLuminance:120,blurScore:8,status:'OPTIMAL'};
const region=id=>({id,nameTr:id,rednessScore:20,luminanceScore:50,textureVariance:30});
const capturePose={yaw:0,pitch:0,roll:0,scaleRatio:.5};
const captures={FRONT:{angle:'FRONT',pose:capturePose,quality:{...quality},regions:Object.fromEntries(['forehead','nose','chin','periorbital','rightCheek','leftCheek'].map(id=>[id,region(id)]))},RIGHT:{angle:'RIGHT',pose:{...capturePose,yaw:-.4},quality:{...quality},regions:{leftCheek:region('leftCheek')}},LEFT:{angle:'LEFT',pose:{...capturePose,yaw:.4},quality:{...quality},regions:{rightCheek:region('rightCheek')}}};
const reference={schemaVersion:2,scope:'three-angle-v2',id:'v2',timestamp:'2026-10-03',captures};
assert.equal(Object.keys(M.compareMultiAngle(reference,null).regions).length,6);
assert.deepEqual(M.compareMultiAngle(reference,reference).unavailable,[]);
const changed=structuredClone(reference);changed.captures.LEFT.quality.avgLuminance=140;
const result=M.compareMultiAngle(changed,reference);assert.deepEqual(result.unavailable,['LEFT']);assert.equal(result.regions.rightCheek.changeFromBaselinePct,undefined);assert.equal(result.regions.leftCheek.changeFromBaselinePct,0);
assert.throws(()=>M.compareMultiAngle(reference,{...reference,schemaVersion:1}),/INVALID_REFERENCE/);
"""
    subprocess.run(['node', '-e',"require('./tests/unit/ts_loader.js');\n"+script], cwd=ROOT, check=True, input=json.dumps({'dir': str(tmp_path).replace('\\', '/')}), text=True, encoding='utf-8')
