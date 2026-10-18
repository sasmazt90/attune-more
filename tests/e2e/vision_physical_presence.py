"""Owned visible production browser, actual camera, no saved frames or fake STT.
Only records numeric gate observations; no user acceptance inferred from presence.
"""
import json,time
from pathlib import Path
from playwright.sync_api import sync_playwright
OUT=Path('audit-results/vision-usable');OUT.mkdir(parents=True,exist_ok=True)
with sync_playwright() as pw:
 b=pw.chromium.launch(channel='chrome',headless=False,args=['--autoplay-policy=no-user-gesture-required']);c=b.new_context(permissions=['camera','microphone'],viewport={'width':1500,'height':950});p=c.new_page();errors=[];p.on('pageerror',lambda e:errors.append(str(e)))
 c.add_init_script("window.physicalStreams=[];window.cameraErrors=[];const original=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);navigator.mediaDevices.getUserMedia=async(...args)=>{try{const s=await original(...args);window.physicalStreams.push(s);return s;}catch(e){window.cameraErrors.push({name:e.name,message:e.message});throw e;}};")
 c.add_init_script("window.workerErrors=[];const NativeWorker=window.Worker;window.Worker=class extends NativeWorker{constructor(...args){super(...args);this.addEventListener('message',e=>{if(e.data?.error)window.workerErrors.push(e.data.error)});this.addEventListener('error',e=>window.workerErrors.push(e.message));}};")
 c.request.post('http://127.0.0.1:8000/api/vehicle/speed',data={'speedKmH':0});p.goto('http://127.0.0.1:3000/vision');p.get_by_role('button',name='Başlat',exact=True).click()
 rows=[]
 for i in range(45):
  p.wait_for_timeout(1000);row=p.evaluate("()=>({at:performance.now(),stage:document.querySelector('[data-vision-stage]')?.dataset.visionStage,evidence:JSON.parse(document.querySelector('canvas')?.dataset.visionEvidence||'null'),letter:!!document.querySelector('[data-letter-optotype]'),error:document.querySelector('[role=alert]')?.textContent,device:document.querySelector('video')?{width:document.querySelector('video').videoWidth,height:document.querySelector('video').videoHeight}:null})");rows.append(row)
  if row['stage']=='idle' and row['error']:break
 if p.get_by_role('button',name='Bitir',exact=True).count():p.get_by_role('button',name='Bitir',exact=True).click()
 tracksEnded=p.evaluate("window.physicalStreams.every(s=>s.getTracks().every(t=>t.readyState==='ended'))")
 summary={'physicalCameraAttempt':True,'userPresenceConfirmed':False,'fixtureVideo':False,'fakeSTT':False,'framesSaved':0,'framesSentToCloud':0,'errors':errors,'cameraErrors':p.evaluate('window.cameraErrors'),'workerErrors':p.evaluate('window.workerErrors'),'streamCount':p.evaluate('window.physicalStreams.length'),'anyTrackedFace':any(r['evidence'] and r['evidence']['conditions']['faceCount']==1 for r in rows),'baselineReady':any(r['evidence'] and r['evidence']['conditions']['positionValid'] for r in rows),'letterVisible':any(r['letter'] for r in rows),'tracksEnded':tracksEnded,'positiveUserAcceptance':'OPEN','rows':rows}
 (OUT/'physical-presence.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),'utf8');print(json.dumps({k:v for k,v in summary.items() if k!='rows'}));c.close();b.close()
