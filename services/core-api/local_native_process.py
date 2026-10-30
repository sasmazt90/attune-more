"""A native call cannot be cancelled in a thread. Own and reap its process."""
import asyncio
import json
import os
from pathlib import Path
import struct
import sys
from time import monotonic
from fastapi import HTTPException

MAX_MESSAGE=128*1024*1024

class NativeAnalysisProcess:
    def __init__(self):
        self.process=None
        self.idle=None
        self.generation=0

    async def close(self):
        if self.idle is not None:self.idle.cancel();self.idle=None
        process,self.process=self.process,None
        if process is not None:
            if process.returncode is None:
                try:process.kill()
                except ProcessLookupError:pass
            await process.wait()

    async def exchange(self,operation,value):
        if self.process is None or self.process.returncode is not None:
            await self.close()
            env={k:v for k,v in os.environ.items() if not k.startswith('OPENAI_') and k!='ATTUNE_MENTAL_TTS_TOKEN'}
            # Windows venv python.exe is a redirector: killing it can leave the
            # real interpreter alive. Start that interpreter directly with the
            # current, verified virtualenv import paths and prefixes.
            worker=str(Path(__file__).with_name('local_native_worker.py'))
            bootstrap='import sys,runpy;sys.path='+repr(sys.path)+';sys.prefix='+repr(sys.prefix)+';sys.exec_prefix='+repr(sys.exec_prefix)+';runpy.run_path('+repr(worker)+',run_name="__main__")'
            executable=getattr(sys,'_base_executable',sys.executable) if os.name=='nt' else sys.executable
            args=[executable,'-c',bootstrap] if os.name=='nt' else [executable,worker]
            self.process=await asyncio.create_subprocess_exec(*args,stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=None,env=env)
        process=self.process
        raw=json.dumps({'operation':operation,'value':value},allow_nan=False,separators=(',',':')).encode()
        if len(raw)>MAX_MESSAGE:raise HTTPException(413,'PHOTO_LIMIT')
        process.stdin.write(struct.pack('!I',len(raw))+raw)
        await process.stdin.drain()
        size=struct.unpack('!I',await process.stdout.readexactly(4))[0]
        if not 0<size<=MAX_MESSAGE:raise ValueError('INVALID_WORKER_RESPONSE')
        response=json.loads(await process.stdout.readexactly(size))
        if 'status' in response:raise HTTPException(response['status'],response['code'])
        return response['result']

    async def run(self,operation,value,request,permitted,seconds):
        # Caller holds shared admission until close() has actually reaped the
        # process. No late result or abandoned native computation survives it.
        if self.idle is not None:self.idle.cancel();self.idle=None
        self.generation+=1
        gone=asyncio.Event()
        async def watch():
            try:
                while True:
                    if (await request.receive())['type']=='http.disconnect':
                        gone.set();return
            except asyncio.CancelledError:raise
            except Exception:gone.set()
        watcher=asyncio.create_task(watch())
        task=asyncio.create_task(self.exchange(operation,value))
        deadline=monotonic()+seconds
        try:
            while not task.done():
                if not permitted() or gone.is_set():raise HTTPException(409,'CANCELLED')
                if monotonic()>=deadline:raise HTTPException(504,'LOCAL_ANALYSIS_TIMEOUT')
                await asyncio.wait({task},timeout=.05)
            if not permitted() or gone.is_set():raise HTTPException(409,'CANCELLED')
            if monotonic()>=deadline:raise HTTPException(504,'LOCAL_ANALYSIS_TIMEOUT')
            return await task
        except BaseException:
            # Stop a pending spawn/exchange before releasing its process. A
            # late spawn must not publish a new worker after close() returned.
            task.cancel()
            await asyncio.gather(task,return_exceptions=True)
            await self.close()
            raise
        finally:
            task.cancel();watcher.cancel()
            await asyncio.gather(task,watcher,return_exceptions=True)
            if self.process is not None:
                generation=self.generation
                async def expire():
                    if self.generation==generation:await self.close()
                self.idle=asyncio.get_running_loop().call_later(120,lambda:asyncio.create_task(expire()))

native_analysis=NativeAnalysisProcess()
