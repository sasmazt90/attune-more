"""Presentation localization and safety regression; no paid speech/model requests."""
import asyncio
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import pytest
from fastapi.testclient import TestClient
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'services/core-api'))
from main import app
from localization import request_language, translate, localize_payload
from mental_provider import LocalFallbackSessionAnalyzer
from conversation_control import conversation_control

@pytest.mark.parametrize('language',['tr','en','de'])
def test_request_locale_and_private_data(language):
    token=request_language.set(language)
    try:
        private='Öztürk Straße ÄÖÜäöüß ÇĞİÖŞÜçğıöşü'
        payload={'userMessage':private,'content':private,'driverName':private,'id':'skin','value':12.345,'unit':'dB SNR','summaryText':'Ölçüm tamamlandı.'}
        result=localize_payload(payload)
        assert all(result[k]==payload[k] for k in ('userMessage','content','driverName','id','value','unit'))
        expected=translate('Ölçüm tamamlandı.')
        assert result['summaryText']==expected
        assert request_language.get()==language
    finally:request_language.reset(token)

@pytest.mark.parametrize('language,text',[('en','I feel stress at work and tired'),('de','Ich bin müde und habe Stress bei der Arbeit')])
def test_local_summary_and_controls(language,text):
    token=request_language.set(language)
    try:
        summary=LocalFallbackSessionAnalyzer().analyze_session([{'role':'user','content':text}])
        assert summary['moodTrend']=='STRESSED'
        assert 'Kullanıcı' not in summary['summaryText'] and 'duygu' not in summary['summaryText']
        assert 'work' in summary['summaryText'].lower() if language=='en' else 'arbeit' in summary['summaryText'].lower()
        reply=localize_payload(conversation_control('pause' if language=='en' else 'pausieren'))
        assert reply['sessionAction']=='pause' and 'Görüşmeyi' not in reply['reply']
    finally:request_language.reset(token)

@pytest.mark.parametrize('language,text',[('en','I want to kill myself'),('de','Ich will sterben'),('tr','ÖLMEK İSTİYORUM')])
def test_crisis_and_explicit_api_locale(language,text):
    with TestClient(app) as client:
        response=client.post('/api/mental/converse?language='+language,json={'userMessage':text})
        assert response.status_code==200
        data=response.json()
        assert data['isCrisis'] is True and '112' in data['reply'] and '182' not in data['reply']
        assert response.headers['content-language']=={'tr':'tr-TR','en':'en-US','de':'de-DE'}[language]
        if language!='tr':assert 'Acil Çağrı' not in data['reply']
        if language!='tr':
            assert 'klinik olarak' not in data.get('clinicalDisclaimer','')
            assert 'Çağrı' not in data.get('emergencyContact','')
        invalid=client.post('/api/mental/converse?language='+language,json={'userMessage':{'private':text}})
        assert invalid.status_code==422 and text not in invalid.text
        if language!='tr':assert invalid.json()['displayMessage']
        assert client.get('/?language=fr').status_code==422
        assert client.get('/').headers['content-language']=='tr-TR'

def test_catalog_and_actual_frontend_behavior():
    for script in [['node','scripts/localization/check.cjs'],['node','tests/unit/localization_runtime.cjs'],['node','tests/unit/system_speech_runtime.cjs']]:
        result=subprocess.run(script,cwd=ROOT,text=True,capture_output=True,timeout=60)
        assert result.returncode==0,result.stdout+result.stderr

def test_preserved_and_localized_audio_integrity():
    for row in json.loads((ROOT/'shared/localization/preserved-audio.json').read_text()):
        data=(ROOT/row['path']).read_bytes()
        assert len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256']
    manifest=json.loads((ROOT/'apps/vehicle-app/public/audio/localized/manifest.json').read_text())
    def verify(clip):
        data=(ROOT/'apps/vehicle-app/public'/clip['url'].lstrip('/')).read_bytes()
        assert len(data)==clip['bytes'] and hashlib.sha256(data).hexdigest()==clip['sha256']
    for language in ('en','de'):
        for gender in ('male','female'):
            profile=manifest['voices'][language][gender]
            assert profile['gender']==gender and profile['locale']=={'en':'en-US','de':'de-DE'}[language]
            for kind in ('guidance','vision'):
                for clip in profile[kind].values():verify(clip)
        bank=manifest['hearing'][language];verify(bank)
        for clip in json.loads((ROOT/'apps/vehicle-app/public'/bank['url'].lstrip('/')).read_text())['digits']:
            data=(ROOT/'apps/vehicle-app/public'/clip['url'].lstrip('/')).read_bytes()
            assert hashlib.sha256(data).hexdigest()==clip['sha256']
