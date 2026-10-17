async page=>{
 await page.goto('http://127.0.0.1:3309/hearing');
 const result=await page.evaluate(async({sources,hashes})=>{
  const cache={};const require=name=>{if(cache[name])return cache[name];const module={exports:{}};cache[name]=module.exports;new Function('require','module','exports',sources[name])(require,module,module.exports);return module.exports;};
  const H=require('./hearingProtocol'),M=require('./playbackMeter'),{HearingAudio}=require('./hearingAudio');
  const channels=[];
  for(const hz of [250,500,1000,2000,4000,8000])for(const ear of ['left','right','both']){
   const input=H.tonePCM(hz,-40,1,48000);
   const render=async meter=>{const c=new OfflineAudioContext(2,48000,48000),buffer=c.createBuffer(2,48000,48000);if(ear!=='right')buffer.copyToChannel(input,0);if(ear!=='left')buffer.copyToChannel(input,1);const source=c.createBufferSource();source.buffer=buffer;let detach;if(meter)detach=M.observeOutputNode(c,source);else source.connect(c.destination);source.start();const output=await c.startRendering();detach?.();return [output.getChannelData(0),output.getChannelData(1)];};
   const direct=await render(false),meter=await render(true);let diff=0;for(let ch=0;ch<2;ch++)for(let i=0;i<48000;i++)diff=Math.max(diff,Math.abs(direct[ch][i]-meter[ch][i]));
   const stats=meter.map(p=>({rms:H.rms(p),peak:H.peak(p),first:p[0],last:p.at(-1),clipped:p.filter(x=>Math.abs(x)>=1).length}));
   if(diff!==0||stats.some(s=>s.clipped)||ear!=='both'&&stats[ear==='left'?1:0].peak!==0)throw Error('PCM channel/analyser regression');
   channels.push({frequency:hz,ear,digitalDbFS:-40,maxAbsoluteMeterDifference:diff,stats});
  }
  const engine=new HearingAudio(()=>{});await engine.loadBank(new AbortController().signal);const manifest=engine.manifest;
  const files=[];for(const item of [...manifest.digits,manifest.noise]){const bytes=await(await fetch(item.url)).arrayBuffer(),hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))).map(x=>x.toString(16).padStart(2,'0')).join('');if(hash!==item.sha256)throw Error('Bank hash mismatch');const pcm='digit' in item?engine.bank[item.digit]:engine.noise;files.push({url:item.url,sha256:hash,bytes:bytes.byteLength,samples:pcm.length,rms:H.rms(pcm),peak:H.peak(pcm),clipped:pcm.filter(x=>Math.abs(x)>=1).length});}
  const mixes=[];
  for(const snr of [-15,-8,0,8,15]){
   const digits=[2,0,7],random=.2345,mixed=engine.triplet(digits,snr,()=>random),gap=Math.round(48000*.18),length=mixed.pcm.length;
   const speech=new Float32Array(length),noise=new Float32Array(length);let at=0;for(const d of digits){speech.set(engine.bank[d],at);at+=engine.bank[d].length+gap;}
   const offset=Math.floor(random*engine.noise.length),ramp=Math.floor(.03*48000);for(let i=0;i<length;i++){const envelope=Math.min(1,i/ramp,(length-1-i)/ramp);speech[i]*=envelope;noise[i]=engine.noise[(offset+i)%engine.noise.length]*envelope;}
   const speechRMS=H.rms(speech),noiseRMS=H.rms(noise),noiseGain=speechRMS/noiseRMS/10**(snr/20);let delta=0;
   for(let i=0;i<length;i++){const unscaled=Math.fround(speech[i]+noise[i]*noiseGain),expected=Math.fround(unscaled*mixed.gain);delta=Math.max(delta,Math.abs(expected-mixed.pcm[i]));}
   const independentSNR=20*Math.log10((speechRMS*mixed.gain)/(noiseRMS*noiseGain*mixed.gain));
   if(delta>1e-8||Math.abs(independentSNR-snr)>1e-9||mixed.peak>.0800001||mixed.pcm[0]!==0||mixed.pcm.at(-1)!==0)throw Error('Independent mix/SNR check failed');
   mixes.push({digits,requestedSNR:snr,independentSNR,reportedSNR:mixed.actualSNR,peak:mixed.peak,rms:H.rms(mixed.pcm),speechRMS:mixed.speechRMS,noiseRMS:mixed.noiseRMS,maxReconstructionDifference:delta,clipped:mixed.pcm.filter(x=>Math.abs(x)>=1).length,first:mixed.pcm[0],last:mixed.pcm.at(-1)});
  }
  engine.close();return {runtimeSourceHashes:hashes,channels,bankVersion:manifest.version,bankProfile:{voice:manifest.voice,rate:manifest.rate,pitch:manifest.pitch,auditoryAcceptance:manifest.auditoryAcceptance},files,mixes,physicalHeadphoneAcceptance:false,clinicalValidation:false,hardwareOutput:'muted browser; OfflineAudioContext renders'};
 },{sources:__MODULES__,hashes:__HASHES__});
 const d=page.waitForEvent('download');await page.evaluate(v=>{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(v)],{type:'application/json'}));a.download='pcm.json';a.click()},result);await(await d).saveAs('../cdc-progress/hearing-technical-closeout-20261017/pcm.json');return {channels:result.channels.length,files:result.files.length,mixes:result.mixes.length,bank:result.bankVersion};
}
