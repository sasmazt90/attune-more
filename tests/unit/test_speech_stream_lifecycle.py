"""Actual ASGI lifecycle; no provider or microphone calls."""
import asyncio,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'services/core-api'))
from speech_stream import ProviderSpeechResponse,close_once
class Context:
    def __init__(self):self.closed=0
    def __exit__(self,*args):self.closed+=1

def test_close_once_is_idempotent():
    context=Context();close=close_once(context);close();close();assert context.closed==1

def test_disconnect_before_first_chunk_closes_provider():
    async def run():
        context=Context();close=close_once(context);chunks=[]
        async def receive():return {'type':'http.disconnect'}
        async def send(message):chunks.append(message)
        async def body():
            await asyncio.sleep(10)
            yield b'not delivered'
        await ProviderSpeechResponse(body(),close,media_type='audio/mpeg')({'type':'http','asgi':{'spec_version':'2.0'}},receive,send)
        assert context.closed==1
        assert not any(message.get('body') for message in chunks)
    asyncio.run(run())

def test_ordered_chunks_and_finish_close_provider():
    async def run():
        context=Context();close=close_once(context);messages=[]
        async def receive():await asyncio.sleep(10);return {'type':'http.disconnect'}
        async def send(message):messages.append(message)
        async def body():
            try:
                yield b'first';yield b'second'
            finally:close()
        await ProviderSpeechResponse(body(),close,media_type='audio/mpeg')({'type':'http','asgi':{'spec_version':'2.0'}},receive,send)
        assert context.closed==1
        assert [m['body'] for m in messages if m['type']=='http.response.body']==[b'first',b'second',b'']
    asyncio.run(run())
