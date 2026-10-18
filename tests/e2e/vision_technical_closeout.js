/** Playwright CLI run-code. Controlled camera/model/ASR only in this test page.
 * Actual production controller, local bank/API, native MSE/Audio and history.
 * No physical microphone, eye-cover or audible-speaker acceptance is claimed.
 */
async page => {
 const MODE='desktop';
 const assert=(ok,why)=>{if(!ok)throw Error(why);};
 const wait=()=>page.waitForFunction(()=>{const c=JSON.parse(document.querySelector('canvas')?.dataset.visionEvidence||'null')?.conditions;return document.querySelector('[data-vision-stage]')?.dataset.visionStage==='listening'&&probe.current&&!probe.current.aborted&&document.querySelector('[data-letter-optotype]')&&c?.positionValid&&c.qualityValid&&c.distanceState==='stable'&&performance.now()-c.observedAt<500;},null,{timeout:40000});
 const count=()=>page.evaluate(()=>probe.events.filter(e=>e.combinedCorrect!==undefined).length);
 const target=()=>page.locator('[data-letter-optotype]').evaluate(e=>({id:document.querySelector('[data-vision-trial]').dataset.visionTrial,path:e.querySelector('path').getAttribute('d'),transform:e.querySelector('g').getAttribute('transform'),size:e.getBoundingClientRect().width,rect:e.getBoundingClientRect().toJSON()}));
 const paths={'M15 90L50 10L85 90M29 60H71':'A','M20 90V10H55C85 10 85 50 55 50H20M55 50C90 50 90 90 55 90H20':'B','M80 10H20V90H80M20 50H70':'E','M80 10H20V90M20 50H70':'F','M20 90V10H55C90 10 90 50 55 50H20':'P','M20 90V10H55C90 10 90 50 55 50H20M55 50L85 90':'R'};
 const words=t=>({letter:paths[t.path],direction:({0:'düz',90:'sağa yatmış',180:'baş aşağı',270:'sola yatmış'})[+t.transform.match(/rotate\((\d+)\)/)[1]]+(t.transform.includes('scale(-1')?' ve aynalı':'')});
 const emit=(text,confidence=.99,final=true,duplicate=false)=>page.evaluate(({text,confidence,final,duplicate})=>{probe.current.confidence=confidence;probe.current.emit(text,final,duplicate);},{text,confidence,final,duplicate});
 const prior=await page.evaluate(()=>typeof probe==='undefined'?[]:probe.events.filter(e=>e.combinedCorrect!==undefined));
 const resume=MODE==='desktop'&&prior.length>0&&prior.length<24&&await page.locator('[data-letter-optotype]').count()>0;
 if(!resume){await page.addInitScript({path:'tests/e2e/vision_technical_boot.js'});await page.goto('http://127.0.0.1:3306/vision');await page.getByRole('button',{name:'Başlat',exact:true}).waitFor();}
 const initialRecords=await page.evaluate(()=>JSON.parse(localStorage.getItem('togg_health_vision_history')||'[]').length);
 if(!resume)await page.getByRole('button',{name:'Başlat',exact:true}).click();await wait();
 const observations=resume?prior.map(e=>({id:e.presentationId,size:e.renderedGeometry.viewportWidthCssPx,source:'production DOM geometry diagnostic from the same pending session'})):[],checks={resumedPartialSession:resume,priorCompletedTrials:resume?prior.length:0};const max=MODE==='desktop'?24:3;
 for(let index=resume?prior.length:0;index<max;index++){
  await wait();let t=await target();const answer=words(t);assert(answer.letter,'Unknown actual SVG path');
  if(index===0){
   await page.waitForFunction(()=>probe.audios.some(a=>a.code==='first'&&!a.paused),null,{timeout:10000});
   checks.answerDuringNativePrompt=await page.evaluate(()=>probe.audios.at(-1).paused===false);
   await emit('Harf alanına bakın. Harfi ve yönünü istediğiniz sırada söyleyin.');assert(await count()===0,'Instruction echo scored');
   await emit(answer.direction,.99,false);assert(await count()===0,'Interim scored');
   await emit(answer.direction);await emit(answer.direction,.99,true,true);assert(await count()===0,'Partial or duplicate scored');
   await emit(answer.letter);
  }else if(index===1&&MODE==='desktop'){
   await emit(answer.letter,.3);await emit(answer.direction);assert(await count()===index,'Low confidence component accepted without confirmation');await emit(answer.letter);
  }else if(index===2&&MODE==='desktop')await emit((answer.letter==='F'?'P':'F')+' '+answer.direction);
  else if(index===3&&MODE==='desktop')await emit('göremiyorum');
  else if(index===4&&MODE==='desktop'){
   const wrong=answer.letter==='F'?'P':'F';await emit(wrong);await emit(`${wrong} değil ${answer.letter} ${answer.direction}`);
  }else if(index===5&&MODE==='desktop'){
   await emit(answer.direction);await emit('duraklat');
   await page.waitForFunction(()=>document.querySelector('[data-vision-stage]').dataset.visionStage==='user-paused'&&probe.current&&!probe.current.aborted);
   await emit('göremiyorum');assert(await count()===index,'Paused answer scored');assert(await page.locator('[data-letter-optotype]').count()===0,'Paused letter visible');
   await emit('devam et',.3);assert(await page.locator('[data-vision-stage]').getAttribute('data-vision-stage')==='user-paused','Low-confidence resume admitted');
   await emit('devam et');await wait();const resumed=await target();assert(resumed.path===t.path&&resumed.transform===t.transform&&resumed.size===t.size,'Resume changed pending target');checks.spokenPauseResume=true;t=resumed;await emit(answer.letter+' '+answer.direction);
  }else if(index===6&&MODE==='desktop'){
   await page.evaluate(()=>probe.fault='near');await page.waitForFunction(()=>JSON.parse(document.querySelector('canvas').dataset.visionEvidence).rawConditions.distanceState==='near');
   await emit(answer.letter+' '+answer.direction);assert(await count()===index,'Technical distance fault scored');await page.evaluate(()=>probe.fault=null);await wait();assert(await count()===index,'Old blocked answer automatically scored');checks.distanceDoesNotScore=true;await emit(answer.letter+' '+answer.direction);
  }else if(index===7&&MODE==='desktop'){
   await page.evaluate(()=>{probe.old=probe.current;probe.oldCallback=probe.current.onresult;probe.current.onerror({error:'no-speech'});probe.current.onend();});
   await page.waitForFunction(()=>probe.current!==probe.old&&!probe.current.aborted);await page.evaluate(()=>probe.oldCallback({resultIndex:0,results:[Object.assign([{transcript:'düz F',confidence:.99}],{isFinal:true})]}));assert(await count()===index,'Stale recognizer scored');checks.staleRecognitionIgnored=true;await emit(answer.direction+' '+answer.letter);
  }else if(index===9&&MODE==='desktop'){
   await page.evaluate(()=>probe.fault='uncertain');await page.waitForFunction(()=>document.querySelector('[data-vision-stage]').dataset.visionStage==='condition-paused',null,{timeout:6000});
   assert(await count()===index,'Unknown eyes scored');await page.evaluate(()=>probe.fault=null);await wait();const recovered=await target();assert(recovered.path===t.path&&recovered.transform===t.transform&&recovered.size===t.size,'Recovery changed pending target');checks.sensorRecoverySameTarget=true;t=recovered;await emit(answer.letter+' '+answer.direction);
  }else if(index%2){await emit(answer.letter);await emit(answer.direction);}
  else await emit(answer.direction+' '+answer.letter);
  await page.waitForFunction(n=>probe.events.filter(e=>e.combinedCorrect!==undefined).length===n,index+1,{timeout:7000});
  observations.push(t);
  if(index<max-1)await page.waitForFunction(id=>document.querySelector('[data-vision-trial]').dataset.visionTrial!==id,t.id,{timeout:7000});
  if(index===1){await page.locator('[data-letter-optotype]').scrollIntoViewIfNeeded();await page.screenshot({path:`output/playwright/vision/${MODE}-active.png`});}
 }
 const dimensions=await page.evaluate(()=>({width:innerWidth,height:innerHeight,dpr:devicePixelRatio,screenWidth:screen.width,screenHeight:screen.height,cssZoom:getComputedStyle(document.body).zoom,documentWidth:document.documentElement.scrollWidth,videoWidth:document.querySelector('video')?.videoWidth}));
 assert(dimensions.documentWidth<=dimensions.width+1,'Horizontal overflow');
 let record=null,history=null;
 if(MODE==='desktop'){
  await page.getByRole('dialog',{name:'Görme bildirimi'}).waitFor();await page.getByRole('button',{name:'Tamam',exact:true}).click();
  record=await page.evaluate(()=>JSON.parse(localStorage.getItem('togg_health_latest_vision')));const valid=record.trials.filter(t=>t.valid);
  assert(valid.length===24&&valid.filter(t=>t.eye==='RIGHT').length===12&&valid.filter(t=>t.eye==='LEFT').length===12,'Wrong valid denominator');
  assert(record.trials.some(t=>!t.valid)&&valid.some(t=>t.notVisible)&&valid.some(t=>!t.letterCorrect&&!t.notVisible),'Missing valid-wrong/not-visible/technical distinctions');
  assert(observations[0].size===120&&observations[1].size===120&&observations[2].size===60&&observations[3].size===60&&observations[4].size===120,'Two-up/down rendered sizes changed');
  assert(valid.every((t,i)=>t.renderedGeometry.viewportWidthCssPx===observations[i].size),'Stored geometry differs from actual SVG');
  const summary=await page.locator('[data-eye-summary]').allTextContents();await page.screenshot({path:'output/playwright/vision/desktop-result.png',fullPage:true});
  const before=JSON.stringify(record);await page.reload();await page.getByRole('button',{name:'Sonucu Aç',exact:true}).click();const dialog=page.getByRole('dialog',{name:'Göz Sağlığı sonucu'});await dialog.locator('[data-eye-summary]').first().waitFor();
  history={sameSummary:JSON.stringify(await dialog.locator('[data-eye-summary]').allTextContents())===JSON.stringify(summary),unchangedRecord:await page.evaluate(before=>JSON.stringify(JSON.parse(localStorage.getItem('togg_health_latest_vision')))===before,before)};
  assert(history.sameSummary&&history.unchangedRecord,'History mismatch');await page.screenshot({path:'output/playwright/vision/desktop-history.png',fullPage:true});await dialog.getByRole('button',{name:'Sonuç penceresini kapat'}).click();
 }else{
  await page.getByRole('button',{name:'Bitir',exact:true}).click();await page.getByRole('button',{name:'Tamam',exact:true}).click();assert(await page.evaluate(()=>JSON.parse(localStorage.getItem('togg_health_vision_history')||'[]').length)===initialRecords,'Cancelled partial record saved');
 }
 const value={mode:MODE,kind:'controlled video/model/ASR; actual page, native Audio/MSE and local speech API',physicalUserAcceptance:false,checks,dimensions,observations,record,history};
 const download=page.waitForEvent('download');await page.evaluate(value=>{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(value)],{type:'application/json'}));a.download='controller-proof.json';a.click();URL.revokeObjectURL(a.href);},value);await(await download).saveAs(`output/playwright/vision/${MODE}-proof.json`);
 return {mode:MODE,validTrials:record?.trials.filter(t=>t.valid).length,checks,dimensions,history};
}
