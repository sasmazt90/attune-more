"""Opt-in, bounded microphone transcription for devices without native ASR.

Audio and transcripts remain in request memory; no payload logging or persistence.
Deploy only on the existing loopback backend. Browser origin and explicit consent
are mandatory, including for callers that do not send an Origin by default.
"""
import base64
import binascii
import json
import os
from threading import BoundedSemaphore

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from openai_client import get_openai_client

router = APIRouter()
MAX_BODY = 2_800_000
MAX_AUDIO = 2_000_000
_slot = BoundedSemaphore(1)


def transcribe(audio, suffix, language):
    if not _slot.acquire(blocking=False):
        raise HTTPException(429, "SPEECH_BUSY")
    try:
        key = os.getenv("OPENAI_API_KEY", "")
        if not key:
            raise HTTPException(503, "SPEECH_PROVIDER_UNAVAILABLE")
        client = get_openai_client(key)
        result = client.audio.transcriptions.create(
            model="gpt-transcribe", file=("microphone." + suffix, audio),
            extra_body={"languages": [language]},
        )
        text = result.text.strip()
        if not text or len(text) > 4000:
            raise HTTPException(422, "SPEECH_NO_RESULT")
        # The provider has not supplied calibrated recognition confidence.
        return {"text": text, "confidence": 0, "confidenceSource": "unavailable",
                "provider": "openai", "model": "gpt-transcribe"}
    except HTTPException:
        raise
    except Exception:
        # SDK exceptions can include request data. Never echo or log them.
        raise HTTPException(502, "SPEECH_PROVIDER_FAILED") from None
    finally:
        _slot.release()


@router.post("/api/speech/transcribe")
async def microphone_transcription(request: Request):
    if os.getenv("ATTUNE_CLOUD_ASR_ENABLED") != "1":
        raise HTTPException(404, "SPEECH_DISABLED")
    origins = {s.strip() for s in os.getenv("ATTUNE_TRUSTED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")}
    if request.headers.get("origin") not in origins or "*" in origins:
        raise HTTPException(403, "SPEECH_ORIGIN_REQUIRED")
    if request.headers.get("content-type", "").split(";")[0] != "application/json":
        raise HTTPException(415, "SPEECH_JSON_REQUIRED")
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_BODY:
            raise HTTPException(413, "SPEECH_TOO_LARGE")
    try:
        value = json.loads(body)
        if not isinstance(value, dict) or value.get("consent") is not True:
            raise HTTPException(403, "SPEECH_CONSENT_REQUIRED")
        if value.get("service") not in ("vision", "mental") or value.get("language") not in ("tr", "en", "de"):
            raise HTTPException(422, "SPEECH_CONTEXT_INVALID")
        audio = base64.b64decode(value["audio"], validate=True)
    except (ValueError, KeyError, TypeError, binascii.Error):
        raise HTTPException(422, "SPEECH_AUDIO_INVALID") from None
    if not 100 <= len(audio) <= MAX_AUDIO:
        raise HTTPException(413, "SPEECH_AUDIO_SIZE_INVALID")
    suffix = "webm" if audio[:4] == b"\x1aE\xdf\xa3" else "wav" if audio[:4] == b"RIFF" and audio[8:12] == b"WAVE" else None
    if suffix is None:
        raise HTTPException(415, "SPEECH_AUDIO_FORMAT_INVALID")
    result = await run_in_threadpool(transcribe, audio, suffix, value["language"])
    return JSONResponse(result, headers={"Cache-Control": "no-store"})
