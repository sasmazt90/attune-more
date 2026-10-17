import hashlib
import json
import os
import sys
import threading
from pathlib import Path
import uvicorn

ROOT=Path(sys.argv[1]).resolve().parents[1]
sys.path.insert(0, sys.argv[1])
sys.path.insert(0,str(ROOT/'.runtime/edge-tts'))
# Reuse the former backend's existing secret source, in process memory only.
# Deliberately do not enable main.py's AG/Roboflow credential loader.
os.environ['ATTUNE_LOAD_LOCAL_ENV']='0'
for name in ('ATTUNE_ROBOFLOW_API_KEY','ROBOFLOW_API_KEY'):os.environ.pop(name,None)
source=ROOT.parent/'attune-live-test/.env.local'
if source.is_file():
    for line in source.read_text('utf-8-sig').splitlines():
        name,separator,value=line.partition('=')
        if separator and name.strip() in ('OPENAI_API_KEY','OPENAI_MODEL','OPENAI_TTS_MODEL'):
            os.environ[name.strip()]=value.strip().strip('\"').strip("'")
server = uvicorn.Server(uvicorn.Config("main:app", host="127.0.0.1", port=8311, log_level="info",access_log=False))

def wait_for_shutdown():
    # This pipe is inherited only from our launcher; no HTTP shutdown endpoint.
    sys.stdin.buffer.readline()
    server.should_exit = True

# Load ASGI/native numeric extensions before a blocking Windows stdin reader.
# The previous order stalled NumPy DLL initialization in the normal launcher;
# the owned pipe still controls graceful shutdown once initialization completes.
server.config.load()
from main import app
@app.get('/api/launcher/identity')
def launcher_identity():
    descriptor=json.loads(Path(os.environ['ATTUNE_LAUNCHER_DELIVERY']).read_text('utf8'))
    config=ROOT/'services/core-api/models/skin-type-hosted.json'
    return dict(sourceCommit=descriptor['sourceCommit'],BUILD_ID=descriptor['BUILD_ID'],frontendOrigin='http://127.0.0.1:3000',apiPort=8311,hostedSkinTypeEnabled=json.loads(config.read_text('utf8'))['enabled'],hostedConfigSHA256=hashlib.sha256(config.read_bytes()).hexdigest(),experimentalAcneV5=os.getenv('ATTUNE_EXPERIMENTAL_ACNE_V5')=='1')
threading.Thread(target=wait_for_shutdown, daemon=True).start()
server.run()
