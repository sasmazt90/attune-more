"""
Attune.more - Core API (FastAPI)
Yerel önleyici sağlık ve araç bağlamı orkestrasyon servisi.
Lisans: UNLICENSED
"""

from fastapi import FastAPI, HTTPException, Request
from localization import LocalizedJSONResponse, LANGUAGES, request_language, current_language, translate
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException
from speech_stream import ProviderSpeechResponse, close_once
from pydantic import BaseModel, Field, StrictBool, field_validator
from typing import List, Optional, Dict, Any
from datetime import datetime
from contextlib import asynccontextmanager
import os
from time import perf_counter
from openai_client import get_openai_client, close_openai_client
from pathlib import Path
from qa_vehicle_read import QAVehicleReadPolicy, QA_VEHICLE_ORIGIN
from hosted_skin_credentials import load_existing_backend_key
load_existing_backend_key()

# Backend-only local configuration. CI has no local file and remains keyless.
_local_env = Path(__file__).resolve().parents[2] / '.env.local'
if os.getenv('ATTUNE_LOAD_LOCAL_ENV') == '1' and _local_env.is_file():
    for _line in _local_env.read_text(encoding='utf-8').splitlines():
        _name, _separator, _value = _line.partition('=')
        if _separator and _name.strip() in ('OPENAI_API_KEY', 'OPENAI_MODEL', 'OPENAI_TTS_MODEL'):
            os.environ[_name.strip()] = _value.strip().strip('\"').strip("'")

from mental_provider import (get_active_mental_provider, check_mental_crisis, get_active_session_analyzer,
                             LocalFallbackMentalProvider, LocalFallbackSessionAnalyzer, provider_error_category)
from session_memory import SessionMemoryManager
from care_provider import BrowserCareSearchProvider, DemoCareSearchProvider, CalendarProvider, TravelTimeProvider

@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        yield
    finally:
        close_openai_client()

app = FastAPI(
    default_response_class=LocalizedJSONResponse,
    title="Attune.more Core API",
    description="Attune.more sağlık ve iyi oluş ön değerlendirmesi, sesli asistan ve randevu orkestrasyonu.",
    version="1.0.0",
    lifespan=lifespan
)

@app.middleware('http')
async def selected_language(request: Request, call_next):
    language = request.query_params.get('language','tr')
    if language not in LANGUAGES:
        return JSONResponse(status_code=422,content={'detail':'UNSUPPORTED_LANGUAGE'})
    token = request_language.set(language)
    try:
        result = await call_next(request)
        result.headers['Content-Language'] = LANGUAGES[language]
        return result
    finally:
        request_language.reset(token)


@app.exception_handler(RequestValidationError)
async def request_validation_error(_request, error: RequestValidationError):
    # Do not echo private request values. Non-finite input also cannot be JSON-serialized.
    content = {"detail": [
        {key: item[key] for key in ("loc", "type", "msg")} for item in error.errors()
    ]}
    if current_language() != 'tr':
        content['displayMessage'] = translate('Girilen bilgiler doğrulanamadı. Lütfen alanları kontrol edin.')
    return JSONResponse(status_code=422, content=content)


@app.exception_handler(StarletteHTTPException)
async def localized_http_error(_request, error):
    # Keep machine diagnostics intact; expose a separate localized presentation.
    content = {'detail': error.detail}
    if current_language() != 'tr':
        source = error.detail if isinstance(error.detail,str) else ''
        translated = translate(source)
        content['displayMessage'] = translated if translated != source else translate('İşlem tamamlanamadı. Lütfen izinleri ve bağlantıyı kontrol edin.')
    return JSONResponse(status_code=error.status_code,content=content,headers=error.headers)

trusted_origins = [origin.strip() for origin in os.getenv(
    "ATTUNE_TRUSTED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
).split(",") if origin.strip()]
if not trusted_origins or "*" in trusted_origins:
    raise ValueError("ATTUNE_TRUSTED_ORIGINS must list explicit trusted origins")

# Startup-only opt-in. This never adds the QA origin to the general CORS list.
qa_vehicle_read_policy = QAVehicleReadPolicy.from_environment(os.environ)

