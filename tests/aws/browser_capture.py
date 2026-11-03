"""Real Chromium / production bridge transport test, using a SYNTHETIC browser camera.
No models, clinical outputs, AWS, native APK or AAOS acceptance are claimed.
"""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/aws'))
from capture_bridge import create_app
from fastapi.responses import HTMLResponse
from playwright.sync_api import sync_playwright
import uvicorn

state={'parked':True}
async def parked():return state['parked']
# Local fixtures use one ephemeral origin; deployed bridge uses distinct exact origins.
with socket.socket() as sock:
    sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
origin=f'http://127.0.0.1:{port}'
app=create_app(parked,{origin},{origin})
compile_script="""const fs=require('fs'),ts=require('typescript');let s=fs.readFileSync('apps/vehicle-app/src/utils/demoCamera.ts','utf8');s=s.replace("import {isCameraAllowed} from './attuneMode';", 'const isCameraAllowed=()=>true;');process.stdout.write(ts.transpileModule(s,{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText);"""
js=subprocess.check_output(['node','-e',compile_script],cwd=ROOT,text=True)
@app.get('/')
def index():
    return HTMLResponse('<script>const exports={};const process={env:{NEXT_PUBLIC_ATTUNE_REMOTE_CAPTURE:"1"}};'+js+'</script><video id="v" autoplay muted playsinline></video>')
@app.get('/capture')
def capture():
    return HTMLResponse((ROOT/'infra/aws/aaos/capture.html').read_text().replace("'wss://'", "'ws://'"))
server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,log_level='error',ws_max_size=8*1024*1024,ws_max_queue=1))
thread=threading.Thread(target=server.run,daemon=True);thread.start()
for _ in range(100):
    if server.started:break
    time.sleep(.05)
checks={}
try:
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=os.environ.get('ATTUNE_TEST_CHROME','/workspace/.attune-tools/chrome/opt/google/chrome/chrome'),headless=True,args=['--no-sandbox','--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream'])
        context=browser.new_context(user_agent='AttuneCloudDemo/1 Chromium transport test',permissions=['camera'])
        rx=context.new_page();rx.on('pageerror',lambda e: print('PAGE_ERROR',str(e)));rx.goto(origin)
        rx.evaluate("window.capturePromise=exports.acquireCamera({video:true}).then(s=>{window.stream=s;v.srcObject=s;window.ended=false;s.getVideoTracks()[0].addEventListener('ended',()=>window.ended=true);}).catch(e=>window.error=e.message);void 0")
        rx.wait_for_function("document.querySelector('dialog textarea')||window.error");assert not rx.evaluate('window.error'),rx.evaluate('window.error');key=rx.locator('dialog textarea').input_value()
        tx=context.new_page();tx.goto(origin+'/capture');tx.locator('#key').fill(key);tx.locator('#consent').check();tx.locator('#start').click()
        rx.wait_for_function('window.stream && v.videoWidth>0',timeout=20000)
        checks['realBrowserPngTransport']=rx.evaluate('v.videoWidth>0&&v.currentTime>=0')
        checks['sourceIdentity']=rx.evaluate("exports.demoCameraSource().sourceType==='remote-demo-camera'")
        state['parked']=False
        rx.wait_for_function('window.ended===true',timeout=5000)
        checks['driveStopsTrack']=rx.evaluate("stream.getVideoTracks()[0].readyState==='ended'")
        checks['sourceCleared']=rx.evaluate('exports.demoCameraSource()===undefined')
        browser.close()
finally:
    server.should_exit=True;thread.join(timeout=5)
report={'checks':checks,'camera':'synthetic Chromium input','aws':'NOT_RUN','AAOS':'NOT_RUN','inference':'NOT_RUN'}
out=ROOT/'docs/aws/evidence/browser-capture.json';out.write_text(json.dumps(report,indent=2)+'\n')
assert len(checks)==4 and all(checks.values()),report
print(json.dumps(report))
