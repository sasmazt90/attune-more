/**
 * Browser timeline of the Mental closing bridge on the active normal conversation path (not structured-v1).
 *
 * Real: the production Next build with NEXT_PUBLIC_MENTAL_CLOSING_BRIDGE=technical-preview, Chromium's media
 * pipeline playing the committed A/B/C WAV files, the hook's real finish()/closing code and its content-free
 * 'attune-speech-timing' events.
 * Synthetic (labelled in the output): every backend response. The vehicle is parked, the conversation turn and
 * the summary come from fixtures (no provider call), and /api/mental-neural-speech answers with WAV parts the
 * speech host produced for a synthetic summary, after the delay measured on that host for the same request.
 *
 * Usage: node scripts/qa/mental_closing_bridge_timeline.cjs <baseURL> <latency-dir> <out.json>
 */
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path');
const [baseURL,latencyDir,outFile]=process.argv.slice(2);
const latency=JSON.parse(fs.readFileSync(path.join(latencyDir,'latency.json'),'utf8'));
const verify=Object.fromEntries(latency.perRequestVerifySeconds.map(r=>[r.language,r.seconds]));
const row=label=>latency.rows.find(r=>r.label===label);
const SUMMARY={tr:latency.summaries.tr,en:latency.summaries.en,de:latency.summaries.de};
const LOCALE={tr:'tr-TR',en:'en-US',de:'de-DE'};
const turnWav=fs.readFileSync(path.join(latencyDir,'en-part0.wav')); // any valid PCM; normal turns are not measured here