app.add_middleware(
    CORSMiddleware,
    allow_origins=trusted_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
    expose_headers=["Server-Timing"],
)


@app.middleware("http")
async def enforce_browser_origin(request: Request, call_next):
    origin = request.headers.get("origin")
    qa_read = False
    if origin == QA_VEHICLE_ORIGIN:
        qa_read = await qa_vehicle_read_policy.authorizes(request)
        if not qa_read:
            return JSONResponse(status_code=403, content={"detail": "Untrusted browser origin"})
    # CORS handles preflight. Reject actual untrusted browser requests before
    # they can mutate local health data, including simple POSTs without preflight.
    if (not qa_read and request.method != "OPTIONS"
            and origin is not None and origin not in trusted_origins):
        return JSONResponse(status_code=403, content={"detail": "Untrusted browser origin"})
    started = perf_counter()
    response = await call_next(request)
    if qa_read:
        # Expiry during a handler must not grant a late cross-origin response.
        if not qa_vehicle_read_policy.active():
            return JSONResponse(status_code=403, content={"detail": "Untrusted browser origin"})
        response.headers["Access-Control-Allow-Origin"] = QA_VEHICLE_ORIGIN
        if "origin" not in {v.strip().lower() for v in response.headers.get("Vary", "").split(",")}:
            response.headers.add_vary_header("Origin")
        response.headers["Cache-Control"] = "no-store"
    if request.url.path.startswith("/api/mental/"):
        existing = response.headers.get("Server-Timing")
        timing = f"app;dur={(perf_counter() - started) * 1000:.1f}"
        response.headers["Server-Timing"] = f"{existing}, {timing}" if existing else timing
    return response


# ---------------------------------------------------------------------------
# In-Memory State & Mock Data (Local-First)
# ---------------------------------------------------------------------------

vehicle_state = {
    "state": "PARKED",
    "vehicleMoving": False,
    "vehicleParked": True,
    "currentSpeed": 0,
    "gear": "P",
    "currentLocation": {"latitude": 40.9912, "longitude": 29.0234, "label": "Kadıköy, İstanbul"},
    "destination": {"latitude": 41.0082, "longitude": 28.9784, "label": "Levent, İstanbul"},
    "estimatedTravelTimeToDestMin": 22,
    "driverAuthenticated": True,
    "driverId": "demo-driver-001",
    "driverName": "Ahmet Yılmaz",
    "driverFatigueSignal": "LOW",
    "cabinCameraAvailable": True,
    "microphoneAvailable": True,
    "batteryLevelPct": 78,
    "lastUpdated": datetime.utcnow().isoformat()
}

profile_state = {
    "user": {
        "id": "user-togg-001",
        "displayName": "Ahmet Yılmaz",
        "truId": "TRU-8924-IST",
        "ageRange": "36-50",
        "preferredCity": "İstanbul",
        "preferredConsultationType": "ALL"
    },
    "visionSummary": {
        "lastTestDate": "2026-09-18T09:15:00Z",
        "acuityRightSnellen": "20/30",
        "acuityLeftSnellen": "20/24",
        "contrastSensitivityLogCS": 1.55,
        "baselineDiffNote": "Önceki ölçümünüze göre sağ göz kontrast hassasiyetinizde değişim gözlendi.",
        "referralSuggested": True
    },
    "skinSummary": {
        "lastScanDate": "2026-09-17T18:40:00Z",
        "highestChangeRegion": "Sağ Yanak",
        "changePct": 24,
        "baselineDiffNote": "Önceki ölçümünüze göre sağ yanak bölgesinde belirgin bir görsel değişim gözlendi. Bir dermatologla görüşmek faydalı olabilir.",
        "referralSuggested": True
    },
    "mentalSummary": {
        "lastSessionDate": "2026-09-19T19:10:00Z",
        "recurringThemes": ["uyku düzensizliği", "fiziksel yorgunluk"],
        "summaryText": "Son görüşmelerinizde uyku ve yorgunluk temalarının tekrar ettiği gözlemlendi.",
        "referralSuggested": True
    }
}

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class SpeedUpdatePayload(BaseModel):
    speedKmH: float = Field(ge=0, allow_inf_nan=False)

from mental_context import validate_memory,compact_context

