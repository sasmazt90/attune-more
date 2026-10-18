"""Real FastAPI/OpenAI, with a test-only fail-closed HTTP transport gate."""
import argparse
import json
import os
from pathlib import Path
import sys
import time
parser = argparse.ArgumentParser()
parser.add_argument('--approved-additional-text-run', action='store_true')
parser.add_argument('--run-id')
parser.add_argument('--fixture', choices=['success','failure'])
args = parser.parse_args()
if not args.approved_additional_text_run:
    raise SystemExit('No authorization: no server or provider request')
if not args.fixture:raise SystemExit('Historical OpenAI TTS harness superseded by Edge-only product; zero dispatch')
# Reject unapproved execution before importing the SDK/runtime. This path
# neither loads local credentials nor waits for provider dependencies.
import uvicorn
from live_provider_admission import LiveAdmission,live_run_output,claim_live_run
from live_provider_transport import sdk_http_family
import openai
from openai import OpenAI, DefaultHttpxClient
httpx=sdk_http_family(DefaultHttpxClient)
RUN_ID = args.run_id
ROOT = Path(__file__).resolve().parents[2]
OUT = live_run_output(ROOT,args.run_id)
OUT.mkdir(parents=True, exist_ok=True)
CONSUMED = OUT/'run-consumed.json'
if CONSUMED.exists():
    raise SystemExit('The authorized bounded live run was already consumed; refusing another run')
gate = LiveAdmission(source_verified=True)  # Content itself is checked before every HTTP send.
events = []
original_send = httpx.Client.send
fixture_calls = []
blocked_socket_connections = []
if args.fixture:
    from live_provider_fixtures import NONSECRET, install_fixture, deny_nonloopback_connections
    assert os.getenv('ATTUNE_LOAD_LOCAL_ENV') == '0' and os.getenv('OPENAI_API_KEY') == NONSECRET
    assert RUN_ID and RUN_ID.startswith('prep-')
    blocked_socket_connections = deny_nonloopback_connections()
    fixture_calls = install_fixture(args.fixture, OUT, gate, httpx)
    print('KEYLESS FIXTURE PREPARATION; NOT LIVE PROVIDER EVIDENCE', flush=True)
original_send_calls = 0
admission_attempts = 0
sdk_retries = []
original_sdk_init = OpenAI.__init__
def checked_sdk_init(self, *values, **options):
    try:
        if options.get('max_retries') != 0:gate.reject('SDK_RETRY_CONFIGURATION_CHANGED')
        sdk_retries.append(options['max_retries'])
        result=original_sdk_init(self, *values, **options)
        if not isinstance(self._client,httpx.Client) or self._client.send.__func__ is not send:
            gate.reject('SDK_TRANSPORT_CHANGED')
        save()
        return result
    except Exception:
        gate.failed=True
        events.append({'kind':None,'failureCategory':'SDK_CONFIGURATION_FAILURE','dispatchStarted':False,'httpStatus':None})
        save()
        raise
OpenAI.__init__ = checked_sdk_init

def save():
    (OUT/'egress-proof.json').write_text(json.dumps({**gate.proof(), 'events': events, 'rawRejectedContentRetained': False, 'runId': RUN_ID or 'controlled-text', 'mode': 'KEYLESS_FIXTURE_PREPARATION' if args.fixture else 'LIVE_ATTEMPT', 'admissionAttempts':admission_attempts, 'originalSendCalls': original_send_calls, 'fixtureTransportCalls':len(fixture_calls), 'realHTTPDispatchCalls':0 if args.fixture else original_send_calls, 'httpResponses':sum(e.get('httpStatus') is not None for e in events), 'sdkMaxRetries':sdk_retries, 'billingVerified':False,'sdkVersion':openai.__version__,'transportFamily':httpx.__name__,'blockedSocketConnections':len(blocked_socket_connections)}, indent=2), encoding='utf-8')

