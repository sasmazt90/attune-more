"""Close a provider stream even when ASGI disconnects before its first chunk."""
from threading import Lock
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

class ProviderSpeechResponse(StreamingResponse):
    def __init__(self, iterator, close, **options):
        super().__init__(iterator, **options)
        self.provider_close = close

    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            await run_in_threadpool(self.provider_close)

def close_once(context):
    lock = Lock()
    closed = False
    def close():
        nonlocal closed
        with lock:
            if not closed:
                closed = True
                context.__exit__(None, None, None)
    return close