class MemoryPayload(BaseModel):
    memory: List[str] = Field(default_factory=list,max_length=32)
    @field_validator('memory')
    @classmethod
    def memory_bounds(cls,value):return validate_memory(value)

class ConversePayload(MemoryPayload):
    userMessage: str = Field(min_length=1, max_length=6000)
    sessionId: Optional[str] = Field(default=None,min_length=1,max_length=128)
    history: Optional[List[Dict[str, str]]] = Field(default=None,max_length=40)
    cloudConsent: StrictBool = False

    @field_validator('userMessage')
    @classmethod
    def nonempty_message(cls,value):
        if not value.strip():raise ValueError('EMPTY_MESSAGE')
        return value

    @field_validator('history')
    @classmethod
    def completed_context(cls,value):
        if value is None:return value
        validate_mental_messages(value)
        if len(value)%2 or any(m['role']!=('user' if i%2==0 else 'assistant') for i,m in enumerate(value)):
            raise ValueError('COMPLETED_TURN_PAIRS_REQUIRED')
        return value

def validate_mental_messages(messages):
    if any(set(m)!= {'role','content'} or m['role'] not in ('user','assistant') or not m['content'].strip() or len(m['content'])>6000 for m in messages):
        raise ValueError('INVALID_CONVERSATION_MESSAGE')
    if sum(len(m['content']) for m in messages)>120000:raise ValueError('SESSION_CONTENT_LIMIT')
    return messages

class AnalyzeSessionPayload(MemoryPayload):
    messages: List[Dict[str, str]] = Field(max_length=200)
    cloudConsent: StrictBool = False

    @field_validator('messages')
    @classmethod
    def bounded_messages(cls,value):return validate_mental_messages(value)

class SpeechPayload(BaseModel):
    text: str = Field(min_length=1, max_length=4096)
    cloudConsent: StrictBool = False
    voiceId: Optional[str] = Field(default=None,max_length=160)

class NeuralSpeechPayload(BaseModel):
    text: str = Field(min_length=1, max_length=4096)
    language: str
    speechConsent: StrictBool = False

    @field_validator('text')
    @classmethod
    def nonempty_speech(cls, value):
        if not value.strip():
            raise ValueError('NONEMPTY_SPEECH_REQUIRED')
        return value

class CreateSessionPayload(BaseModel):
    summaryText: str
    recurringThemes: List[str]
    durationSeconds: Optional[int] = None
    moodBefore: Optional[str] = None
    moodAfter: Optional[str] = None
    escalationSuggested: Optional[bool] = False
    suggestedAction: Optional[str] = None
    saveMentalSummaries: StrictBool = False

class AppointmentMatchPayload(BaseModel):
    specialty: str = Field(min_length=1,max_length=120)
    preferredCity: Optional[str] = Field(default="İstanbul",max_length=120)
    maxTravelTimeMin: Optional[int] = 30
    useBrowserAgent: Optional[bool] = True
    availableWindows: List[dict] = Field(default_factory=list,max_length=30)
    timeZone: str = "Europe/Istanbul"
    durationMin: int = 45

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/")
def read_root():
    return {
        "service": "Attune.more Core API",
        "status": "OPERATIONAL",
        "language": LANGUAGES[current_language()],
        "clinicalSafety": "Non-diagnostic trend monitoring",
        "version": "0.3.0-faz3"
    }

@app.get("/api/health")
def health_check():
    import fastapi, starlette, aiohttp, PIL
    modules = (fastapi, starlette, aiohttp, PIL)
    isolated = Path(__file__).resolve().parents[2] / '.runtime/security-20261008'
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat(),
            "runtimeVersions": {module.__name__: module.__version__ for module in modules},
            "runtimeIsolated": all(Path(module.__file__).resolve().is_relative_to(isolated) for module in modules)}

# ---------------------------------------------------------------------------
# Vehicle State
# ---------------------------------------------------------------------------

@app.get("/api/vehicle/state")
def get_vehicle_state():
    return vehicle_state

