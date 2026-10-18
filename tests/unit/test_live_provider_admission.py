"""No key/network: admission rejects before dispatch and never retains rejected input."""
import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('admission', Path(__file__).parents[1]/'e2e/live_provider_admission.py')
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)

def conversation(gate, text=None, history=None):
    return {'messages': [{'role': 'system', 'content': 'Sen Togg araç içi Ruhsal İyi Oluş Asistanısın.'}] + (gate.messages if history is None else history) + [{'role': 'user', 'content': text or module.TEXTS[gate.counts['conversation']]}]}

def test_unverified_source_never_dispatches():
    gate = module.LiveAdmission()
    with pytest.raises(module.AdmissionRejected): gate.admit('/v1/chat/completions', conversation(gate))
    assert gate.counts == {'conversation': 0, 'tts': 0, 'summary': 0}

@pytest.mark.parametrize('payload', ['wrong-user', 'wrong-history'])
def test_unexpected_input_or_history_blocks_all_following_requests(payload):
    gate = module.LiveAdmission(True)
    data = conversation(gate, text='REJECTED_TEST_TOKEN') if payload == 'wrong-user' else conversation(gate, history=[{'role':'user','content':'REJECTED_TEST_TOKEN'}])
    with pytest.raises(module.AdmissionRejected): gate.admit('/v1/chat/completions', data)
    with pytest.raises(module.AdmissionRejected): gate.admit('/v1/chat/completions', conversation(gate))
    assert sum(gate.counts.values()) == 0 and 'REJECTED_TEST_TOKEN' not in str(gate.proof())

def test_failed_request_consumes_budget_without_retry():
    gate = module.LiveAdmission(True)
    kind = gate.admit('/v1/chat/completions', conversation(gate))
    with pytest.raises(module.AdmissionRejected): gate.complete(kind, success=False)
    with pytest.raises(module.AdmissionRejected): gate.admit('/v1/chat/completions', conversation(gate))
    assert gate.counts['conversation'] == 1

def test_three_pairs_exact_tts_and_one_summary_then_closed():
    gate = module.LiveAdmission(True)
    for i in range(3):
        gate.complete(gate.admit('/v1/chat/completions', conversation(gate)), f'Sentetik yanıt {i}')
        gate.complete(gate.admit('/v1/audio/speech', {'input': f'Sentetik yanıt {i}', 'voice':'coral','response_format':'mp3'}))
    summary = {'response_format': {'type':'json_object'}, 'messages':[{'role':'user','content':'Aşağıdaki kullanıcı-asistan araç içi konuşmasını analiz et\nKonuşma Geçmişi:\n'+'\n'.join(f"{m['role']}: {m['content']}" for m in gate.messages)}]}
    gate.complete(gate.admit('/v1/chat/completions', summary))
    with pytest.raises(module.AdmissionRejected): gate.admit('/v1/chat/completions', summary)
    assert gate.counts == {'conversation':3,'tts':3,'summary':1}

def test_tts_cannot_send_unverified_content():
    gate = module.LiveAdmission(True)
    gate.complete(gate.admit('/v1/chat/completions', conversation(gate)), 'Sentetik yanıt')
    with pytest.raises(module.AdmissionRejected): gate.admit('/v1/audio/speech', {'input':'REJECTED_TEST_TOKEN','voice':'coral','response_format':'mp3'})
    assert gate.counts['tts'] == 0

@pytest.mark.parametrize('violation', ['stream', 'store', 'unknown-endpoint', 'concurrent'])
def test_other_egress_paths_fail_closed(violation):
    gate = module.LiveAdmission(True)
    data = conversation(gate)
    if violation in ['stream', 'store']: data[violation] = True
    if violation == 'concurrent': gate.admit('/v1/chat/completions', data)
    endpoint = '/v1/responses' if violation == 'unknown-endpoint' else '/v1/chat/completions'
    with pytest.raises(module.AdmissionRejected): gate.admit(endpoint, data)
    assert gate.failed and gate.counts['conversation'] == (1 if violation == 'concurrent' else 0)

def test_response_completes_before_browser_can_request_tts():
    gate = module.LiveAdmission(True)
    kind = gate.admit('/v1/chat/completions', conversation(gate))
    events = []
    class Response:
        ok = True
        def json(self): return {'providerType':'LIVE_OPENAI','reply':'Sentetik yanıt'}
    class Route:
        def fetch(self, **options):
            assert options['max_retries']==0
            return Response()
        def fulfill(self, **options):
            assert gate.pending is None and events==['recorded']
            gate.admit('/v1/audio/speech', {'input':'Sentetik yanıt','voice':'coral','response_format':'mp3'})
    assert module.forward_admitted_response(Route(),gate,kind,lambda *a:events.append('recorded'))
    assert gate.counts=={'conversation':1,'tts':1,'summary':0} and not gate.failed

def test_honest_fallback_delivered_but_no_following_request_admitted():
    gate = module.LiveAdmission(True)
    kind = gate.admit('/v1/chat/completions',conversation(gate));delivered=[]
    class Response:
        ok = True
        def json(self): return {'providerType':'LOCAL_DEMO_FALLBACK','reply':'Yerel demo'}
    class Route:
        def fetch(self, **options): return Response()
        def fulfill(self, **options): delivered.append(options['response'].json()['providerType'])
    assert not module.forward_admitted_response(Route(),gate,kind,lambda *a:None)
    assert delivered==['LOCAL_DEMO_FALLBACK'] and gate.failed
    with pytest.raises(module.AdmissionRejected):gate.admit('/v1/audio/speech',{'input':'Yerel demo','voice':'coral','response_format':'mp3'})


