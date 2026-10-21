'use strict';
// Finite real-WebView acceptance helpers. No native media grants, provider
// calls, test hooks in the product, or fabricated playback events.
const path = require('node:path');
const {execFileSync} = require('node:child_process');
const LANGUAGES = new Set(['tr', 'en', 'de']);
const MODULE_EVENTS = {skin:'guidance:skin-neutral', dental:'guidance:dental-front',
  vision:'vision:next1', hearing:'guidance:hearing-tone', mental:'guidance:mental-entry'};
const NATIVE_PARK = {tr:'PARK doğrulandı', en:'PARK verified', de:'PARK bestätigt'};
let bundle;
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
  const statuses=[];
  const observe=response=>{if(new URL(response.url()).pathname==='/api/mental-neural-speech')statuses.push(response.status());};
  page.on('response',observe);
  try {
    const result=await page.evaluate(async language=>{
      const q=window.ApprovedAudioQA;
      if(q.core.getLanguage()!==language)throw Error('Selected locale differs');
      if(q.neural.mentalSpeechEngine()!=='chatterbox-v3')throw Error('Explicit fallback selected; do not overwrite owner preference');
      const text={tr:'Bu yeni ve kişisel olmayan örnekte 1287 sayısı var.',en:'This new nonpersonal example includes the number 1287.',de:'Dieses neue, nichtpersönliche Beispiel enthält die Zahl 1287.'}[language];
      const started=performance.now();let starts=0;
      const played=await q.neural.mentalNeuralSpeech(text,new AbortController().signal,()=>q.core.getLanguage()===language,()=>starts++,()=>{});
      return {language,played,starts,milliseconds:performance.now()-started,format:'audio/wav',realModelClaimed:false};
    },value);
    return {...result,httpStatuses:statuses,status:result.played&&result.starts===1?'PASS':statuses.some(s=>[401,403,429,503,504].includes(s))?'BLOCKED':'FAIL',
      meaning:'Actual backend transport/playback attempt. Model/profile readiness and naturalness require separately verified inference evidence.'};
  }finally{page.off('response',observe);}
}
module.exports={LANGUAGES,MODULE_EVENTS,NATIVE_PARK,validate,language,recording,decode,neural};