@app.post("/api/vehicle/toggle")
def toggle_driving_mode():
    if vehicle_state["vehicleMoving"]:
        vehicle_state["vehicleMoving"] = False
        vehicle_state["vehicleParked"] = True
        vehicle_state["currentSpeed"] = 0
        vehicle_state["gear"] = "P"
        vehicle_state["state"] = "PARKED"
    else:
        vehicle_state["vehicleMoving"] = True
        vehicle_state["vehicleParked"] = False
        vehicle_state["currentSpeed"] = 50
        vehicle_state["gear"] = "D"
        vehicle_state["state"] = "DRIVING"
    vehicle_state["lastUpdated"] = datetime.utcnow().isoformat()
    return vehicle_state

@app.post("/api/vehicle/speed")
def update_vehicle_speed(payload: SpeedUpdatePayload):
    speed = payload.speedKmH
    vehicle_state["currentSpeed"] = speed
    if speed > 0:
        vehicle_state["vehicleMoving"] = True
        vehicle_state["vehicleParked"] = False
        vehicle_state["gear"] = "D"
        vehicle_state["state"] = "DRIVING"
    else:
        vehicle_state["vehicleMoving"] = False
        vehicle_state["vehicleParked"] = True
        vehicle_state["gear"] = "P"
        vehicle_state["state"] = "PARKED"
    vehicle_state["lastUpdated"] = datetime.utcnow().isoformat()
    return vehicle_state

# ---------------------------------------------------------------------------
# Health Profile Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/profile")
def get_user_profile():
    return profile_state

# ---------------------------------------------------------------------------
# Mental Wellbeing Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/mental/provider-status")
def get_mental_provider_status():
    provider = get_active_mental_provider()
    return {
        "providerName": provider.get_provider_name(),
        "isLiveLLM": provider.is_live_llm(),
        "apiKeyConfigured": bool(os.getenv("OPENAI_API_KEY"))
    }

@app.post("/api/mental/converse")
def converse_mental_assistant(payload: ConversePayload):
    is_driving = vehicle_state["vehicleMoving"]
    user_msg = payload.userMessage.strip()

    # 1. Kriz Güvenlik Filtresi (İki katmanlı: Deterministik + Sürüş duyarlı)
    crisis_check = check_mental_crisis(user_msg, is_driving)
    if crisis_check.get("isCrisis"):
        return {
            "reply": crisis_check["reply"],
            "isCrisis": True,
            "riskLevel": crisis_check.get("riskLevel", "IMMINENT"),
            "emergencyContact": crisis_check.get("emergencyContact", "112 Acil Çağrı Merkezi"),
            "drivingModeResponse": is_driving,
            "providerType": "CRISIS_SAFETY_GUARD",
            "clinicalDisclaimer": crisis_check.get("clinicalDisclaimer")
        }

    from conversation_control import conversation_control
    control = conversation_control(user_msg) if not is_driving else None
    if control:
        return control

    # 2. Mental Conversation Provider (OpenAI veya LocalFallback)
    if payload.cloudConsent and not os.getenv('OPENAI_API_KEY', '').strip():
        raise HTTPException(status_code=503, detail='PROVIDER_NOT_CONFIGURED')
    provider = get_active_mental_provider() if payload.cloudConsent else LocalFallbackMentalProvider()
    history = payload.history or []
    driver_name = vehicle_state.get("driverName", "Ahmet Bey")

    if payload.memory:
        provider.session_memory = payload.memory
    result = provider.generate_reply(
        user_message=user_msg,
        is_driving=is_driving,
        history=history,
        driver_name=driver_name
    )

    return result

@app.post("/api/mental/analyze-session")
def analyze_mental_session(payload: AnalyzeSessionPayload):
    if not any(m.get('role') == 'user' and m.get('content', '').strip() for m in payload.messages):
        raise HTTPException(status_code=422, detail='EMPTY_SESSION')
    if payload.cloudConsent and not os.getenv('OPENAI_API_KEY', '').strip():
        raise HTTPException(status_code=503, detail='PROVIDER_NOT_CONFIGURED')
    analyzer = get_active_session_analyzer() if payload.cloudConsent else LocalFallbackSessionAnalyzer()
    if payload.memory:
        analyzer.session_memory = payload.memory
    return analyzer.analyze_session(payload.messages)

class CompactContextPayload(AnalyzeSessionPayload):
    pass

