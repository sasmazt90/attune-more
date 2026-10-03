"""One content-free models GET using product's normal backend loader. Never emit credentials."""
import datetime, importlib, json, os, re, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];PRODUCT=ROOT.parent/'attune-live-test';OUT=ROOT/'research/preacceptance'
marker=OUT/'readonly-auth-consumed.json'
assert not marker.exists(),'This bounded authentication check was already consumed'
proof={'checkedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'sourceHead':'f8f08d98cf23eb23c5a171b5b50411364d79adf6','method':'GET','endpoint':'https://api.openai.com/v1/models','maxRequests':1,'maxRetries':0,'modelGenerationRequests':0,'ttsRequests':0,'summaryRequests':0,'keyValueRecorded':False}
for name in list(os.environ):
    if name.startswith('OPENAI_'):del os.environ[name]
os.environ.update(ATTUNE_LOAD_LOCAL_ENV='1',OPENAI_API_KEY='')
sys.path.insert(0,str(PRODUCT/'services/core-api'))
try:
    with tempfile.TemporaryDirectory(prefix='attune-readonly-config-') as data:
        os.environ['ATTUNE_DATA_DIR']=data
        main=importlib.import_module('main')
        provider=main.get_active_mental_provider()
        proof['configuration']={'keyPresent':bool(os.environ.get('OPENAI_API_KEY')),'file':str(PRODUCT/'.env.local'),'loader':str(PRODUCT/'services/core-api/main.py'),'inheritedOpenAIConfigurationCleared':True,'providerType':provider.get_provider_name(),'model':os.environ.get('OPENAI_MODEL','gpt-4o-mini'),'ttsModel':os.environ.get('OPENAI_TTS_MODEL','gpt-4o-mini-tts'),'baseUrlOverridePresent':bool(os.environ.get('OPENAI_BASE_URL')),'freshProviderUsesLoadedKey':getattr(provider,'api_key',None)==os.environ.get('OPENAI_API_KEY')}
        assert proof['configuration']['keyPresent'] and not proof['configuration']['baseUrlOverridePresent']
        client=main.get_openai_client(provider.api_key,provider.base_url)
        assert str(client.base_url)=='https://api.openai.com/v1/'
        marker.write_text(json.dumps({'startedAt':proof['checkedAt'],'maxRequests':1,'operation':'models.list','generationAllowed':False},indent=2),encoding='utf-8')
        raw=client.models.with_raw_response.list()
        models=raw.parse();ids={m.id for m in models.data}
        proof['httpStatus']=raw.status_code
        proof['authentication']='PASS' if raw.status_code==200 else 'UNVERIFIED'
        proof['configuredModelsListed']={m:m in ids for m in {proof['configuration']['model'],proof['configuration']['ttsModel']}}
        proof['headers']={}
        for name in ['x-request-id','openai-organization','openai-project']:
            value=raw.headers.get(name)
            if value and re.fullmatch(r'[A-Za-z0-9_.-]{1,200}',value):proof['headers'][name]=value
        proof['keyId']=None;proof['keyName']=None;proof['oldKeyDifference']='UNVERIFIED_NO_METADATA_LINK';proof['oldKeyRevocation']='USER_REPORTED_NOT_ADMIN_VERIFIED'
        main.close_openai_client()
except Exception as error:
    proof['authentication']='UNVERIFIED';proof['errorCategory']=type(error).__name__
    proof['httpStatus']=getattr(error,'status_code',None)
finally:
    (OUT/'openai-readonly-proof.json').write_text(json.dumps(proof,indent=2),encoding='utf-8')
print(json.dumps(proof))
