const fs=require('fs'),path=require('path'),assert=require('assert/strict');
// Machine-local locations come from the environment; see scripts/qa/README.md.
const {chromium}=require(process.env.ATTUNE_QA_PLAYWRIGHT||'playwright');
const root=path.resolve(process.env.ATTUNE_QA_OUT||path.join(__dirname,'../../../output/qa'));fs.mkdirSync(path.join(root,'runtime'),{recursive:true});
const fixtureRoot=process.env.ATTUNE_QA_FIXTURES;if(!fixtureRoot)throw Error('ATTUNE_QA_FIXTURES is required');
const product=path.resolve(__dirname,'../../..');
const origin=process.env.ATTUNE_QA_ORIGIN||'http://localhost:3000';const language=process.env.ATTUNE_QA_LANG||'en';const recordingEnabled=process.env.ATTUNE_QA_RECORD!=='0';
const buildId=process.env.ATTUNE_QA_BUILD_ID||fs.readFileSync(path.join(product,'apps/vehicle-app/.next/BUILD_ID'),'utf8').trim();
const sourceCommit=process.env.ATTUNE_QA_SHA||require('child_process').execFileSync('git',['-C',product,'rev-parse','HEAD'],{encoding:'utf8'}).trim();
const catalog=Object.values(JSON.parse(fs.readFileSync(path.join(product,'shared/localization/messages.json'),'utf8')));
const tr=text=>language==='tr'?text:catalog.find(v=>v.tr.trim()===text.trim())?.[language]||text;
async function open(module,{camera,microphone}={}){
 const out=path.join(root,'runs',module+'-'+Date.now());fs.mkdirSync(out,{recursive:true});
 const r={module,started:new Date().toISOString(),language,platform:'WEB QA service / isolated headless Chrome',sourceCommit,buildId,boundary:process.env.ATTUNE_QA_SCOPE||'Isolated repair services. Headless browser is separately launched, not a capture of the shortcut browser window. Controlled project media; actual product inference. No physical, clinical or AAOS acceptance.',actions:[],inventory:[],responses:[],errors:[]};
 const save=()=>fs.writeFileSync(path.join(out,'evidence.json'),JSON.stringify(r,null,2));save();
 const args=['--autoplay-policy=no-user-gesture-required','--auto-select-tab-capture-source-by-title=Attune.more','--auto-accept-this-tab-capture','--enable-usermedia-screen-capturing','--allow-http-screen-capture'];
 if(camera)args.push('--use-fake-device-for-media-stream','--use-file-for-fake-video-capture='+camera);
 if(microphone)args.push('--disable-audio-input','--use-fake-device-for-media-stream','--use-file-for-fake-audio-capture='+microphone+(process.env.ATTUNE_QA_AUDIO_LOOP==='1'?'':'%noloop'));
 const b=await chromium.launch({headless:true,ignoreDefaultArgs:['--mute-audio'],executablePath:process.env.ATTUNE_QA_CHROME||'C:/Program Files/Google/Chrome/Application/chrome.exe',...(process.env.ATTUNE_QA_PROXY?{proxy:{server:process.env.ATTUNE_QA_PROXY}}:{}),args});
 const c=await b.newContext({viewport:{width:1280,height:720},permissions:['camera','microphone'],acceptDownloads:true,...(process.env.ATTUNE_QA_HTTP_CREDENTIALS_FILE?{httpCredentials:JSON.parse(fs.readFileSync(process.env.ATTUNE_QA_HTTP_CREDENTIALS_FILE,'utf8'))}:{})});
 // Observe only object creation for deterministic silent teardown. No audio,
 // recognition, inference or gate data is replaced during the assessment.
 await c.addInitScript(()=>{window.__taskAudioObjects=[];window.__taskContexts=[];for(const [name,list] of [['Audio',window.__taskAudioObjects],['AudioContext',window.__taskContexts]]){const Original=window[name];window[name]=new Proxy(Original,{construct(target,args,newTarget){const object=Reflect.construct(target,args,newTarget);list.push(object);return object;}});}});
 if(microphone)await c.addInitScript(()=>{window.__nativeSpeechEvents=[];for(const name of ['SpeechRecognition','webkitSpeechRecognition']){const Original=window[name];if(!Original)continue;window[name]=new Proxy(Original,{construct(target,args,newTarget){const object=Reflect.construct(target,args,newTarget);for(const event of ['start','audiostart','soundstart','speechstart','result','error','end'])object.addEventListener(event,e=>window.__nativeSpeechEvents.push({event,error:e.error,at:Date.now(),results:e.results?[...e.results].map(r=>({final:r.isFinal,text:r[0]?.transcript})):undefined}));return object;}});}});
 const p=await c.newPage();p.setDefaultTimeout(20000);
 const pending=[];let recording;let writes=Promise.resolve();
 const stamp=()=>r.recordStart?Math.round((Date.now()-r.recordStart)/100)/10:null;
 p.on('request',req=>{const u=new URL(req.url());if(u.pathname.startsWith('/api/local-health')){r.requestTimes??=[];r.requestTimes.push({path:u.pathname,at:Date.now()});}});p.on('pageerror',e=>r.errors.push(String(e)));
 p.on('response',res=>{const url=new URL(res.url());if(/^\/api\/(local-health|speech\/transcribe|mental\/)/.test(url.pathname))pending.push(res.json().then(body=>{r.responses.push({path:url.pathname,status:res.status(),body,seconds:stamp()});save();}).catch(()=>{}));});
 p.on('response',res=>{if(new URL(res.url()).pathname==='/api/mental-neural-speech')pending.push(res.body().then(data=>{r.responses.push({path:'/api/mental-neural-speech',status:res.status(),bytes:data.length,sha256:require('crypto').createHash('sha256').update(data).digest('hex'),seconds:stamp()});save();}).catch(()=>{}));});
 async function record(){
  if(recording)return;
  if(!recordingEnabled){if(!r.recordStart){r.recordStart=Date.now();r.recording={disabled:true};save();}return;}
  const file=path.join(out,'continuous-candidate.webm');fs.writeFileSync(file,Buffer.alloc(0));
  await p.exposeBinding('__backgroundRecordChunk',(_,s)=>{writes=writes.then(()=>fs.promises.appendFile(file,Buffer.from(s,'base64')));return writes;});
  const session=await c.newCDPSession(p);
  const result=await session.send('Runtime.evaluate',{userGesture:true,awaitPromise:true,returnByValue:true,expression:`(async()=>{const stream=await navigator.mediaDevices.getDisplayMedia({video:{width:{ideal:1280},height:{ideal:720},frameRate:{max:2}},audio:{suppressLocalAudioPlayback:true,echoCancellation:false,noiseSuppression:false,autoGainControl:false,channelCount:2},selfBrowserSurface:'include',systemAudio:'exclude',preferCurrentTab:true});const recorder=new MediaRecorder(stream,{mimeType:'video/webm;codecs=vp8,opus',videoBitsPerSecond:550000,audioBitsPerSecond:128000});let pending=Promise.resolve();recorder.ondataavailable=e=>{if(e.data.size)pending=pending.then(async()=>{const bytes=new Uint8Array(await e.data.arrayBuffer());let binary='';for(const byte of bytes)binary+=String.fromCharCode(byte);await window.__backgroundRecordChunk(btoa(binary));});};window.__stopBackgroundRecord=()=>new Promise(resolve=>{recorder.onstop=async()=>{await pending;stream.getTracks().forEach(t=>t.stop());resolve();};recorder.stop();});recorder.start(1000);return stream.getTracks().map(t=>({kind:t.kind,settings:t.getSettings()}));})()`});
  if(result.exceptionDetails)throw Error(result.exceptionDetails.exception?.description||result.exceptionDetails.text);
  recording={session,file};r.recordStart=Date.now();r.recording={file:path.basename(file),tracks:result.result.value,silentHost:true};save();
 }
 async function seal(){if(!recording)return;await p.evaluate(()=>window.__stopBackgroundRecord());await writes;await recording.session.detach();recording=null;r.sealedBeforeReload=true;save();}
 async function stableScroll(loc){for(let attempt=0;;attempt++){try{await loc.waitFor({state:'visible'});await loc.scrollIntoViewIfNeeded();return;}catch(e){if(attempt>=2||!/attached|detached/.test(String(e)))throw e;await p.waitForTimeout(250);}}}
 async function observe(label,loc,ms=900){await stableScroll(loc);await p.waitForTimeout(ms);r.actions.push({label,action:'observe',text:await loc.innerText(),seconds:stamp()});save();}
 async function act(label,loc,verify){await stableScroll(loc);const control=await loc.evaluate(e=>e.innerText||e.getAttribute('aria-label')||e.textContent||'');await loc.click();if(verify)await verify();await p.waitForTimeout(350);r.actions.push({label,action:'click',control,seconds:stamp(),status:verify?'PASS':'ACTIVATED'});save();}
 async function inventory(label,loc){r.inventory.push({label,seconds:stamp(),elements:await loc.locator('button,[role=button],a[href],summary,input,select').evaluateAll(es=>es.map(e=>({tag:e.tagName,text:(e.innerText||e.textContent||'').trim(),label:e.getAttribute('aria-label'),href:e.getAttribute('href'),disabled:e.disabled||false,visible:!!(e.offsetWidth||e.offsetHeight||e.getClientRects().length)})))});save();}
 async function enter(){await p.getByRole('button',{name:tr('Sağlık Merkezi'),exact:true}).click();await p.locator('#health-centre-links a[href="/'+module+'"]').click();await p.waitForURL('**/'+module);const d=p.getByRole('dialog');await d.waitFor();await observe('Actual service permissions',d);for(const cb of await d.getByRole('checkbox').all())await cb.check();await d.getByRole('button',{name:tr('İzin ver ve devam et'),exact:true}).click();await p.locator('[data-health-start]').waitFor();await observe('Existing English module entry',p.locator('[data-health-start]'));}
 async function close(error){
  if(error){r.error=String(error);r.current=await p.locator('body').innerText().catch(()=>null);await p.screenshot({path:path.join(out,'failure.png')}).catch(()=>{});}
  await Promise.allSettled(pending);r.nativeSpeechEvents=await p.evaluate(()=>window.__nativeSpeechEvents||[]);
  r.functionalStatus=error?'FAIL':r.result&&r.fullResultCoverage?'PASS':'INCOMPLETE';
  r.scope='Controlled WEB journey; broader acceptance is evaluated in the parity matrix.';
  if(recording){try{await p.evaluate(async()=>{for(const a of window.__taskAudioObjects||[])a.pause();for(const a of document.querySelectorAll('audio,video'))a.pause();await Promise.allSettled((window.__taskContexts||[]).filter(x=>x.state==='running').map(x=>x.suspend()));await window.__stopBackgroundRecord();});await writes;await recording.session.detach();}catch(e){r.recordingError=String(e);}}
  await p.screenshot({path:path.join(out,'ending.png')}).catch(()=>{});r.finished=new Date().toISOString();save();await c.close();await b.close();console.log(JSON.stringify({out,result:r.result,coverage:r.fullResultCoverage,status:r.functionalStatus,error:r.error}));
 }
 try{await p.goto(origin+'/');assert(await p.evaluate(async asset=>(await fetch(asset)).ok,'/_next/static/'+r.buildId+'/_buildManifest.js'));await p.locator('#attune-language').selectOption(language);await p.waitForFunction(()=>document.querySelector('[data-vehicle-status]')?.textContent==='PARK');await record();if(recordingEnabled)assert(r.recording.tracks.some(t=>t.kind==='audio'&&t.settings.suppressLocalAudioPlayback===true),'Local output suppression must be confirmed before any module is entered');}
 catch(e){await close(e);throw e;}
 return {p,q:p,r,out,save,stamp,tr,record,seal,enter,close,act,observe,inventory};
}
module.exports={open,root,fixtureRoot,tr,language};