@app.post('/api/mental/compact-context')
def compact_mental_context(payload: CompactContextPayload):
    if not payload.cloudConsent:raise HTTPException(403,'CLOUD_CONSENT_REQUIRED')
    if vehicle_state['vehicleMoving']:raise HTTPException(409,'PARK_REQUIRED')
    return compact_context(payload.memory,payload.messages)

from vision_speech import response as fixed_vision_speech
from vision_speech import mental_response as edge_mental_speech
from vision_speech import available_voices, localized_profile, speech_response
from local_speech import available_local_voices, response as local_speech_response

@app.get('/api/speech/local-voices')
async def local_voices():
    if vehicle_state['vehicleMoving']:raise HTTPException(409,'PARK_REQUIRED')
    return {'locale':LANGUAGES[current_language()],'voices':await available_local_voices()}

@app.get('/api/speech/voices')
async def speech_voices():
    if vehicle_state['vehicleMoving']:
        raise HTTPException(status_code=409,detail='PARK_REQUIRED')
    voices=await available_voices()
    return {'locale':LANGUAGES[current_language()],'voices':[
        {'id':v['ShortName'],'name':v.get('FriendlyName') or v['ShortName'],
         'locale':v['Locale'],'gender':v.get('Gender','unknown').lower() if v.get('Gender','unknown').lower() in ('male','female') else 'unknown',
         'provider':'edge','local':False} for v in voices]}

@app.post('/api/guidance/speech')
async def guidance_speech(payload: SpeechPayload):
    if not payload.cloudConsent:raise HTTPException(status_code=403,detail='CLOUD_CONSENT_REQUIRED')
    if vehicle_state['vehicleMoving']:raise HTTPException(status_code=409,detail='PARK_REQUIRED')
    import json
    from tts_profiles import VISION_TTS_PROFILE
    bank=Path(__file__).resolve().parents[2]/'apps/vehicle-app/public/audio/guidance/manifest.json'
    entries=json.loads(bank.read_text('utf8'))['entries']
    if payload.text not in entries:raise HTTPException(status_code=422,detail='FIXED_INSTRUCTION_REQUIRED')
    profile=await localized_profile(VISION_TTS_PROFILE,payload.voiceId)
    return await speech_response(translate(entries[payload.text]['text']),profile,lambda:vehicle_state['vehicleMoving'])

@app.post('/api/mental/speech')
async def mental_speech(payload: SpeechPayload):
    if not payload.cloudConsent:
        raise HTTPException(status_code=403, detail='CLOUD_CONSENT_REQUIRED')
    if vehicle_state['vehicleMoving']:
        raise HTTPException(status_code=409, detail='PARK_REQUIRED')
    if payload.voiceId:return await edge_mental_speech(payload.text, lambda: vehicle_state['vehicleMoving'],payload.voiceId)
    return await edge_mental_speech(payload.text, lambda: vehicle_state['vehicleMoving'])

@app.post('/api/mental/neural-speech')
async def mental_neural_speech(payload: NeuralSpeechPayload, request: Request):
    from mental_neural_tts import authorize, generate_for_request
    authorize(request.headers.get('authorization'))
    if not payload.speechConsent:
        raise HTTPException(403, 'SPEECH_CONSENT_REQUIRED')
    if payload.language != current_language():
        raise HTTPException(422, 'TTS_LANGUAGE_MISMATCH')
    def permitted():
        return (vehicle_state.get('driverAuthenticated') is True
                and vehicle_state.get('vehicleMoving') is False
                and vehicle_state.get('vehicleParked') is True)
    raw = await generate_for_request(payload.text, payload.language, permitted, request)
    return Response(raw, media_type='audio/wav', headers={
        'Cache-Control':'no-store', 'X-Content-Type-Options':'nosniff',
        'X-TTS-Source':'chatterbox-multilingual-v3', 'X-TTS-Locale':LANGUAGES[payload.language]})

@app.post('/api/vision/speech')
async def vision_speech(payload: SpeechPayload):
    if not payload.cloudConsent:
        raise HTTPException(status_code=403, detail='CLOUD_CONSENT_REQUIRED')
    if vehicle_state['vehicleMoving']:
        raise HTTPException(status_code=409, detail='PARK_REQUIRED')
    if payload.voiceId:return await fixed_vision_speech(payload.text, lambda: vehicle_state['vehicleMoving'],payload.voiceId)
    return await fixed_vision_speech(payload.text, lambda: vehicle_state['vehicleMoving'])

