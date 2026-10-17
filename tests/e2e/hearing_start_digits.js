async page=>{
 if(await page.getByRole('dialog').count())await page.getByRole('button',{name:'Sonuç penceresini kapat'}).click();
 await page.evaluate(async()=>{
  window.fixedSeed=8102026;window.autoRespond=false;window.dinReference=[];window.countdowns=[];window.dinActive=false;window.answerProbeCount=0;
  const decoder=new OfflineAudioContext(1,1,48000),manifest=await(await fetch('/audio/hearing-bank/manifest.json')).json();window.referenceManifest=manifest;
  const decode=async item=>(await decoder.decodeAudioData(await(await fetch(item.url)).arrayBuffer())).getChannelData(0).slice();window.referenceBank=await Promise.all(manifest.digits.map(decode));window.referenceNoise=await decode(manifest.noise);
  const observer=new MutationObserver(()=>{const value=document.querySelector('[data-din-countdown]')?.textContent;if(value&&window.countdowns.at(-1)?.value!==value)window.countdowns.push({value,at:performance.now()})});observer.observe(document.body,{subtree:true,childList:true,characterData:true});window.dinObserver=observer;
  let randomState=8102026;const random=()=>{randomState=(1664525*randomState+1013904223)>>>0;return randomState/4294967296;};let snr=0,lastDirection=0,reversals=0;
  const nativeStart=AudioBufferSourceNode.prototype.start;
  AudioBufferSourceNode.prototype.start=function(...args){
   if(window.dinActive){
    const index=window.dinReference.length,digits=Array.from({length:3},()=>Math.floor(random()*10)),draw=random(),gap=8640,length=digits.reduce((n,d)=>n+referenceBank[d].length,0)+2*gap;
    const speech=new Float32Array(length),noise=new Float32Array(length);let at=0;for(const d of digits){speech.set(referenceBank[d],at);at+=referenceBank[d].length+gap;}const offset=Math.floor(draw*referenceNoise.length),ramp=1440;
    for(let i=0;i<length;i++){const e=Math.min(1,i/ramp,(length-1-i)/ramp);speech[i]*=e;noise[i]=referenceNoise[(offset+i)%referenceNoise.length]*e;}
    const rms=a=>Math.sqrt(a.reduce((s,x)=>s+x*x,0)/a.length),sr=rms(speech),nr=rms(noise),ng=sr/nr/10**(snr/20),raw=new Float32Array(length);for(let i=0;i<length;i++)raw[i]=speech[i]+noise[i]*ng;
    let peak=0;for(const x of raw)peak=Math.max(peak,Math.abs(x));const common=Math.min(.015/Math.max(rms(raw),.0001),.08/Math.max(peak,.0001));let difference=0;
    const buffer=this.buffer;if(buffer.length!==length||buffer.numberOfChannels!==2)throw Error('Unexpected DIN PCM length/channels');
    for(let ch=0;ch<2;ch++){const actual=buffer.getChannelData(ch);for(let i=0;i<length;i++)difference=Math.max(difference,Math.abs(actual[i]-Math.fround(raw[i]*common)));}
    if(difference>1e-8)throw Error('Actual played triplet differs from independent bank/order/SNR');
    const correct=index%2===0,answer=correct?digits:digits.map(d=>(d+1)%10);
    const row={index,digits,answer,requestedSNR:snr,maxPCMReconstructionDifference:difference,at:performance.now(),ended:false};window.dinReference.push(row);this.addEventListener('ended',()=>row.ended=true);
    const direction=correct?-1:1;if(lastDirection&&lastDirection!==direction&&snr>-15&&snr<15)reversals++;const step=reversals>=2?2:4;snr=Math.min(15,Math.max(-15,snr+direction*step));lastDirection=direction;
   }
   return nativeStart.apply(this,args);
  };
  window.dinAuto=setInterval(()=>{
   const input=document.querySelector('input[aria-label="Üç sayı yanıtı"]'),submit=[...document.querySelectorAll('[data-din-keypad] button')].find(b=>b.textContent==='Yanıtı Gönder');
   const row=window.dinReference.at(-1);if(!row||row.sent||!input||input.disabled||!submit)return;
   if(input.value.length<3){const digit=String(row.answer[input.value.length]),button=[...document.querySelectorAll('[data-din-keypad] button')].find(b=>b.textContent===digit&&!b.disabled);button?.click();}
   else if(!submit.disabled){row.sent=true;row.sentAt=performance.now();submit.click();submit.click();window.answerProbeCount++;}
   if(document.querySelector('[data-hearing-result]'))clearInterval(window.dinAuto);
  },90);
 });
 await page.getByRole('button',{name:'Ses hazırlığını başlat'}).click();for(const ear of ['sol','sağ']){await page.getByRole('button',{name:(ear==='sol'?'Sol':'Sağ')+' kanalı dinle'}).click({timeout:25000});await page.getByLabel('Yalnız '+ear+' kulağımda duydum.').check({timeout:10000});}
 await page.evaluate(()=>{window.dinActive=true;window.dinStartedAt=performance.now()});await page.getByRole('button',{name:'Gürültüde Türkçe sayılar',exact:true}).click();
 return {stage:'one 24-valid DIN session running',source:'approved bank; independent byte-for-byte PCM reconstruction',engineeringReplies:'alternating correct/incorrect via actual keypad; deliberate duplicate submit',browserOutputMuted:true};
}
