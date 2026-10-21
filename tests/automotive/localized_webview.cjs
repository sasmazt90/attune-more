'use strict';
// Finite real-WebView acceptance helpers. No native media grants, provider
// calls, test hooks in the product, or fabricated playback events.
const path = require('node:path');
const {execFileSync} = require('node:child_process');
const {createHash} = require('node:crypto');
const LANGUAGES = new Set(['tr', 'en', 'de']);
const MODULE_EVENTS = {skin:'guidance:skin-neutral', dental:'guidance:dental-front',
  vision:'vision:next1', hearing:'guidance:hearing-tone', mental:'guidance:mental-entry'};
// Comparable short utterances exercise real synthesis; long-form CPU capacity
// is not established by this bounded acceptance. Interruptions reuse the WAV.
const NEURAL_TEXT = {tr:'Bu yeni ve kişisel olmayan örnekte 1287 sayısı var.',
  en:'Hello, this new and nonpersonal audio example includes the number 1287.',
  de:'Dieses neue, nichtpersönliche Beispiel enthält die Zahl 1287.'};
const NATIVE_PARK = {tr:'PARK doğrulandı', en:'PARK verified', de:'PARK bestätigt'};
let bundle;
let generatedEnglish;
function validate(language, moduleName) {
  if (!LANGUAGES.has(language)) throw Error('Language outside finite acceptance list');
  if (moduleName !== undefined && !Object.hasOwn(MODULE_EVENTS, moduleName)) throw Error('Module outside finite acceptance list');
}
async function inject(page) {
  if (!bundle) bundle = execFileSync(process.execPath,
    [path.join(__dirname,'../localization/approved_audio_bundle.cjs')], {encoding:'utf8', maxBuffer:8*1024*1024});
  if (!await page.evaluate(() => !!window.ApprovedAudioQA)) await page.addScriptTag({content:bundle});
}
async function language(page, value) {
  validate(value);
  const selector = page.locator('#attune-language');
  if (await selector.isDisabled()) throw Error('Language selector locked; no safety override is permitted');
  await selector.selectOption(value);
  await page.waitForFunction(value => document.documentElement.lang === value, value);
  // Settle React's deliberate old-language cancellation before a new utterance.
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  return {language:value, locale:await page.evaluate(() => document.documentElement.lang)};
}
async function recording(page, languageValue, moduleName) {
  validate(languageValue,moduleName);await inject(page);
  if (await page.locator('#attune-language').inputValue() !== languageValue) throw Error('Actual selected language differs');
  // Trusted interaction satisfies WebView's unchanged media user-gesture rule.
  await page.locator('h1').first().click();
  return page.evaluate(async ({languageValue,moduleName,event}) => {
    window.dispatchEvent(new Event('attune-guidance-cancel'));
    const q=window.ApprovedAudioQA,clip=q.audio.approvedClip(languageValue,moduleName,event),events=[];
    if(!clip)throw Error('Selected approved recording missing');
    const female=['skin','mental'].includes(moduleName);
    const expectedProfile={tr:female?'emel':'ahmet',en:female?'ada':'andrew',de:female?'katja':'stefan'}[languageValue];
    if(clip.voiceProfile!==expectedProfile||clip.mimeType!=='audio/mp4')throw Error('Module voice or original MIME differs from approved policy');
    const audio=new Audio();
    const played=await q.playback.playFixedSpeech(audio,clip,new AbortController().signal,
      ()=>document.documentElement.lang===languageValue,stage=>events.push(stage),true);
    return {language:languageValue,module:moduleName,event,recordingId:clip.recordingId,voice:clip.voice,
      voiceProfile:clip.voiceProfile,applicationLocale:clip.applicationLocale,voiceLocale:clip.voiceLocale,mime:clip.mimeType,
      status:played&&events.includes('playing')&&events.includes('ended')?'PASS':'FAIL',events};
  },{languageValue,moduleName,event:MODULE_EVENTS[moduleName]});
}
async function decode(page) {
  await inject(page);
  return page.evaluate(async()=>{
    const context=new AudioContext(),rows=[];
    try{
      for(const clip of window.ApprovedAudioQA.audio.approvedAudio.recordings){
        try {
          const r=await fetch(clip.url),bytes=await r.arrayBuffer();
          const hash=[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(v=>v.toString(16).padStart(2,'0')).join('');
          const pcm=await context.decodeAudioData(bytes.slice(0));
          rows.push({id:clip.recordingId,sha256:hash,bytes:bytes.byteLength,duration:pcm.duration,
            channels:pcm.numberOfChannels,sampleRate:pcm.sampleRate,
            status:r.ok&&bytes.byteLength===clip.bytes&&hash===clip.sha256&&pcm.duration>0?'PASS':'FAIL'});
        } catch(error) { rows.push({id:clip.recordingId,status:'FAIL',error:String(error)}); }
      }
    }finally{await context.close();}
    // Return failures too, so Python preserves every actual codec observation.
    return rows;
  });
}
async function neural(page, value) {
  validate(value);await inject(page);
  if(value==='en')generatedEnglish=undefined;
  const statuses=[],responseBodies=[],responseTimings=[],requestStartedAtUnixMs=Date.now();
  const observe=response=>{if(new URL(response.url()).pathname==='/api/mental-neural-speech'){
    statuses.push(response.status());responseTimings.push({status:response.status(),milliseconds:Date.now()-requestStartedAtUnixMs});
    // Read immediately, before playback/other requests can evict CDP's body.
    // Keep a settled outcome so observation errors cannot become unhandled.
    if(response.status()===200)responseBodies.push(response.body().then(bytes=>({bytes}),()=>({unavailable:true})));
  }};
  page.on('response',observe);
  try {
    await page.evaluate(({language,text})=>{
      const q=window.ApprovedAudioQA;
      if(q.core.getLanguage()!==language)throw Error('Selected locale differs');
      if(q.neural.mentalSpeechEngine()!=='chatterbox-v3')throw Error('Explicit fallback selected; do not overwrite owner preference');
      const started=performance.now(),row=window.attuneNeuralQA={starts:0,stages:[],gestureRequested:false,result:null};
      q.neural.mentalNeuralSpeech(text,new AbortController().signal,()=>q.core.getLanguage()===language,()=>row.starts++,()=>{},{
        observe:stage=>row.stages.push({stage,milliseconds:performance.now()-started}),
        // This observer runs outside the microphone conversation. Use the same
        // production callback contract and a visible, trusted user action.
        requestGesture:play=>{
          row.gestureRequested=true;
          const button=document.createElement('button');button.dataset.aaosNeuralPlay='';
          button.textContent=q.core.translateText('Sesli yanıtı oynat');
          button.style.cssText='position:fixed;bottom:20px;left:20px;z-index:9999;padding:20px;background:white;color:black';
          button.onclick=()=>play();document.body.append(button);
          return()=>button.remove();
        },
      }).then(played=>{row.result={language,played,starts:row.starts,stages:row.stages,gestureRequested:row.gestureRequested,milliseconds:performance.now()-started,format:'audio/wav',realModelClaimed:false};});
    },{language:value,text:NEURAL_TEXT[value]});
    await page.waitForFunction(()=>attuneNeuralQA.result||attuneNeuralQA.gestureRequested,null,{timeout:200000});
    if(!await page.evaluate(()=>!!attuneNeuralQA.result))await page.locator('[data-aaos-neural-play]').click();
    await page.waitForFunction(()=>!!attuneNeuralQA.result,null,{timeout:75000});
    const result=await page.evaluate(()=>attuneNeuralQA.result);
    if(value==='en'&&result.played){
      const retained=responseBodies.length?await responseBodies[0]:null;
      if(!retained?.bytes)return {...result,requestStartedAtUnixMs,responseTimings,httpStatuses:statuses,status:'BLOCKED',evidenceError:'Current-run neural response bytes unavailable; interruption checks cannot proceed'};
      const bytes=retained.bytes;
      if(bytes.length<=44||bytes.length>8*1024*1024||bytes.toString('ascii',0,4)!=='RIFF'||bytes.toString('ascii',8,12)!=='WAVE')throw Error('Invalid actual neural WAV');
      generatedEnglish={bytes,sha256:createHash('sha256').update(bytes).digest('hex')};
    }
    return {...result,requestStartedAtUnixMs,responseTimings,httpStatuses:statuses,status:result.played&&result.starts===1?'PASS':statuses.some(s=>[401,403,429,503,504].includes(s))?'BLOCKED':'FAIL',
      meaning:'Actual backend transport/playback attempt. Model/profile readiness and naturalness require separately verified inference evidence.'};
  }finally{page.off('response',observe);}
}
// Actual current-run neural bytes, reused through the application's shared WAV
// lifecycle. No fetch replacement, fabricated media events or new synthesis.
async function activeStart(page,mode){
  if(!['mute','cancel','consent','language','session','motion'].includes(mode))throw Error('Unknown finite interruption');
  if(!generatedEnglish)throw Error('BLOCKED: no current-run real English neural WAV');
  await inject(page);await language(page,'en');
  await page.locator('h1').first().click();
  await page.evaluate(({b64,mode,sha256})=>{
    const q=window.ApprovedAudioQA;
    if(!q.consent.serviceAllowed('mental'))throw Error('Explicit synthetic Mental consent missing');
    q.meter.setSpeechMuted(false);
    window.dispatchEvent(new Event('attune-guidance-cancel'));
    const audio=new Audio(),controller=new AbortController(),language=q.core.getLanguage(),path=location.pathname;
    // Keep actual, unchanged neural bytes active while native UI/probe calls run.
    // Only the motion observation loops; no policy, timing gate or audio event is mocked.
    audio.loop=mode==='motion';
    const row=window.attuneActiveQA={audio,controller,mode,sha256,events:[],done:false,played:null,startedAt:null};
    const bytes=Uint8Array.from(atob(b64),v=>v.charCodeAt(0));
    q.playback.playAudioBytes(audio,bytes.buffer,'audio/wav',60,controller.signal,
      ()=>q.consent.serviceAllowed('mental')&&q.core.getLanguage()===language&&location.pathname===path,
      stage=>{row.events.push({stage,at:performance.now()});if(stage==='playing')row.startedAt=performance.now();},true)
      .then(played=>{row.played=played;row.done=true;row.stoppedAt=performance.now();});
  },{b64:generatedEnglish.bytes.toString('base64'),mode,sha256:generatedEnglish.sha256});
  await page.waitForFunction(()=>window.attuneActiveQA?.startedAt!==null&&!window.attuneActiveQA.audio.paused&&!window.attuneActiveQA.done,null,{timeout:10000});
  return page.evaluate(()=>{const r=attuneActiveQA;if(r.audio.duration-r.audio.currentTime<3)throw Error('Insufficient active neural output window for transition evidence');return {mode:r.mode,sha256:r.sha256,active:true,duration:r.audio.duration,remaining:r.audio.duration-r.audio.currentTime,observedAtUnixMs:Date.now(),loopedForMotionObservation:r.audio.loop,source:'current-run-real-neural-response',pipeline:'production playAudioBytes',humanListening:false};});
}
async function activeInterrupt(page,mode,navigate){
  const active=await activeStart(page,mode);
  if(mode==='language')await language(page,'de');
  else if(mode==='session')await navigate(page,'/mental'); // Real SPA unmount/navigation.
  else await page.evaluate(mode=>{
    const q=window.ApprovedAudioQA,row=window.attuneActiveQA;
    if(mode==='mute'){q.meter.setSpeechMuted(true);window.dispatchEvent(new Event('attune-guidance-muted'));}
    if(mode==='cancel')row.controller.abort();
    if(mode==='consent')q.consent.setServiceConsent('mental',null);
  },mode);
  await page.waitForFunction(()=>window.attuneActiveQA?.done,null,{timeout:5000});
  const stopped=await page.evaluate(()=>{const r=attuneActiveQA;return {played:r.played,paused:r.audio.paused,sourceCleared:!r.audio.getAttribute('src'),events:r.events,startedAt:r.startedAt,stoppedAt:r.stoppedAt};});
  // Restore conditions, then observe beyond the scheduler polling interval.
  await page.evaluate(()=>{const q=ApprovedAudioQA;q.meter.setSpeechMuted(false);window.dispatchEvent(new Event('attune-guidance-muted'));});
  if(mode==='language')await language(page,'en');
  // Consent is renewed only by the ordinary explicit UI gate on the next visit.
  await page.evaluate(()=>new Promise(resolve=>setTimeout(resolve,1500)));
  const after=await page.evaluate(()=>{const r=attuneActiveQA;return {paused:r.audio.paused,sourceCleared:!r.audio.getAttribute('src'),starts:r.events.filter(e=>e.stage==='playing').length};});
  return {...active,...stopped,after,status:stopped.played===false&&stopped.paused&&stopped.sourceCleared&&after.paused&&after.sourceCleared&&after.starts===1?'PASS':'FAIL',
    boundary:'Shared production WAV output with consent/locale/route validity; full microphone/LLM conversation is not exercised'};
}

async function hearing(page,value){
  validate(value);await inject(page);
  const requests=[],row={language:value,status:'FAIL',syntheticReplies:true,humanHearingAcceptance:false,clinicalValidation:false};
  const observe=r=>{const p=new URL(r.url()).pathname;if(p.startsWith('/audio/hearing-'))requests.push({path:p,status:r.status()});};
  page.on('response',observe);
  const label=source=>page.evaluate(source=>ApprovedAudioQA.core.translateText(source),source);
  const button=async source=>page.getByRole('button',{name:await label(source),exact:true});
  try{
    if(await page.locator('#attune-language').inputValue()!==value)throw Error('Selected Hearing locale differs');
    const previousID=await page.evaluate(()=>JSON.parse(localStorage.getItem('attune_hearing_latest_v1')||'null')?.id||null);
    // Observe real PCM starts/end events without changing data, playback, time or scoring.
    await page.evaluate(()=>{
      window.attuneHearingQA={pcm:[],seed:8102026};
      const original=crypto.getRandomValues.bind(crypto);window.attuneRestoreRandom=()=>{crypto.getRandomValues=original;};
      crypto.getRandomValues=function(a){if(a instanceof Uint32Array&&a.length===1){a[0]=8102026;return a;}return original(a);};
      const start=AudioBufferSourceNode.prototype.start;
      window.attuneRestorePCM=()=>{AudioBufferSourceNode.prototype.start=start;};
      AudioBufferSourceNode.prototype.start=function(...args){
        const b=this.buffer;if(b){const r={frames:b.length,rate:b.sampleRate,channels:b.numberOfChannels,ended:false};attuneHearingQA.pcm.push(r);this.addEventListener('ended',()=>{r.ended=true;});}
        return start.apply(this,args);
      };
    });
    await (await button('Ses hazırlığını başlat')).click();
    await page.waitForFunction(()=>[...document.querySelectorAll('[data-hearing-page] button')].some(b=>!b.disabled&&b.textContent===ApprovedAudioQA.core.translateText('Sol kanalı dinle')),null,{timeout:40000});
    await page.evaluate(()=>attuneRestoreRandom());
    for(const [source,confirm] of [['Sol kanalı dinle','Yalnız sol kulağımda duydum.'],['Sağ kanalı dinle','Yalnız sağ kulağımda duydum.']]){
      const check=page.getByLabel(await label(confirm),{exact:true});
      if(!await check.isDisabled())throw Error('Channel confirmation admitted before real playback');
      await (await button(source)).click();
      await check.check({timeout:10000});
    }
    await (await button(value==='tr'?'Gürültüde Türkçe sayılar':'Gürültüde seçilen dilin sayıları')).click();
    const answer=page.getByRole('textbox',{name:await label('Üç sayı yanıtı'),exact:true});
    let seed=8102026;const random=()=>{seed=(1664525*seed+1013904223)>>>0;return seed/4294967296;};
    const replies=[];
    for(let i=0;i<24;i++){
      const digits=Array.from({length:3},()=>Math.floor(random()*10));random();
      const response=i%2?digits.map(d=>(d+1)%10):digits;
      await answer.fill(response.join(''),{timeout:40000});
      const progress=await page.locator('[data-din-progress] [role=progressbar]').getAttribute('aria-valuenow');
      if(Number(progress)!==i)throw Error('Scored progress differs from actual UI submission');
      replies.push({digits,response});await (await button('Yanıtı Gönder')).click();
    }
    await page.locator('[data-hearing-result]').waitFor({state:'visible',timeout:10000});
    await page.waitForFunction(({value,previousID})=>{const r=JSON.parse(localStorage.getItem('attune_hearing_latest_v1')||'null');return r?.language===value&&r.id!==previousID;},{value,previousID},{timeout:10000});
    const result=await page.evaluate(()=>JSON.parse(localStorage.getItem('attune_hearing_latest_v1')));
    const prefix=value==='tr'?'/audio/hearing-bank/':`/audio/hearing-approved-derived-20261021-v1/${value}/`;
    if(requests.length<12||requests.some(r=>r.status!==200||!r.path.startsWith(prefix)))throw Error('Wrong or unavailable selected-language bank');
    const expectedVoice={tr:'tr-TR-AhmetNeural',en:'Andrew',de:'Stefan'}[value];
    if(result.bankVoice!==expectedVoice||result.bankLocale!=={tr:'tr-TR',en:'en-US',de:'de-DE'}[value]||result.validTrials!==24||result.presentations?.length!==24||result.digitAccuracy!==.5||result.tripletAccuracy!==.5||result.value!==-1||result.quality!=='valid')throw Error('Actual localized scored record differs');
    if(result.history.some((h,i)=>JSON.stringify(h.digits)!==JSON.stringify(replies[i].digits)||JSON.stringify(h.answer)!==JSON.stringify(replies[i].response)))throw Error('Scored responses differ from submitted synthetic answers');
    const pcm=await page.evaluate(()=>attuneHearingQA.pcm);
    if(pcm.length!==26||pcm.some(r=>!r.ended||r.rate!==48000||r.channels!==2))throw Error('Real channel/DIN output completion missing');
    const cards=await page.locator('[data-din-scorecards]').innerText();
    for(const title of ['Doğru sayı','Tam üçlü','Geçerli deneme'])if(!cards.includes(await label(title)))throw Error('Localized scorecard missing');
    Object.assign(row,{status:'PASS',requests,pcm,result,submitted:replies,localizedScorecards:cards});
  }catch(error){Object.assign(row,{error:String(error),requests,observed:await page.evaluate(()=>window.attuneHearingQA||null).catch(()=>null)});}
  finally{
    page.off('response',observe);
    await page.evaluate(()=>{window.attuneRestoreRandom?.();window.attuneRestorePCM?.();}).catch(()=>{});
  }
  return row;
}
module.exports={NEURAL_TEXT,LANGUAGES,MODULE_EVENTS,NATIVE_PARK,validate,language,recording,decode,neural,activeStart,activeInterrupt,hearing};
