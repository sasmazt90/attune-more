async page=>{
 const assert=(x,m)=>{if(!x)throw Error(m)};
 await page.addInitScript(()=>{
  window.contexts=[];window.waves=[];window.failSource=false;window.unownedPauses=0;
  const Context=window.AudioContext;window.AudioContext=function(...args){const c=new Context(...args);contexts.push(c);return c};window.AudioContext.prototype=Context.prototype;
  const pause=HTMLMediaElement.prototype.pause;HTMLMediaElement.prototype.pause=function(){if(this.id==='unowned')unownedPauses++;return pause.call(this)};
  const start=AudioBufferSourceNode.prototype.start;AudioBufferSourceNode.prototype.start=function(...args){const row={at:performance.now(),duration:this.buffer?.duration,ended:false,suppressed:failSource};waves.push(row);this.addEventListener('ended',()=>row.ended=true);if(failSource)return;return start.apply(this,args)};
 });
 await page.goto('http://127.0.0.1:3309/hearing');await page.getByRole('dialog').waitFor();await page.getByRole('dialog').getByRole('checkbox').check();await page.getByRole('button',{name:'İzin ver ve devam et'}).click();await page.waitForFunction(()=>document.querySelector('[data-vehicle-status]')?.textContent==='PARK',{},{timeout:30000});
 await page.evaluate(()=>{const media=document.createElement('video');media.id='unowned';document.body.append(media)});
 await page.getByRole('button',{name:'Ses hazırlığını başlat'}).click();await page.getByRole('button',{name:'Sol kanalı dinle'}).waitFor();await page.waitForFunction(()=>!document.querySelector('button')?.disabled&&unownedPauses>0,{},{timeout:25000});
 for(const ear of ['sol','sağ']){const button=page.getByRole('button',{name:(ear==='sol'?'Sol':'Sağ')+' kanalı dinle'});await button.waitFor();await button.click();await page.getByLabel('Yalnız '+ear+' kulağımda duydum.').check({timeout:15000});}
 await page.getByRole('button',{name:'Saf ses testi',exact:true}).click();await page.getByRole('button',{name:'Duydum',exact:true}).waitFor({timeout:25000});
 await page.evaluate(()=>{failSource=true});await page.waitForFunction(()=>waves.some(w=>w.suppressed),{},{timeout:10000});
 const initial=await page.evaluate(()=>({waves:waves.length,text:document.querySelector('[data-tone-progress]')?.innerText}));
 await page.waitForFunction(()=>/[1-9][0-9]* ses denemesi/.test(document.querySelector('[data-tone-progress]')?.textContent||''),{},{timeout:7000});
 const fault=await page.evaluate(()=>({waves,unownedPauses,progress:document.querySelector('[data-tone-progress]')?.textContent,contexts:contexts.map(c=>c.state)}));
 await page.getByRole('button',{name:'Durdur',exact:true}).click();await page.waitForTimeout(100);
 const after=await page.evaluate(()=>({contexts:contexts.map(c=>c.state),records:JSON.parse(localStorage.getItem('attune_hearing_history_v1')||'[]').length}));
 assert(fault.unownedPauses>0,'Baseline did not reproduce unrelated media pause');assert(fault.waves.some(w=>w.suppressed&&!w.ended),'Baseline fault missing');assert(after.contexts.includes('running'),'Baseline pause did not leave context running');
 const proof={sourceCommit:'7fe773c1f87e0e45dd3386c6e08d13fda6f2cba7',initial,fault,after,bugs:['claim calls pause on unrelated DOM media','unstarted source advances completed presentation/adaptation','pause leaves hearing AudioContext running'],faultInjection:'one AudioBufferSource.start withheld; native timers and protocol untouched',physicalHeadphoneAcceptance:false};
 const d=page.waitForEvent('download');await page.evaluate(v=>{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(v)],{type:'application/json'}));a.download='baseline.json';a.click()},proof);await(await d).saveAs('../cdc-progress/hearing-technical-closeout-20261017/baseline.json');return proof;
}
