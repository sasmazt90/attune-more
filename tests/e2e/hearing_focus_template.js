async page=>{
 await page.goto('http://127.0.0.1:3309/hearing');
 const proof=await page.evaluate(async({sources,hashes})=>{
  const cache={};const require=name=>{if(cache[name])return cache[name];const module={exports:{}};cache[name]=module.exports;new Function('require','module','exports',sources[name])(require,module,module.exports);return module.exports;};const {streamSpeech}=require('./streamSpeech');
  const manifest=await(await fetch('/audio/guidance/manifest.json')).json(),entry=manifest.entries['hearing-tone'],bytes=new Uint8Array(await(await fetch(entry.url)).arrayBuffer());
  const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))).map(x=>x.toString(16).padStart(2,'0')).join('');if(digest!==entry.sha256)throw Error('Existing voice hash changed');
  let cancelled=false,delayed;
  const response=new Response(new ReadableStream({start(controller){controller.enqueue(bytes);delayed=setTimeout(()=>controller.close(),60000)},cancel(){cancelled=true;clearTimeout(delayed)}}),{headers:{'Content-Type':'audio/mpeg'}});
  const audio=new Audio(),playing=new Promise((resolve,reject)=>{audio.addEventListener('playing',resolve,{once:true});setTimeout(()=>reject(Error('MSE did not play')),8000)});
  const stream=streamSpeech(audio,response,new AbortController().signal,()=>true),finished=stream.finished.then(()=>null,e=>e.name);await playing;
  localStorage.setItem('attune_hearing_audio_focus',String(Date.now()+5000));window.dispatchEvent(new Event('attune-audio-focus'));const error=await finished;
  let blocked=false;try{streamSpeech(new Audio(),new Response(bytes,{headers:{'Content-Type':'audio/mpeg'}}),new AbortController().signal,()=>true)}catch(e){blocked=e.message.includes('İşitme testi')}
  localStorage.setItem('attune_hearing_audio_focus',String(Date.now()-1));const next=new Audio(),ended=new Promise((resolve,reject)=>{next.addEventListener('ended',resolve,{once:true});next.addEventListener('error',reject,{once:true})});const resumed=streamSpeech(next,new Response(bytes,{headers:{'Content-Type':'audio/mpeg'}}),new AbortController().signal,()=>true);await resumed.finished;await ended;
  const value={runtimeSourceHashes:hashes,sourceSHA256:digest,actualMSEPlaying:true,pausedOnHearingLease:audio.paused,readerCancelled:cancelled,error,blockedDuringLease:blocked,playedAfterExpiry:next.ended,providerCalls:0,physicalHeadphoneAcceptance:false};
  stream.cancel();resumed.cancel();audio.removeAttribute('src');next.removeAttribute('src');URL.revokeObjectURL(stream.url);URL.revokeObjectURL(resumed.url);localStorage.removeItem('attune_hearing_audio_focus');
  if(!value.pausedOnHearingLease||!cancelled||error!=='AbortError'||!blocked||!next.ended)throw Error('Shared stream ownership regression');return value;
 },{sources:__MODULES__,hashes:__HASHES__});
 const d=page.waitForEvent('download');await page.evaluate(v=>{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(v)],{type:'application/json'}));a.download='focus.json';a.click()},proof);await(await d).saveAs('../cdc-progress/hearing-technical-closeout-20261017/focus.json');return {actualMSEPlaying:proof.actualMSEPlaying,blocked:proof.blockedDuringLease,readerCancelled:proof.readerCancelled,providerCalls:0};
}
