'use strict';
// One three-turn conversation per language/surface, two AAOS interruption checks.
// Real test build, provider, recorded files and media; only microphone/ASR synthetic.
const fs=require('fs'),path=require('path');
const {chromium}=require(process.env.HYBRID_PLAYWRIGHT||'playwright');
const {cancellationRegistry,forwardVerbatim,fulfillHeaders}=require('./aaos/closing_live_forward.cjs');
const {closingSequence}=require('./aaos/closing_stop_verdict.cjs');
const surface=process.env.HYBRID_SURFACE||'WEB',aaos=surface==='AAOS';
const out=process.env.HYBRID_OUT;fs.mkdirSync(out,{recursive:true});
const origin=aaos?'http://127.0.0.1:3000':'http://127.0.0.1:13102',front=aaos?'http://127.0.0.1:13103':origin;
const api='http://127.0.0.1:18192',vehicle=aaos?'http://127.0.0.1:18001':api;
const report={surface,commit:process.env.HYBRID_SHA,buildId:process.env.HYBRID_BUILD_ID,startedAt:new Date().toISOString(),boundary:'Separate test build via existing SSM connections; installed AAOS shell/native gates retained. Synthetic microphone+ASR only. Real provider, existing female-calm-v1 TTS and approved recordings. Media playing/ended indicators; not acoustic microphone measurement or public DNS validation.',runs:[]};
const save=()=>fs.writeFileSync(path.join(out,surface+'.json'),JSON.stringify(report,null,2));
const inputs={tr:['Son haftalarda işte tempo çok yoğun ve uykum sık sık bölünüyor.','Her gece oluyor; gün içinde odaklanmakta zorlanıyorum.','Düzeltmek istiyorum: üzgün değilim. Şimdilik tavsiye istemiyorum, sadece konuşmak istiyorum.'],en:['Work has been very intense lately and my sleep keeps getting interrupted.','It happens every night; during the day I cannot concentrate.','To clarify, I am not sad. For now I only want to talk, no advice.'],de:['Bei der Arbeit ist es sehr intensiv und mein Schlaf wird oft unterbrochen.','Es passiert jede Nacht; tagsüber kann ich mich nicht konzentrieren.','Zur Klarstellung: Ich bin nicht traurig. Ich möchte im Moment nur reden, keine Ratschläge.']};
const source=fs.readFileSync(path.join(__dirname,'aaos/aaos-mental-closing.cjs'),'utf8');
let script=eval(source.match(/const PAGE_SCRIPT = (`[\s\S]*?`);\n/)[1]);
script=script.replace("stage:e.detail.stage,atMs:e.detail.atMs", "stage:e.detail.stage,atMs:e.detail.atMs,turn:e.detail.turn").replace("emit('stage',{stage:e.detail.stage})", "emit('stage',{stage:e.detail.stage,turn:e.detail.turn,pm:e.detail.atMs})").replace("url.includes('/audio/mental/closing-')","url.includes('/audio/mental/')");
const mic=`(()=>{const original=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);navigator.mediaDevices.getUserMedia=async c=>{if(!c.audio)return original(c);const ctx=new AudioContext(),dest=ctx.createMediaStreamDestination(),osc=ctx.createOscillator(),gain=ctx.createGain();osc.frequency.value=300;gain.gain.value=window.__qaUtterances?.length ? 0.15 : 0;osc.connect(gain);gain.connect(dest);await ctx.resume();osc.start();setTimeout(()=>{gain.gain.value=0;osc.stop()},800);for(const t of dest.stream.getTracks()){const stop=t.stop.bind(t);t.stop=()=>{stop();void ctx.close().catch(()=>{});};}return dest.stream;};})();`;
const durations=new Map();for(const n of ['closing-abc','closing-catalog'])for(const e of JSON.parse(fs.readFileSync(path.join(__dirname,`../../apps/vehicle-app/public/audio/mental/${n}/v1/manifest.json`))).entries)durations.set(e.audioPath,e.durationMs/1000);
const phase=page=>page.locator('[data-conversation-phase]').getAttribute('data-conversation-phase');
async function speed(kmh){for(const target of new Set([api,vehicle])){const r=await fetch(target+'/api/vehicle/speed',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({speedKmH:kmh})});if(!r.ok)throw Error('vehicle transition failed');}}
(async()=>{let browser,page,savedStorage,current;
 try{
 if(aaos){browser=await chromium.connectOverCDP('http://127.0.0.1:19226');page=browser.contexts()[0].pages().find(p=>p.url().startsWith(origin));if(!page)throw Error('AAOS page missing');savedStorage=await page.evaluate(()=>Object.fromEntries(Object.entries(localStorage)));fs.writeFileSync(path.join(out,'private-storage.json'),JSON.stringify(savedStorage),{mode:0o600});}
 else{browser=await chromium.launch({executablePath:process.env.HYBRID_CHROME,headless:true,ignoreDefaultArgs:['--mute-audio'],args:['--no-sandbox','--disable-dev-shm-usage']});page=await browser.newPage();}
 page.setDefaultTimeout(20000);await page.addInitScript(script);await page.addInitScript(mic);
 page.on('console',m=>{const t=m.text();if(current&&t.startsWith('__qa '))try{current.events.push(JSON.parse(t.slice(5)));}catch{}});
 const registry=cancellationRegistry(page);
 await page.route('**/*',async route=>{
  const request=route.request(),u=new URL(request.url());if(u.origin!==origin){await route.continue();return;}
  if(u.pathname==='/api/speech/transcribe'){const text=await page.evaluate(()=>window.__qaUtterances.shift()||' ');await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({text})});return;}
  const entry=registry.signalFor(request);let target=u.pathname.startsWith('/api/vehicle/')?vehicle:u.pathname.startsWith('/api/')&&u.pathname!='/api/mental-neural-speech'?api:front;
  let row;
  if(current&&['/api/mental/converse','/api/mental/analyze-session','/api/mental-neural-speech'].includes(u.pathname)){row={path:u.pathname,at:Date.now(),body:request.postDataJSON()};current.requests.push(row);}
  try{const response=await forwardVerbatim(request,target,entry.controller.signal);if(row){row.status=response.status;row.answeredAt=Date.now();if(response.headers['content-type']?.includes('json'))row.response=JSON.parse(response.body.toString());}
   await route.fulfill({status:response.status,headers:fulfillHeaders(response.headers),body:response.body});
  }catch(e){if(row){row.aborted=entry.controller.signal.aborted;row.abortReason=entry.reason;row.endedAt=Date.now();}await route.abort().catch(()=>{});}
  finally{registry.release(request);}
 });
 async function open(language){await speed(0);await page.goto(origin+'/');await page.evaluate(l=>{localStorage.setItem('attune.language.v1',l);localStorage.removeItem('togg_health_mental_history');localStorage.removeItem('togg_health_latest_mental');},language);await page.goto(origin+'/mental');
  const dialog=page.getByRole('dialog');if(await dialog.count()){for(const box of await dialog.getByRole('checkbox').all())await box.check();await dialog.getByRole('button').filter({hasText:/İzin ver ve devam et|Allow and continue|Erlauben und fortfahren/}).click();}
 }
 for(const language of ['tr','en','de']){
  current={language,status:'RUNNING',events:[],requests:[],turns:[],startedAt:new Date().toISOString()};report.runs.push(current);save();
  try{
   await open(language);await page.evaluate(t=>window.__qaUtterances.push(t),inputs[language][0]);
   await page.getByRole('button').filter({hasText:/Görüşmeyi Başlat|Start conversation|Gespräch starten/}).first().click();
   for(let i=0;i<3;i++){
    if(i)await page.evaluate(t=>window.__qaUtterances.push(t),inputs[language][i]);
    await page.waitForFunction(n=>document.querySelectorAll('[data-chat-author=AI]').length>=n&&document.querySelector('[data-conversation-phase]')?.getAttribute('data-conversation-phase')==='listening',i+1,{timeout:25000});
    const events=current.events.filter(e=>e.kind==='stage'&&e.turn===i+1),at=s=>events.find(e=>e.stage===s)?.pm;
    const t0=at('hybrid-t0'),start=at('hybrid-first-playing'),select=events.find(e=>e.stage.startsWith('hybrid-selected-'));
    const a=at('prepared-0-ended'),b=at('prepared-1-playing');
    const turn={turn:i+1,input:inputs[language][i],path:select?.stage.replace('hybrid-selected-',''),decisionMs:select?.pm-t0,firstSoundMs:start-t0,selectedToSoundMs:start-select?.pm,aToBMs:a!==undefined&&b!==undefined?b-a:null,asr:'synthetic; end-of-real-speech to ASR not measured',indicator:aaos?'Android WebView media playing':'browser media playing'};
    turn.pass=Number.isFinite(turn.firstSoundMs)&&turn.decisionMs<=3100&&turn.selectedToSoundMs>=0&&turn.selectedToSoundMs<500&&events.filter(e=>e.stage.startsWith('hybrid-selected-')).length===1;
    current.turns.push(turn);save();if(!turn.pass)throw Error('Timing or single-winner criterion failed');
   }
   current.transcript=await page.locator('[data-chat-author]').evaluateAll(xs=>xs.map(x=>({role:x.getAttribute('data-chat-author'),text:x.textContent})));
   const first=current.events.length;current.closingAt=Date.now();await page.getByRole('button').filter({hasText:/Görüşmeyi Bitir|End conversation|Gespräch beenden/}).first().click();
   await page.waitForFunction(()=>document.querySelector('[data-conversation-phase]')?.getAttribute('data-conversation-phase')==='completed',null,{timeout:60000});await page.waitForTimeout(1000);
   const events=current.events.slice(first),assets=[...new Set(events.filter(e=>e.kind==='asset').map(e=>e.url))],only=xs=>xs.length===1?durations.get(xs[0])??null:null;
   const parts=['A','B','C'].map(g=>({part:g,expectedS:only(assets.filter(u=>u.includes('/closing-abc/')&&u.includes('/'+g+'/')))}));parts.push({part:'P',expectedS:only(assets.filter(u=>u.includes('/closing-catalog/')))});
   current.closing=closingSequence({parts,stages:events.filter(e=>e.kind==='stage'),media:events.filter(e=>e.kind==='media')});
   const at=s=>events.find(e=>e.kind==='stage'&&e.stage===s)?.pm;current.cToPersonalMs=at('closing-summary-audio-start')-at('closing-C-ended');
   const analysis=current.requests.find(q=>q.path==='/api/mental/analyze-session');current.writtenSummary=!!analysis?.response?.summaryText&&await page.evaluate(text=>JSON.parse(localStorage.getItem('togg_health_mental_history')||'[]').some(x=>x.summaryText===text&&x.completed&&x.consented),analysis.response.summaryText);
   current.noDynamicClosing=!current.requests.some(q=>q.path==='/api/mental-neural-speech'&&q.at>=current.closingAt);
   current.status=current.closing.status==='PASS'&&current.writtenSummary&&current.noDynamicClosing?'PASS':'FAIL';
   await page.screenshot({path:path.join(out,surface+'-'+language+'.png')});
  }catch(e){current.status='FAIL';current.error=String(e);}
  current.finishedAt=new Date().toISOString();save();console.log(JSON.stringify({surface,language,status:current.status,turns:current.turns,cToPersonalMs:current.cToPersonalMs,error:current.error}));
  if(current.status!=='PASS')break;
 }
 if(aaos&&report.runs.every(r=>r.status==='PASS'))for(const action of ['consent','drive']){
  current={language:'tr',action,status:'RUNNING',events:[],requests:[]};report.runs.push(current);save();
  try{
   await open('tr');await page.evaluate(t=>window.__qaUtterances.push(t),inputs.tr[0]);await page.getByRole('button',{name:'Görüşmeyi Başlat',exact:true}).click();
   await page.waitForFunction(()=>window.__timeline.some(e=>e.stage==='hybrid-t0'),null,{timeout:15000});
   current.actionPm=await page.evaluate(()=>performance.now());
   if(action==='consent')await page.evaluate(()=>{const key='attune_health_processing_v1',d=JSON.parse(localStorage.getItem(key));delete d.services.mental;localStorage.setItem(key,JSON.stringify(d));dispatchEvent(new Event('attune-service-consent'));dispatchEvent(new Event('attune-privacy'));});else await speed(75);
   await new Promise(ok=>setTimeout(ok,4500));
   current.playsAfter=current.events.filter(e=>e.kind==='media'&&e.type==='playing'&&e.pm>current.actionPm);
   current.status=current.playsAfter.length===0?'PASS':'FAIL';
  }catch(e){current.status='FAIL';current.error=String(e);}finally{await speed(0);save();console.log(JSON.stringify({surface,action,status:current.status,error:current.error}));}
 }
 }catch(e){report.error=String(e);}
 finally{
  try{await speed(0);if(aaos&&savedStorage&&!page.isClosed()){await page.unrouteAll({behavior:'ignoreErrors'});await page.evaluate(d=>{localStorage.clear();for(const [k,v] of Object.entries(d))localStorage.setItem(k,v);},savedStorage);report.storageRestored=true;}}catch(e){report.restoreError=String(e);}
  report.finishedAt=new Date().toISOString();save();await browser?.close();
 }
})();
