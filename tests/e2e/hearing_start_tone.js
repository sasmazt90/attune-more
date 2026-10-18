async page=>{
 await page.addInitScript(()=>{
  window.contexts=[];window.waves=[];window.guidance=[];window.autoRespond=false;window.failSource=false;window.unownedPauses=0;
  const C=window.AudioContext;window.AudioContext=function(...args){const c=new C(...args);contexts.push(c);return c};window.AudioContext.prototype=C.prototype;
  const pause=HTMLMediaElement.prototype.pause;HTMLMediaElement.prototype.pause=function(){if(this.id==='unowned')unownedPauses++;return pause.call(this)};
  const nativeRandom=crypto.getRandomValues.bind(crypto);crypto.getRandomValues=a=>{const result=nativeRandom(a);if(a instanceof Uint32Array&&a.length===1){window.lastNativeSeed=a[0];if(window.fixedSeed!==undefined)a[0]=window.fixedSeed;window.lastSeed=a[0];}return result;};
  window.addEventListener('attune-guidance-event',e=>guidance.push({...e.detail,at:performance.now()}));
  const nativeStart=AudioBufferSourceNode.prototype.start;
  AudioBufferSourceNode.prototype.start=function(...args){
   const b=this.buffer,stats=[];for(let ch=0;ch<b.numberOfChannels;ch++){const data=b.getChannelData(ch);let sum=0,peak=0,clipped=0;for(const x of data){sum+=x*x;peak=Math.max(peak,Math.abs(x));if(Math.abs(x)>=1)clipped++;}stats.push({rms:Math.sqrt(sum/data.length),peak,first:data[0],last:data.at(-1),clipped});}
   const row={at:performance.now(),audioTime:this.context.currentTime,scheduledAudioTime:args[0]||0,sampleRate:b.sampleRate,duration:b.duration,channels:stats,ended:false,suppressed:failSource};waves.push(row);
   this.addEventListener('ended',()=>{row.ended=true;row.endedAt=performance.now();row.endedAudioTime=this.context.currentTime});
   if(failSource)return;
   const out=nativeStart.apply(this,args);
   if(window.autoRespond&&Math.max(...stats.map(c=>c.peak))>=Math.pow(10,-50/20))setTimeout(()=>{const button=[...document.querySelectorAll('button')].find(b=>b.textContent==='Duydum');button?.click();row.respondedAt=performance.now()},320);
   return out;
  };
 });
 await page.goto('http://127.0.0.1:3309/hearing');
 const modal=page.getByRole('dialog');if(await modal.count()){await modal.getByRole('checkbox').check();await modal.getByRole('button',{name:'İzin ver ve devam et'}).click();}
 await page.waitForFunction(()=>document.querySelector('[data-vehicle-status]')?.textContent==='PARK',{},{timeout:20000});
 await page.evaluate(()=>{const v=document.createElement('video');v.id='unowned';document.body.append(v);window.fixedSeed=8102026});
 await page.getByRole('button',{name:'Ses hazırlığını başlat'}).click();
 for(const ear of ['sol','sağ']){await page.getByRole('button',{name:(ear==='sol'?'Sol':'Sağ')+' kanalı dinle'}).click({timeout:25000});await page.getByLabel('Yalnız '+ear+' kulağımda duydum.').check({timeout:10000});}
 await page.evaluate(()=>{if(unownedPauses)throw Error('Hearing touched unrelated media');window.autoRespond=true;window.sessionStartedAt=performance.now();});
 await page.getByRole('button',{name:'Saf ses testi',exact:true}).click();await page.getByRole('button',{name:'Duydum',exact:true}).waitFor({timeout:20000});
 return {stage:'one complete native-timer tone session running',engineeringResponses:'based on actual PCM peak',randomSeed:8102026,mutedBrowserProcess:true,protocolTimersUnchanged:true};
}
