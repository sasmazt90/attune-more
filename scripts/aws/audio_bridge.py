"""Optional authenticated demo PCM transport to/from the emulator host PulseAudio.
No calibration/clinical or guest-device compatibility claim. Loopback listener only.
"""
import asyncio
import math
import os
import struct
from fastapi import FastAPI, WebSocket, WebSocketDisconnect


def valid_microphone_frame(value):
    return (0 < len(value) <= 16384 and len(value)%4 == 0
            and all(math.isfinite(v[0]) and abs(v[0]) <= 1 for v in struct.iter_unpack('<f',value)))


def create_app(origin):
    app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None)
    active=asyncio.Lock()

    @app.websocket('/audio/ws')
    async def audio(ws:WebSocket):
        if ws.headers.get('origin')!=origin or active.locked():
            await ws.close(code=1008);return
        async with active:
            await ws.accept()
            processes=[];tasks=[]
            try:
                hello=await asyncio.wait_for(ws.receive_json(),10)
                if hello not in ({'listenConsent':True,'microphoneConsent':False},{'listenConsent':True,'microphoneConsent':True}):
                    await ws.close(code=1008);return
                output=await asyncio.create_subprocess_exec('parec','--device=attune_out.monitor','--format=float32le','--rate=48000','--channels=2','--latency-msec=20',stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL)
                processes.append(output)
                microphone=None
                if hello['microphoneConsent']:
                    microphone=await asyncio.create_subprocess_exec('pacat','--playback','--device=attune_mic','--format=float32le','--rate=48000','--channels=1','--latency-msec=20',stdin=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL)
                    processes.append(microphone)
                async def play():
                    while True:
                        data=await asyncio.wait_for(output.stdout.readexactly(4096),2)
                        await asyncio.wait_for(ws.send_bytes(data),.5)
                async def record():
                    while True:
                        data=await ws.receive_bytes()
                        if not microphone or not valid_microphone_frame(data):raise ValueError('Invalid microphone frame')
                        microphone.stdin.write(data)
                        await asyncio.wait_for(microphone.stdin.drain(),.5)
                tasks=[asyncio.create_task(play()),asyncio.create_task(record())]
                done,_=await asyncio.wait(tasks,return_when=asyncio.FIRST_COMPLETED)
                for task in done:task.result()
            except (TimeoutError,ValueError,KeyError,TypeError,OSError,asyncio.IncompleteReadError,WebSocketDisconnect,RuntimeError):
                pass
            finally:
                for task in tasks:task.cancel()
                await asyncio.gather(*tasks,return_exceptions=True)
                for process in processes:
                    if process.returncode is None:
                        process.terminate()
                        try:await asyncio.wait_for(process.wait(),2)
                        except TimeoutError:process.kill();await process.wait()
                try:await ws.close(code=1000)
                except (RuntimeError,WebSocketDisconnect):pass
    return app


def configured_app():
    origin=os.environ['ATTUNE_AUDIO_ORIGIN']
    if not origin.startswith('https://') or origin.endswith('/'):
        raise ValueError('Exact HTTPS origin required')
    return create_app(origin)
