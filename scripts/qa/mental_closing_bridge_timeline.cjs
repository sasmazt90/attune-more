/**
 * Browser timeline of the Mental closing bridge on the active normal conversation path (not structured-v1).
 *
 * Real: a production Next build of this branch, Chromium's media pipeline playing the committed A/B/C WAVs, the
 * hook's finish()/closing code and its content-free 'attune-speech-timing' events, trusted (CDP) clicks.
 * Replayed, never live: every backend response. Each scenario names where its replayed responses came from
 * (`summary.source`, `tts[].row`) — synthetic fixtures or responses recorded earlier from a real provider/backend.
 * This is not a live end-to-end measurement.
 *
 * Before a scenario runs, each replayed speech response is checked against its recorded measurement: WAV present,
 * 24 kHz mono PCM16, duration equal to the measured audio, text hash, speaker profile and measurement label. During
 * the run the app's request text must equal the measured text, or the scenario fails.
 *
 * A scenario with mode 'live' replays nothing: the page talks to a running Next server and test API (real provider,
 * real TTS endpoint). Only the microphone is replaced, by recognition results carrying the scenario's synthetic
 * utterances. Live results record the response headers (TTS start/seconds, Server-Timing) and the analysis result.
 *
 * Usage: node scripts/qa/mental_closing_bridge_timeline.cjs <baseURL> <scenarios.json> <out.json> [autoplay]
 *   autoplay: default (no override) | user-gesture-required | no-user-gesture-required
 *   env: PLAYWRIGHT_MODULE (path of a playwright package), CHROME_PATH (browser executable), ONLY (one label)
 */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const [baseURL,scenarioFile,outFile,autoplay='default']=process.argv.slice(2);
