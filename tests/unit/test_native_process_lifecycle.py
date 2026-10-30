"""Real sleeping OS process: timeout, movement, disconnect and subsequent reuse."""
import asyncio
from pathlib import Path
import sys
import pytest
from fastapi import HTTPException
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'services/core-api'))
from local_native_process import NativeAnalysisProcess

@pytest.mark.parametrize('reason',['timeout','movement','disconnect','cancel'])
def test_uncooperative_native_process_is_reaped(reason):
    async def scenario():
        service=NativeAnalysisProcess();spawned=asyncio.Event();gone=asyncio.Event();allowed=True
        class Request:
            async def receive(self):
                await gone.wait();return {'type':'http.disconnect'}
        async def work(*_):
            service.process=await asyncio.create_subprocess_exec(getattr(sys,'_base_executable',sys.executable),'-c','import time;time.sleep(60)')
            spawned.set();await service.process.wait()
        service.exchange=work
        task=asyncio.create_task(service.run('skin',{},Request(),lambda:allowed,.2))
        await spawned.wait();process=service.process
        if reason=='movement':allowed=False
        if reason=='disconnect':gone.set()
        if reason=='cancel':task.cancel()
        with pytest.raises((HTTPException,asyncio.CancelledError)):
            await asyncio.wait_for(task,3)
        assert process.returncode is not None and service.process is None
        # A healthy subsequent request is admitted by the same supervisor.
        allowed=True;gone.clear()
        async def success(*_):return {'result':'new computation'}
        service.exchange=success
        assert await service.run('dental',{},Request(),lambda:allowed,1)=={'result':'new computation'}
    asyncio.run(scenario())