def send(self, request, *send_args, **kwargs):
    global original_send_calls, admission_attempts
    kind = None
    dispatch_started = False
    try:
        if request.url.host != 'api.openai.com' or request.url.scheme != 'https' or request.method != 'POST':
            gate.reject('UNEXPECTED_PROVIDER_DESTINATION')
        data = json.loads(request.content)
        expected_model = os.getenv('OPENAI_TTS_MODEL', 'gpt-4o-mini-tts') if request.url.path.endswith('/speech') else os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
        if data.get('model') != expected_model:
            gate.reject('MODEL_CHANGED')
        if request.url.path == '/v1/chat/completions':
            limit = 400 if data.get('response_format') == {'type':'json_object'} else 250
            if not isinstance(data.get('max_tokens'), int) or not 1 <= data['max_tokens'] <= limit: gate.reject('OUTPUT_TOKEN_BUDGET')
            if len(json.dumps(data.get('messages', []), ensure_ascii=False)) > 14000: gate.reject('INPUT_CONTEXT_BUDGET')
        admission_attempts += 1
        kind = gate.admit(request.url.path, data)
        if sum(gate.counts.values()) == 1:
            claim_live_run(OUT,RUN_ID)
            if args.fixture:
                marker=json.loads(CONSUMED.read_text());marker['authorization']='keyless fixture preparation only; no live authorization consumed';CONSUMED.write_text(json.dumps(marker),encoding='utf-8')
        assert json.loads(CONSUMED.read_text())['runId'] == (RUN_ID or 'controlled-text')
        start = time.monotonic()
        dispatch_started = True
        original_send_calls += 1
        response = original_send(self, request, *send_args, **kwargs)  # Original SDK send; fixture transport is enabled only by explicit keyless preparation.
        headers_ready = time.monotonic()
        response.read()
        body_ready = time.monotonic()
        event = {'kind': kind, 'httpStatus': response.status_code, 'durationMs': round((body_ready-start)*1000, 1), 'headersMs': round((headers_ready-start)*1000, 1), 'bodyReadMs': round((body_ready-headers_ready)*1000, 1), 'streamedResponse': kwargs.get('stream') is True, 'requestId': response.headers.get('x-request-id'), 'markerBeforeDispatch': CONSUMED.exists(), 'admissionCompletedBeforeBackendReturn':False}
        events.append(event)
        if kind == 'conversation' and response.is_success:
            reply = response.json()['choices'][0]['message']['content']
        else:
            reply = None
        gate.complete(kind, reply, response.is_success)
        event['admissionCompletedBeforeBackendReturn'] = True
        if kind == 'tts' and response.is_success:
            (OUT/f"synthetic-reply-{gate.counts['tts']}.mp3").write_bytes(response.content)
        save()
        return response
    except Exception as error:
        events.append({'kind': kind, 'failureCategory': type(error).__name__, 'dispatchStarted': dispatch_started, 'httpStatus': None})
        gate.failed = True
        save()
        raise

httpx.Client.send = send
save()
sys.path.insert(0, str(ROOT/'services/core-api'))
import main
async def historical_fixture_speech(text,moving):
    assert args.fixture and os.getenv('ATTUNE_LOAD_LOCAL_ENV')=='0'
    from speech_stream import ProviderSpeechResponse,close_once
    try:
        context=main.get_openai_client(os.environ['OPENAI_API_KEY']).audio.speech.with_streaming_response.create(model=os.getenv('OPENAI_TTS_MODEL','gpt-4o-mini-tts'),voice='coral',input=text,response_format='mp3')
        speech=context.__enter__();close=close_once(context)
    except Exception as error:
        raise main.HTTPException(status_code=503,detail=main.provider_error_category(error)) from None
    def chunks():
        try:
            for part in speech.iter_bytes(chunk_size=None):
                if moving():return
                yield part
        finally:close()
    return ProviderSpeechResponse(chunks(),close,media_type='audio/mpeg')
main.edge_mental_speech=historical_fixture_speech
uvicorn.run(main.app, host='127.0.0.1', port=8000, access_log=True)