@app.get("/api/mental/sessions")
def get_mental_sessions():
    return SessionMemoryManager.get_all_sessions()

class DeleteSessionPayload(BaseModel):
    deletionToken: str = Field(min_length=64, max_length=64)

@app.delete('/api/mental/sessions/{session_id}')
def delete_mental_session(session_id: str, payload: DeleteSessionPayload):
    if vehicle_state['vehicleMoving']:
        raise HTTPException(status_code=409, detail='PARK_REQUIRED')
    try:
        deleted = SessionMemoryManager.delete_session(session_id, payload.deletionToken)
    except (OSError, ValueError, RuntimeError):
        raise HTTPException(status_code=503, detail='DELETION_UNVERIFIED') from None
    if not deleted:
        raise HTTPException(status_code=404, detail='OWNED_RECORD_NOT_FOUND')
    return {'deleted': True}

@app.post("/api/mental/sessions")
def record_mental_session(payload: CreateSessionPayload):
    return SessionMemoryManager.add_session(
        summary_text=payload.summaryText,
        recurring_themes=payload.recurringThemes,
        duration_seconds=payload.durationSeconds,
        mood_before=payload.moodBefore,
        mood_after=payload.moodAfter,
        escalation_suggested=payload.escalationSuggested or False,
        suggested_action=payload.suggestedAction,
        save_mental_summaries=payload.saveMentalSummaries
    )

# ---------------------------------------------------------------------------
# Care Agent Endpoints (Playwright Browser + Calendar Collision + Travel)
# ---------------------------------------------------------------------------

calendar_provider = CalendarProvider()

@app.post("/api/care/match")
async def match_appointments(payload: AppointmentMatchPayload, request: Request):
    from care_provider import get_care_provider, available_window_match, normalize_care_slots
    from starlette.concurrency import run_in_threadpool
    if vehicle_state["vehicleMoving"] or not vehicle_state["vehicleParked"]:
        raise HTTPException(409, "PARK_REQUIRED")
    if await request.is_disconnected(): raise HTTPException(409, "CANCELLED")
    specialty = payload.specialty
    city = payload.preferredCity or "İstanbul"
    # Reject invalid manual windows before any provider/network side effect.
    try: available_window_match(None,payload.availableWindows,payload.durationMin,payload.timeZone)
    except ValueError: raise HTTPException(422,'INVALID_MATCH_WINDOW') from None
    provider=get_care_provider(payload.useBrowserAgent)
    search_result = await run_in_threadpool(provider.search_slots,specialty=specialty,city=city)
    if await request.is_disconnected(): raise HTTPException(409, "CANCELLED")
    if vehicle_state["vehicleMoving"] or not vehicle_state["vehicleParked"]:
        raise HTTPException(409, "PARK_REQUIRED")
    processed_slots = normalize_care_slots(search_result,payload.availableWindows,payload.durationMin,payload.timeZone)

    return {
        "status": search_result.get("status", "SUCCESS"),
        "specialty": specialty,
        "city": city,
        "providerType": search_result.get("providerType"),
        "sourceBadge": search_result.get("sourceBadge"),
        "handoffNote": search_result.get("handoffNote"),
        "liveSearchUrl": search_result.get("liveSearchUrl"),
        "matchedSlots": processed_slots,
        "currentTravelBufferMin": None
    }

# ---------------------------------------------------------------------------
# Privacy & Data Deletion
# ---------------------------------------------------------------------------

@app.post("/api/privacy/wipe")
def wipe_user_health_data():
    SessionMemoryManager.clear_all()
    return {
        "status": "SUCCESS",
        "message": "Tüm yerel sağlık verisi, geçmiş seans kayıtları ve önbellekler başarıyla silindi.",
        "timestamp": datetime.utcnow().isoformat()
    }

# New routes share the same authoritative vehicle state and origin middleware.
import local_health
local_health.parked = lambda: vehicle_state["vehicleParked"] and not vehicle_state["vehicleMoving"]
app.include_router(local_health.router)
