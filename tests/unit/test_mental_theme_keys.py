"""Stable wire/storage identities; explicit model fixtures, no paid requests."""
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'services/core-api'))
from localization import request_language,localize_payload
from mental_themes import stable_session_themes
import mental_provider
import main

@pytest.mark.parametrize('language',['tr','en','de'])
def test_actual_api_keeps_theme_values_raw(language):
    with TestClient(main.app) as client:
        response=client.post('/api/mental/analyze-session?language='+language,json={'messages':[{'role':'user','content':'uyku iş yorgun aile kaygı trafik'}],'cloudConsent':False})
    assert response.status_code==200
    assert response.json()['themes']==['uyku düzeni','iş yaşamı','sosyal ilişkiler','fiziksel yorgunluk','kaygı ve endişe','trafik gerilimi']
    token=request_language.set(language)
    try:
        payload={'themes':['iş yaşamı','PRIVATE Straße İı'],'detectedThemes':['uyku düzensizliği'],'recurringThemes':['fiziksel yorgunluk']}
        assert localize_payload(payload)==payload
    finally:request_language.reset(token)

@pytest.mark.parametrize('language,alias',[('en','working life'),('de','Arbeitsleben')])
def test_live_adapter_requests_stable_keys_and_normalizes_known_aliases(monkeypatch,language,alias):
    output={'summaryText':'Synthetic summary','themes':[alias,alias],'moodTrend':'NEUTRAL','professionalSupportSuggested':False,'professionalSupportReason':None}
    create=Mock(return_value=SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(output)))]))
    monkeypatch.setattr(mental_provider,'get_openai_client',lambda *a:SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))))
    token=request_language.set(language)
    try:
        result=mental_provider.OpenAICompatibleSessionAnalyzer('synthetic-key').analyze_session([{'role':'user','content':'Synthetic nonpersonal example'}])
        assert result['themes']==['iş yaşamı']
        prompt=create.call_args.kwargs['messages'][0]['content'];assert 'stable category keys' in prompt and 'never translated display labels' in prompt
        output['themes']=['unknown custom provider category']
        create.return_value.choices[0].message.content=json.dumps(output)
        with pytest.raises(HTTPException) as error:mental_provider.OpenAICompatibleSessionAnalyzer('synthetic-key').analyze_session([{'role':'user','content':'Synthetic'}])
        assert error.value.status_code==503
    finally:request_language.reset(token)

def test_mixed_legacy_storage_grouping_and_live_display_without_rewrites():
    result=subprocess.run(['node','tests/unit/mental_theme_runtime.cjs'],cwd=ROOT,text=True,capture_output=True,timeout=25)
    assert result.returncode==0,result.stdout+result.stderr