@pytest.mark.parametrize('run_id',['../previous','a/b','', 'UPPERCASE'])
def test_live_run_identity_cannot_escape_or_reuse_implicit_path(tmp_path,run_id):
    with pytest.raises(ValueError):module.live_run_output(tmp_path,run_id)

def test_distinct_authorization_preserves_previous_consumed_marker(tmp_path):
    old=module.live_run_output(tmp_path);module.claim_live_run(old);before=(old/'run-consumed.json').read_bytes()
    new=module.live_run_output(tmp_path,'20261003-approved-02');module.claim_live_run(new,'20261003-approved-02')
    with pytest.raises(FileExistsError):module.claim_live_run(new,'20261003-approved-02')
    assert (old/'run-consumed.json').read_bytes()==before
    assert new!=old and new.is_relative_to(tmp_path)


def transport_namespace(output, original_send):
    """Compile the exact checked-in wrapper without starting server or provider."""
    import ast,json,os,time
    from types import SimpleNamespace
    source=(Path(__file__).parents[1]/'e2e/live_provider_backend.py').read_text(encoding='utf-8')
    nodes=[n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name in ['save','send','checked_sdk_init']]
    ns={'json':json,'os':os,'time':time,'RUN_ID':'20261003-unit-run','OUT':output,'gate':module.LiveAdmission(True),'events':[],'original_send':original_send,'claim_live_run':module.claim_live_run,'original_send_calls':0,'admission_attempts':0,'sdk_retries':[],'openai':SimpleNamespace(__version__='unit-fixture'),'httpx':__import__('httpx'),'blocked_socket_connections':[],'fixture_calls':[],'args':SimpleNamespace(fixture=None),'CONSUMED':output/'run-consumed.json'}
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'exact-current-transport-wrapper','exec'),ns)
    return ns

def test_actual_transport_wrapper_claims_distinct_run_before_dispatch(tmp_path):
    import httpx,json
    calls=[]
    def original(self,request,*arguments,**options):
        assert (tmp_path/'run-consumed.json').exists()
        assert arguments==('sdk-positional-option',) and options=={'stream':False}
        calls.append(request)
        return httpx.Response(200,json={'choices':[{'message':{'content':'Sentetik kitap yanıtı'}}]},request=request)
    ns=transport_namespace(tmp_path,original)
    data=conversation(ns['gate']);data['model']='gpt-4o-mini';data['max_tokens']=250
    request=httpx.Request('POST','https://api.openai.com/v1/chat/completions',json=data)
    response=ns['send'](object(),request,'sdk-positional-option',stream=False)
    assert response.status_code==200 and len(calls)==1
    assert ns['gate'].counts=={'conversation':1,'tts':0,'summary':0} and ns['gate'].pending is None
    assert json.loads((tmp_path/'run-consumed.json').read_text())['runId']=='20261003-unit-run'

def test_transport_failure_keeps_consumed_marker_and_safe_category_without_retry(tmp_path):
    import httpx,json
    calls=[]
    def original(*args,**kwargs):
        calls.append(True);raise httpx.ConnectError('REJECTED_TEST_TOKEN')
    ns=transport_namespace(tmp_path,original);data=conversation(ns['gate']);data['model']='gpt-4o-mini';data['max_tokens']=250
    request=httpx.Request('POST','https://api.openai.com/v1/chat/completions',json=data)
    with pytest.raises(httpx.ConnectError):ns['send'](None,request)
    before=(tmp_path/'run-consumed.json').read_bytes()
    with pytest.raises(module.AdmissionRejected):ns['send'](None,request)
    assert len(calls)==1 and (tmp_path/'run-consumed.json').read_bytes()==before and ns['gate'].counts['conversation']==1
    proof=(tmp_path/'egress-proof.json').read_text();assert 'REJECTED_TEST_TOKEN' not in proof
    assert json.loads(proof)['events'][0]['failureCategory']=='ConnectError'
    assert json.loads(proof)['events'][0]['dispatchStarted'] is True


@pytest.mark.parametrize('command', [
    ['tests/e2e/live_provider_backend.py'],
    ['tests/e2e/live_provider_voice_followup.py'],
    ['scripts/run-followup-checks.py','--live','--provider-admission','--harness-fixture','success','--live-run-id','prep-forbidden','invalid.py'],
    ['scripts/run-followup-checks.py','--provider-admission','--harness-fixture','success','--live-run-id','live-forbidden','invalid.py'],
])
def test_checked_in_cli_rejects_missing_authorization_or_mixed_live_fixture(command):
    import os,subprocess,sys
    root=Path(__file__).resolve().parents[2]
    env={k:v for k,v in os.environ.items() if not k.startswith('OPENAI_')}
    env['ATTUNE_LOAD_LOCAL_ENV']='0'
    result=subprocess.run([sys.executable,*command],cwd=root,env=env,capture_output=True,timeout=10)
    assert result.returncode!=0

@pytest.mark.parametrize('violation',['automatic-retry','unknown-runtime-client'])
def test_sdk_configuration_error_closes_before_any_transport(tmp_path,violation):
    from types import SimpleNamespace
    sends=[];constructors=[]
    ns=transport_namespace(tmp_path,lambda *a,**k:sends.append(True))
    def initialize(client,*a,**k):
        constructors.append(True);client._client=SimpleNamespace(send=lambda:None)
    ns['original_sdk_init']=initialize
    with pytest.raises(module.AdmissionRejected):
        ns['checked_sdk_init'](SimpleNamespace(),max_retries=1 if violation=='automatic-retry' else 0)
    assert not sends and ns['gate'].failed and sum(ns['gate'].counts.values())==0
    with pytest.raises(module.AdmissionRejected):ns['gate'].admit('/v1/chat/completions',conversation(ns['gate']))
    assert len(constructors)==int(violation=='unknown-runtime-client')
