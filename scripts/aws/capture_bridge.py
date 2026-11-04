"""Opt-in remote demo camera transport, NOT a vehicle camera HAL.

Run one process per isolated AAOS demo. Bind loopback behind the mTLS gateway.
Public ingress must authenticate /bridge/sender and block /bridge/pair and
/bridge/receiver. Frame bytes/capabilities never enter logs or persistent storage.
"""
import asyncio
from dataclasses import dataclass, field
import json
import os
import secrets
import time

import httpx
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect

PNG = b'\x89PNG\r\n\x1a\n'
MAX_BYTES = 8 * 1024 * 1024
# A frame is captured after its challenge, so the challenge proves it is new. These limits say how long that frame may
# take to arrive, not how old an analysed image may be: pages only use frames they have not seen, and stop trusting the
# preview after 750 ms without one. A lossless 1080p frame is about 3.3 MB, so a real camera on home upload needs seconds.
FRAME_SECONDS = 4.0
RECEIVER_SECONDS = 2.0
# PARK is checked this often whatever the frames are doing, so a slow frame never delays leaving PARK.
PARK_POLL_SECONDS = .25
# The state being unreadable is not the same as DRIVE, but frames stop at once and the session ends after this long.
PARK_UNKNOWN_SECONDS = 2.0

@dataclass
class Pair:
    receiver_key: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    sender_key: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    source_id: str = field(default_factory=lambda: secrets.token_hex(16))
    created: float = field(default_factory=time.monotonic)
    receiver: object = None
    sender: object = None
    closed: bool = False
    sequence: int = 0

    def valid(self):
        return not self.closed and time.monotonic() - self.created < (1800 if self.sender else 120)


def valid_frame(raw):
    if len(raw) < 24 or len(raw) > MAX_BYTES or not raw.startswith(PNG):
        return False
    width, height = int.from_bytes(raw[16:20], 'big'), int.from_bytes(raw[20:24], 'big')
    return 320 <= width <= 1920 and 240 <= height <= 1080


def create_app(parked, receiver_origins, sender_origins):
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    state = {'pair': None}

    async def revoke(pair, reason=None):
        if reason and not pair.closed:
            # Reasons and counts only. Frames and capabilities never enter logs.
            print(json.dumps({'captureEnded': reason, 'frames': pair.sequence, 'seconds': round(time.monotonic() - pair.created, 1)}), flush=True)
        pair.closed = True
        for socket in (pair.sender, pair.receiver):
            if socket:
                # One socket failing to close must never leave the other one open.
                try:
                    await socket.close(code=1000)
                except Exception:  # noqa: BLE001
                    pass
        if state['pair'] is pair:
            state['pair'] = None

    @app.post('/bridge/pair')
    async def pair(request: Request):
        if request.headers.get('origin') not in receiver_origins:
            raise HTTPException(403)
        value = await request.json()
        if value != {'processingConsent': True} or not await parked():
            raise HTTPException(409, 'CONSENT_AND_PARK_REQUIRED')
        previous = state['pair']
        if previous and previous.valid():
            raise HTTPException(409, 'CAPTURE_ALREADY_ACTIVE')
        if previous:
            await revoke(previous)
        current = state['pair'] = Pair()
        return {'receiverKey': current.receiver_key, 'senderKey': current.sender_key,
                'sourceId': current.source_id, 'sourceType': 'remote-demo-camera'}

    async def join(ws, role, origins):
        if ws.headers.get('origin') not in origins:
            await ws.close(code=1008)
            return None
        await ws.accept()
        try:
            hello = await asyncio.wait_for(ws.receive_json(), 5)
            pair = state['pair']
            key = getattr(pair, role+'_key', '')
            if not pair or not pair.valid() or not isinstance(hello.get('key'), str) or not secrets.compare_digest(hello['key'], key) or hello.get('consent') is not True or getattr(pair, role) is not None or not await parked():
                await ws.close(code=1008)
                return None
            setattr(pair, role, ws)
            return pair
        except (TimeoutError, ValueError, WebSocketDisconnect):
            await ws.close(code=1008)
            return None

    @app.websocket('/bridge/receiver')
    async def receiver(ws: WebSocket):
        pair = await join(ws, 'receiver', receiver_origins)
        if not pair:
            return
        try:
            # Receiver never sends frame data. Any further message cancels.
            await asyncio.wait_for(ws.receive(), 1800)
        finally:
            await revoke(pair)

    @app.websocket('/bridge/sender')
    async def sender(ws: WebSocket):
        pair = await join(ws, 'sender', sender_origins)
        if not pair:
            return
        if not pair.receiver:
            await revoke(pair, 'no-receiver')
            return
        confirmed = time.monotonic()

        async def watch_park():
            nonlocal confirmed
            while pair.valid():
                value = await parked()
                now = time.monotonic()
                if value is True:
                    confirmed = now
                elif value is False:
                    await revoke(pair, 'not-parked')
                    return
                elif now - confirmed >= PARK_UNKNOWN_SECONDS:
                    await revoke(pair, 'park-state-unknown')
                    return
                await asyncio.sleep(PARK_POLL_SECONDS)

        guard = asyncio.create_task(watch_park())
        step = 'challenge'
        reason = 'session-ended'
        try:
            while pair.valid():
                nonce = secrets.token_hex(16)
                started = time.monotonic()
                step = 'challenge'
                await ws.send_json({'challenge':nonce})
                response = await asyncio.wait_for(ws.receive_json(), FRAME_SECONDS)
                step = 'frame'
                frame = await asyncio.wait_for(ws.receive_bytes(), max(.05, FRAME_SECONDS-(time.monotonic()-started)))
                if response != {'challenge':nonce} or not valid_frame(frame):
                    reason = 'invalid-frame'
                    return
                # Nothing goes out unless PARK was confirmed for this frame, and a stopped session has no receiver left.
                if time.monotonic()-confirmed >= PARK_POLL_SECONDS*4 or not pair.valid():
                    continue
                pair.sequence += 1
                step = 'receiver'
                await asyncio.wait_for(pair.receiver.send_json({'sourceId':pair.source_id,'sequence':pair.sequence,'sourceType':'remote-demo-camera'}), RECEIVER_SECONDS)
                await asyncio.wait_for(pair.receiver.send_bytes(frame), RECEIVER_SECONDS)
                # One frame in flight, no unbounded queue or replay buffer.
                await asyncio.sleep(.1)
        except TimeoutError:
            reason = 'timeout-' + step
        except WebSocketDisconnect:
            reason = 'disconnected-' + step
        except (ValueError, RuntimeError):
            reason = 'error-' + step
        finally:
            guard.cancel()
            await asyncio.gather(guard, return_exceptions=True)
            await revoke(pair, reason)

    return app


async def backend_parked():
    try:
        async with httpx.AsyncClient(trust_env=False, timeout=1) as client:
            response = await client.get('http://127.0.0.1:8001/api/vehicle/state')
            response.raise_for_status()
            value = response.json()
            return value.get('vehicleParked') is True and value.get('vehicleMoving') is False and value.get('currentSpeed') == 0
    except (httpx.HTTPError, ValueError):
        # Unknown, not DRIVE. The bridge treats it as not parked unless a recent answer said PARK.
        return None


def configured_app():
    sender = os.environ['ATTUNE_CAPTURE_SENDER_ORIGIN']
    if not sender.startswith('https://') or sender.endswith('/'):
        raise ValueError('Exact HTTPS sender origin required')
    return create_app(backend_parked, {'http://127.0.0.1:3000'}, {sender})