async function run(scenario){
 const {language,summaryDelayMs,first,second}=scenario;
 const browser=await chromium.launch({args:['--autoplay-policy=no-user-gesture-required']});
 const page=await browser.newPage();
 const step=m=>{if(process.env.DEBUG)console.error('[step]',scenario.label,m);};
 if(process.env.DEBUG)page.on('console',m=>console.error('[console]',m.type(),m.text().slice(0,200)));
 const requests=[];
 await page.addInitScript(({language})=>{
  localStorage.setItem('attune.language.v1',language);
  window.__timeline=[];
  window.addEventListener('attune-speech-timing',e=>window.__timeline.push({stage:e.detail.stage,atMs:e.detail.atMs}));
  // Recognition fixture: the first listen hears one synthetic sentence; later listens stay silent.
  let heard=false;
  window.SpeechRecognition=class{start(){setTimeout(()=>{this.onstart?.();if(!heard){heard=true;setTimeout(()=>this.onresult?.({resultIndex:0,results:[Object.assign([{transcript:'Bu sentetik ve kişisel olmayan bir test cümlesidir.'}],{isFinal:true})]}),200);}},50);}abort(){}stop(){}};
 },{language});
 const json=(route,body,status=200)=>route.fulfill({status,contentType:'application/json',headers:{'Access-Control-Allow-Origin':'*'},body:JSON.stringify(body)});
 const at=()=>Date.now();
 await page.route(/^http:\/\/(localhost|127\.0\.0\.1):8000\//,async route=>{
  const url=new URL(route.request().url());
  if(route.request().method()==='OPTIONS')return route.fulfill({status:204,headers:{'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'*','Access-Control-Allow-Methods':'*'}});
  if(url.pathname==='/api/vehicle/state')return json(route,{vehicleMoving:false,currentSpeed:0,vehicleParked:true,driverAuthenticated:true,lastUpdated:'2026-11-09T00:00:00'});
  if(url.pathname==='/api/mental/provider-status')return json(route,{apiKeyConfigured:true,providerName:'Synthetic fixture'});
  if(url.pathname==='/api/mental/converse')return json(route,{reply:{tr:'Anlıyorum.',en:'I understand.',de:'Ich verstehe.'}[language],providerType:'LIVE_OPENAI',isCrisis:false});
  if(url.pathname==='/api/mental/analyze-session'){
   requests.push({kind:'analyze',at:at()});await new Promise(r=>setTimeout(r,summaryDelayMs));
   return json(route,{summaryText:SUMMARY[language],themes:['work-life','sleep'],moodTrend:'STRESSED',professionalSupportSuggested:false,professionalSupportReason:null,providerType:'LIVE_OPENAI'});
  }
  return json(route,{detail:'NOT_IN_FIXTURE'},404);
 });
 let part=0;
 await page.route('**/api/mental-neural-speech',async route=>{
  const body=JSON.parse(route.request().postData());
  if(!body.speakerProfile){ // ordinary turn (official-default); not part of this measurement
   return route.fulfill({status:200,headers:{'Content-Type':'audio/wav','X-TTS-Source':'chatterbox-multilingual-v3','X-TTS-Locale':LOCALE[language]},body:turnWav});
  }
  const index=part++,measured=index===0?first:second;
  requests.push({kind:'tts',index,at:at(),delayMs:Math.round(measured.delayMs)});
  await new Promise(r=>setTimeout(r,measured.delayMs));
  return route.fulfill({status:200,headers:{'Content-Type':'audio/wav','X-TTS-Source':'chatterbox-multilingual-v3','X-TTS-Locale':LOCALE[language],'X-TTS-Speaker-Profile':'female-calm-v1'},body:fs.readFileSync(path.join(latencyDir,measured.file))});
 });
 await page.goto(baseURL+'/mental');
 // The real service-consent dialog: the three required permissions, not the optional history permission.
 const boxes=page.locator('input[type=checkbox]');await boxes.first().waitFor();
 for(let i=0;i<3;i++)await boxes.nth(i).check();
 await page.getByRole('button').filter({hasText:/İzin ver ve devam et|Allow and continue|Erlauben und fortfahren/}).first().click();
 const start=page.getByRole('button').filter({hasText:/Görüşmeyi Başlat|Start conversation|Gespräch starten/}).first();
 await start.waitFor();await page.waitForFunction(()=>![...document.querySelectorAll('button')].find(b=>/Görüşmeyi Başlat|Start conversation|Gespräch starten/.test(b.textContent))?.disabled,null,{timeout:20000});
 step('start');await start.click();
 // Wait until the synthetic turn was answered and listening resumed, then end the conversation.
 await page.waitForFunction(()=>window.__timeline.some(e=>e.stage==='ended'),null,{timeout:30000});
 await page.waitForFunction(()=>document.querySelector('[data-conversation-phase]')?.getAttribute('data-conversation-phase')==='listening',null,{timeout:30000});
 step('turn answered');
 const finish=page.getByRole('button').filter({hasText:/Görüşmeyi Bitir|End conversation|Gespräch beenden/}).first();
 const previewSeen=page.locator('[data-closing-preview]').first().waitFor({timeout:15000}).then(()=>true,()=>false);
 step('finish');await finish.click();
 await page.waitForFunction(()=>document.querySelector('[data-conversation-phase]')?.getAttribute('data-conversation-phase')==='completed'||window.__timeline.some(e=>e.stage==='closing-summary-complete'),null,{timeout:120000});
 await page.waitForTimeout(300);
 const events=await page.evaluate(()=>window.__timeline);
 const states=await page.evaluate(()=>document.querySelector('[data-conversation-phase]')?.getAttribute('data-conversation-phase'));
 await browser.close();
 const t0=events.find(e=>e.stage==='closing-trigger').atMs;
 const first_=s=>{const e=events.find(x=>x.stage===s&&x.atMs>=t0);return e?Math.round(e.atMs-t0):null;};
 const all=s=>events.filter(x=>x.stage===s&&x.atMs>=t0).map(e=>Math.round(e.atMs-t0));
 const marks={trigger:0,bridgeVerified:first_('closing-bridge-verified'),aPlaying:first_('closing-A-playing'),aEnded:first_('closing-A-ended'),
  bPlaying:first_('closing-B-playing'),bEnded:first_('closing-B-ended'),cPlaying:first_('closing-C-playing'),cEnded:first_('closing-C-ended'),
  contextStart:first_('closing-context-start'),contextEnd:first_('closing-context-end'),summaryRequest:first_('closing-summary-request'),
  summaryResponse:first_('closing-summary-response'),summaryTextReady:first_('closing-summary-text-ready'),
  ttsRequest0:first_('closing-summary-segment-request-0'),firstPartReady:first_('closing-summary-first-ready'),
  summaryPlaying:first_('closing-summary-audio-start'),summaryComplete:first_('closing-summary-complete'),summaryPartPlaying:all('closing-summary-playing'),summaryPartEnded:all('closing-summary-ended'),
  ttsRequest1:first_('closing-summary-segment-request-1'),secondPartReady:first_('closing-summary-segment-ready-1')};
 const gaps={aToB:marks.bPlaying-marks.aEnded,bToC:marks.cPlaying-marks.bEnded,cToSummary:marks.summaryPlaying-marks.cEnded,
  summaryPart0ToPart1:marks.summaryPartPlaying.length>1&&marks.summaryPartEnded.length?marks.summaryPartPlaying[1]-marks.summaryPartEnded[0]:null,
  overlapDetected:marks.summaryPlaying!==null&&marks.summaryPlaying<marks.cEnded};
 return {scenario,finalPhase:states,previewLabelShown:await previewSeen,marks,gapsMs:gaps,
  firstPreparedAudioMs:marks.aPlaying,firstPersonalizedAudioMs:marks.summaryPlaying,
  totalClosingAudioMs:marks.summaryComplete,fixtureRequests:requests,events:events.filter(e=>e.atMs>=t0).map(e=>({stage:e.stage,ms:Math.round(e.atMs-t0)}))};
}

(async()=>{
 const scenarios=[];
 for(const language of ['tr','en','de']){
  const p0=row(language+'-part0'),p1=row(language+'-part1'),warm0=row(language+'-part0-repeat');
  // The product verifies the female bundle on every request before synthesis; that cost is part of each delay.
  // Only the probe's first female request (TR part 0) loaded the female model ('cold'); EN/DE part 0 ran warm.
  const sample={delayMs:(verify[language]+p0.seconds)*1000,file:language+'-part0.wav',source:language+'-part0 ('+p0.start+')',start:p0.start};
  const repeat={delayMs:(verify[language]+warm0.seconds)*1000,file:language+'-part0.wav',source:language+'-part0-repeat ('+warm0.start+')',start:warm0.start};
  const second={delayMs:(verify[language]+p1.seconds)*1000,file:language+'-part1.wav',source:language+'-part1 ('+p1.start+')'};
  scenarios.push({language,label:language+'-warm-repeat-summary3s',summaryDelayMs:3000,first:repeat,second});
  scenarios.push({language,label:language+(p0.start==='cold'?'-firstFemaleAfterBoot':'-warm-sample1')+'-summary3s',summaryDelayMs:3000,first:sample,second});
 }
 scenarios.push({language:'tr',label:'tr-warm-repeat-summary12s',summaryDelayMs:12000,first:{...scenarios[0].first},second:{...scenarios[0].second}});
 const results=[];
 for(const scenario of scenarios.filter(s=>!process.env.ONLY||s.label===process.env.ONLY)){results.push(await run(scenario));console.log(JSON.stringify({label:scenario.label,gaps:results.at(-1).gapsMs,firstPrepared:results.at(-1).firstPreparedAudioMs,firstPersonalized:results.at(-1).firstPersonalizedAudioMs,total:results.at(-1).totalClosingAudioMs}));}
 fs.writeFileSync(outFile,JSON.stringify({
  schema:'attune-mental-closing-bridge-browser-timeline-v1',
  kind:'Real production build, real Chromium media playback of committed WAVs, real hook/closing code; synthetic backend fixtures (no provider call). Speech responses replay host-measured delays and host-generated WAV parts for a synthetic summary.',
  realProviderCalls:0,structuredMode:false,bridgeMode:'technical-preview',
  summaryLatencyAssumptionMs:'3000 (and 12000 in one TR case); not measured against a live provider',
  hostMeasurement:{threads:latency.threads,perRequestVerifySeconds:latency.perRequestVerifySeconds},
  results},null,2)+'\n');
})().catch(error=>{console.error(error);process.exitCode=1;});