const LOCALE={tr:'tr-TR',en:'en-US',de:'de-DE'};
const sha=text=>crypto.createHash('sha256').update(text).digest('hex');
const FIRST_PART_MIN_WORDS=6,words=t=>t.trim().split(/\s+/).filter(Boolean).length;
// Same rule as speechParts() in mentalNeuralSpeech.ts.
function speechParts(text){const s=text.trim().split(/(?<=[.!?…]["'”’)]?)\s+/).filter(Boolean);let at=1,first=s[0]||'';while(at<s.length&&words(first)<FIRST_PART_MIN_WORDS)first+=' '+s[at++];const rest=s.slice(at).join(' ');return rest?[first,rest]:[text];}

function wavInfo(file){
 const b=fs.readFileSync(file);
 if(b.toString('ascii',0,4)!=='RIFF'||b.toString('ascii',8,12)!=='WAVE')throw Error('NOT_WAVE '+file);
 let at=12,fmt=null,data=null;
 while(at+8<=b.length){const id=b.toString('ascii',at,at+4),size=b.readUInt32LE(at+4);if(id==='fmt ')fmt={channels:b.readUInt16LE(at+10),rate:b.readUInt32LE(at+12),bits:b.readUInt16LE(at+22)};if(id==='data')data=size;at+=8+size+(size%2);}
 return {...fmt,seconds:data/(fmt.rate*fmt.channels*fmt.bits/8),sha256:crypto.createHash('sha256').update(b).digest('hex'),bytes:b.length};
}

/** Automatic mapping checks; returns a list of problems (empty means the scenario may run). */
function validate(s,root){
 if(s.mode==='live')return Array.isArray(s.live?.utterances)&&s.live.utterances.length?[]:['live scenario without utterances'];
 const problems=[],expected=s.mode==='short'?[s.summary.spokenSummary]:speechParts(s.summary.summaryText);
 if(s.tts.length!==expected.length)problems.push(`expected ${expected.length} speech parts, scenario has ${s.tts.length}`);
 s.tts.forEach((t,i)=>{
  const file=path.resolve(root,t.wav);
  if(!fs.existsSync(file)){problems.push('missing WAV '+t.wav);return;}
  const w=wavInfo(file);t.wavInfo=w;
  if(w.rate!==24000||w.channels!==1||w.bits!==16)problems.push(`${t.wav}: not 24 kHz mono PCM16`);
  if(Math.abs(w.seconds-t.row.audioSeconds)>1/24000+1e-6)problems.push(`${t.wav}: ${w.seconds}s audio but measurement ${t.row.label} says ${t.row.audioSeconds}s`);
  if(t.row.sha256&&t.row.sha256!==w.sha256)problems.push(`${t.wav}: bytes differ from measurement ${t.row.label}`);
  if(t.text!==expected[i])problems.push(`part ${i}: text is not the app's part ${i}`);
  if(t.row.textSha256&&t.row.textSha256!==sha(t.text))problems.push(`part ${i}: text differs from measurement ${t.row.label}`);
  if(t.row.profile!=='female-calm-v1')problems.push(`part ${i}: measurement profile ${t.row.profile}`);
  if(!t.row.label||!t.row.runId)problems.push(`part ${i}: measurement label/run id missing`);
 });
 return problems;
}

async function run(s,root){
 const args=autoplay==='default'?[]:['--autoplay-policy='+autoplay];
 const browser=await chromium.launch({args,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})});
 const live=s.mode==='live',liveResponses=[];
 const page=await browser.newPage();
 const requests=[],mismatches=[];
 await page.addInitScript(({language,utterances})=>{
  localStorage.setItem('attune.language.v1',language);
  window.__timeline=[];
  window.addEventListener('attune-speech-timing',e=>window.__timeline.push({stage:e.detail.stage,atMs:e.detail.atMs}));
  // Recognition fixture: the first listen hears one synthetic sentence; later listens stay silent.
  const queue=[...utterances];
  window.SpeechRecognition=class{start(){setTimeout(()=>{this.onstart?.();const text=queue.shift();if(text)setTimeout(()=>this.onresult?.({resultIndex:0,results:[Object.assign([{transcript:text}],{isFinal:true})]}),200);},50);}abort(){}stop(){}};
 },{language:s.language,utterances:live?s.live.utterances:['Bu sentetik ve kişisel olmayan bir test cümlesidir.']});
 if(live){
  page.on('request',request=>{if(request.url().includes('/api/mental/analyze-session'))try{requests.push({kind:'analyze',at:Date.now(),spokenSummaryRequested:JSON.parse(request.postData()).spokenSummary===true});}catch{}});
  page.on('response',async response=>{
   const url=response.url();
   if(url.includes('/api/mental-neural-speech')){let profile=null;try{profile=JSON.parse(response.request().postData()).speakerProfile||null;}catch{}
    liveResponses.push({kind:'tts',at:Date.now(),status:response.status(),profile,start:response.headers()['x-tts-start']||null,seconds:response.headers()['x-tts-seconds']||null,serverTiming:response.headers()['server-timing']||null});}
   if(url.includes('/api/mental/analyze-session')){let body=null;try{body=await response.json();}catch{}
    liveResponses.push({kind:'analysis',at:Date.now(),status:response.status(),providerType:body?.providerType,summaryText:body?.summaryText,spokenSummary:body?.spokenSummary,spokenSummaryStatus:body?.spokenSummaryStatus});}
  });
 }
 if(!live){
 const json=(route,body,status=200)=>route.fulfill({status,contentType:'application/json',headers:{'Access-Control-Allow-Origin':'*'},body:JSON.stringify(body)});
 await page.route(/^http:\/\/(localhost|127\.0\.0\.1):8000\//,async route=>{
  const url=new URL(route.request().url());
  if(route.request().method()==='OPTIONS')return route.fulfill({status:204,headers:{'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'*','Access-Control-Allow-Methods':'*'}});
  if(url.pathname==='/api/vehicle/state')return json(route,{vehicleMoving:false,currentSpeed:0,vehicleParked:true,driverAuthenticated:true,lastUpdated:'2026-11-10T00:00:00'});
  if(url.pathname==='/api/mental/provider-status')return json(route,{apiKeyConfigured:true,providerName:'replay'});
  if(url.pathname==='/api/mental/converse')return json(route,{reply:{tr:'Anlıyorum.',en:'I understand.',de:'Ich verstehe.'}[s.language],providerType:'LIVE_OPENAI',isCrisis:false});
  if(url.pathname==='/api/mental/analyze-session'){
   const body=JSON.parse(route.request().postData());
   requests.push({kind:'analyze',at:Date.now(),spokenSummaryRequested:body.spokenSummary===true});
   await new Promise(r=>setTimeout(r,s.summary.delayMs));
   return json(route,{summaryText:s.summary.summaryText,themes:['work-life','sleep'],moodTrend:'STRESSED',professionalSupportSuggested:false,professionalSupportReason:null,providerType:'LIVE_OPENAI',
    ...(s.summary.spokenSummary!==undefined?{spokenSummary:s.summary.spokenSummary}:{})});
  }
  return json(route,{detail:'NOT_IN_REPLAY'},404);
 });
 const turnWav=fs.readFileSync(path.resolve(root,s.tts[0].wav));
 let part=0;
 await page.route('**/api/mental-neural-speech',async route=>{
  const body=JSON.parse(route.request().postData());
  if(!body.speakerProfile)return route.fulfill({status:200,headers:{'Content-Type':'audio/wav','X-TTS-Source':'chatterbox-multilingual-v3','X-TTS-Locale':LOCALE[s.language]},body:turnWav}); // ordinary turn, not measured
  const index=part++,t=s.tts[index];
  if(!t||body.text!==t.text||body.speakerProfile!=='female-calm-v1'){mismatches.push({index,requested:sha(body.text||''),expected:t&&sha(t.text)});return route.fulfill({status:503,body:'{}'});}
  requests.push({kind:'tts',index,at:Date.now(),delayMs:Math.round(t.delayMs),measurement:t.row.label});
  await new Promise(r=>setTimeout(r,t.delayMs));
  return route.fulfill({status:200,headers:{'Content-Type':'audio/wav','X-TTS-Source':'chatterbox-multilingual-v3','X-TTS-Locale':LOCALE[s.language],'X-TTS-Speaker-Profile':'female-calm-v1'},body:fs.readFileSync(path.resolve(root,t.wav))});
 });
 }
 await page.goto(baseURL+'/mental');
 const boxes=page.locator('input[type=checkbox]');await boxes.first().waitFor();
 for(let i=0;i<3;i++)await boxes.nth(i).check();
 await page.getByRole('button').filter({hasText:/İzin ver ve devam et|Allow and continue|Erlauben und fortfahren/}).first().click();
 const start=page.getByRole('button').filter({hasText:/Görüşmeyi Başlat|Start conversation|Gespräch starten/}).first();
 await page.waitForFunction(()=>![...document.querySelectorAll('button')].find(b=>/Görüşmeyi Başlat|Start conversation|Gespräch starten/.test(b.textContent))?.disabled,null,{timeout:20000});
 await start.click();
 // The ordinary reply may need a tap under a strict policy; tap it like a user would.
 const taps=[];
 const tapper=setInterval(async()=>{try{const b=page.locator('[data-neural-play-response]');if(await b.count()&&await b.first().isEnabled()){taps.push({at:Date.now(),phase:await page.evaluate(()=>document.querySelector('[data-conversation-phase]')?.getAttribute('data-conversation-phase'))});await b.first().click();}}catch{}},250);
 try{
  await page.waitForFunction(()=>window.__timeline.some(e=>e.stage==='ended'),null,{timeout:live?150000:60000});
  await page.waitForFunction(()=>document.querySelector('[data-conversation-phase]')?.getAttribute('data-conversation-phase')==='listening',null,{timeout:30000});
  const previewSeen=page.locator('[data-closing-preview]').first().waitFor({timeout:15000}).then(()=>true,()=>false);
  await page.getByRole('button').filter({hasText:/Görüşmeyi Bitir|End conversation|Gespräch beenden/}).first().click();
  await page.waitForFunction(()=>document.querySelector('[data-conversation-phase]')?.getAttribute('data-conversation-phase')==='completed',null,{timeout:180000});
  await page.waitForTimeout(300);
  const events=await page.evaluate(()=>window.__timeline);
  const notice=await page.evaluate(()=>[...document.querySelectorAll('[role=status]')].map(n=>n.textContent).join(' | '));
  const t0=events.find(e=>e.stage==='closing-trigger').atMs;
  const first=st=>{const e=events.find(x=>x.stage===st&&x.atMs>=t0);return e?Math.round(e.atMs-t0):null;};
  const all=st=>events.filter(x=>x.stage===st&&x.atMs>=t0).map(e=>Math.round(e.atMs-t0));
  const m={aPlaying:first('closing-A-playing'),aEnded:first('closing-A-ended'),bPlaying:first('closing-B-playing'),bEnded:first('closing-B-ended'),
   cPlaying:first('closing-C-playing'),cEnded:first('closing-C-ended'),contextStart:first('closing-context-start'),contextEnd:first('closing-context-end'),
   summaryRequest:first('closing-summary-request'),summaryResponse:first('closing-summary-response'),summaryTextReady:first('closing-summary-text-ready'),
   noSpokenLine:first('closing-summary-no-spoken-line'),ttsRequest0:first('closing-summary-segment-request-0'),firstPartReady:first('closing-summary-first-ready'),
   summaryPlaying:first('closing-summary-audio-start'),summaryComplete:first('closing-summary-complete'),partPlaying:all('closing-summary-playing'),partEnded:all('closing-summary-ended'),
   gestureRequired:all('closing-A-gesture-required').concat(all('closing-B-gesture-required'),all('closing-C-gesture-required'),all('closing-summary-gesture-required')).length};
  const closingTaps=taps.filter(t=>t.phase==='ending').length;
  const result={label:s.label,language:s.language,mode:s.mode,autoplay,finalPhase:'completed',previewLabelShown:await previewSeen,notice,
   sources:live?{summary:'live: test API -> real provider',tts:'live: Next route -> test API -> resident worker'}:{summary:s.summary.source,tts:s.tts.map(t=>t.row.label+' ('+t.row.source+')')},mismatches,liveResponses,
   spokenSummaryRequested:requests.find(r=>r.kind==='analyze')?.spokenSummaryRequested,
   spokenText:live?(liveResponses.find(r=>r.kind==='analysis')?.spokenSummary??null):s.mode==='short'?s.summary.spokenSummary:s.summary.summaryText,
   spokenWords:live?words(liveResponses.find(r=>r.kind==='analysis')?.spokenSummary||''):words(s.mode==='short'?(s.summary.spokenSummary||''):s.summary.summaryText),
   msFromTrigger:{firstPreparedAudio:m.aPlaying,summaryTextReady:m.summaryTextReady??m.summaryResponse,firstDynamicPartReady:m.firstPartReady,cEnded:m.cEnded,
    firstPersonalizedAudio:m.summaryPlaying,closingAudioEnd:m.summaryComplete??m.cEnded},
   durationsMs:{summaryRequest:m.summaryResponse!==null&&m.summaryRequest!==null?m.summaryResponse-m.summaryRequest:null,
    dynamicSpeechPreparation:m.firstPartReady!==null&&m.ttsRequest0!==null?m.firstPartReady-m.ttsRequest0:null},
   gapsMs:{aToB:m.bPlaying-m.aEnded,bToC:m.cPlaying-m.bEnded,cToSummary:m.summaryPlaying!==null?m.summaryPlaying-m.cEnded:null,
    summaryParts:m.partPlaying.slice(1).map((p,i)=>p-m.partEnded[i]),overlap:m.summaryPlaying!==null&&m.summaryPlaying<m.cEnded},
   userTaps:{total:taps.length,duringClosing:closingTaps},gestureRequiredEvents:m.gestureRequired,
   marks:m,fixtureRequests:requests,events:events.filter(e=>e.atMs>=t0).map(e=>({stage:e.stage,ms:Math.round(e.atMs-t0)}))};
  return result;
 }finally{clearInterval(tapper);await browser.close();}
}

(async()=>{
 const spec=JSON.parse(fs.readFileSync(scenarioFile,'utf8')),root=path.dirname(path.resolve(scenarioFile));
 const results=[];
 for(const s of spec.scenarios.filter(x=>!process.env.ONLY||x.label===process.env.ONLY)){
  const problems=validate(s,root);
  if(problems.length){results.push({label:s.label,valid:false,problems});console.log(JSON.stringify({label:s.label,valid:false,problems}));continue;}
  const r=await run(s,root);r.valid=r.mismatches.length===0;results.push(r);
  console.log(JSON.stringify({label:r.label,valid:r.valid,autoplay,ms:r.msFromTrigger,gaps:r.gapsMs,taps:r.userTaps}));
 }
 fs.writeFileSync(outFile,JSON.stringify({schema:'attune-mental-closing-bridge-browser-timeline-v2',
  kind:'Real production build + Chromium playback + real hook code + trusted CDP clicks; every backend response replayed (see sources). Not a live end-to-end run.',
  autoplayPolicy:autoplay,scenarioFile:path.basename(scenarioFile),description:spec.description,results},null,2)+'\n');
})().catch(error=>{console.error(error);process.exitCode=1;});
