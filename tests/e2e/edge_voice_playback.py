"""Two nonpersonal real Edge requests via normal API and production MPEG helper.
No OpenAI/chat/summary, no physical input, no transcript or event injection.
Run only on the ordinary keyless backend, not ui_contract_backend.
"""
import json,subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright
OUT=Path('audit-results/product-decisions-20261005/voices');OUT.mkdir(parents=True,exist_ok=True)
code=subprocess.check_output(['node','-e',"const fs=require('fs'),ts=require('typescript');process.stdout.write(ts.transpileModule(fs.readFileSync('apps/vehicle-app/src/utils/streamSpeech.ts','utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText)"],text=True).replace('export function streamSpeech','function streamSpeech')
with sync_playwright() as pw:
 b=pw.chromium.launch(channel='chromium',headless=True,args=['--autoplay-policy=no-user-gesture-required']);c=b.new_context();p=c.new_page()
 c.add_init_script("navigator.mediaDevices.getUserMedia=()=>{throw Error('Physical input forbidden')};const S=window.SpeechRecognition||window.webkitSpeechRecognition;if(S)S.prototype.start=()=>{throw Error('Physical STT forbidden')}")
 c.request.post('http://localhost:8000/api/vehicle/speed',data={'speedKmH':0});p.goto('http://localhost:3000/mental');p.add_script_tag(content=code+';window.productionStreamSpeech=streamSpeech')
 result=p.evaluate("""async()=>{
  const results=[];
  for(const [route,text] of [['vision','right'],['mental','Buradayım. İsterseniz gününüzü anlatabilirsiniz.']]){
   const events=[],timings=[],start=performance.now(),controller=new AbortController();
   const response=await fetch('http://localhost:8000/api/'+route+'/speech',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text,cloudConsent:true}),signal:controller.signal});
   if(!response.ok)throw Error('Exact '+route+' unavailable: '+response.status);
   const audio=new Audio();const ended=new Promise((resolve,reject)=>{for(const type of ['playing','ended','error'])audio.addEventListener(type,()=>{events.push({type,ms:performance.now()-start});if(type==='ended')resolve();if(type==='error')reject(Error('Native playback error'))});setTimeout(()=>reject(Error('Native ended missing')),20000);});
   const stream=window.productionStreamSpeech(audio,response,controller.signal,()=>true,stage=>timings.push({stage,ms:performance.now()-start}));
   await stream.finished;await ended;const duration=Number.isFinite(audio.duration)?audio.duration:null;audio.pause();audio.removeAttribute('src');audio.load();stream.cancel();URL.revokeObjectURL(stream.url);
   results.push({route,events,timings,duration,providerHeader:response.headers.get('server-timing')});
  }return results;
 }""")
 for r in result:
  assert any(e['type']=='playing' for e in r['events']) and any(e['type']=='ended' for e in r['events']) and not any(e['type']=='error' for e in r['events'])
 proof={'status':'PASS','routes':result,'realEdgeRequests':2,'paidOpenAIRequests':0,'physicalCapture':0,'productionMPEGHelper':True,'browser':b.version,'humanAuditoryAcceptance':'manual pending','clipchampLowEquivalent':False}
 (OUT/'production-native-playback.json').write_text(json.dumps(proof,indent=2));c.close();b.close()
print(json.dumps(proof))
