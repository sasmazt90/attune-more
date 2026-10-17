/** Recorded pixels -> unmodified production Face/Hand worker, actual API/audio.
 * This is not a physical eye-cover, depth or natural speech acceptance test. */
async page => {
 const assert=(v,m)=>{if(!v)throw Error(m)};
 // Next production inventories public files at startup. Serve only this
 // existing recorded fixture in the test; all model/API requests stay real.
 await page.route('**/__vision_audit__/frame.jpg',route=>route.fulfill({path:'../attune-live-test/audit-fixtures/head-shake-frames/frame-001.jpg',contentType:'image/jpeg'}));
 await page.addInitScript(()=>{
  window.modelProbe={mode:'photo',events:[],workers:[],streams:[],micAttempts:0};
  localStorage.setItem('attune_privacy_vision_save_allowed','true');
  navigator.mediaDevices.getUserMedia=async constraints=>{
   if(!constraints.video){modelProbe.micAttempts++;throw new DOMException('No physical microphone in recorded-pixel test','NotAllowedError')}
   const im=new Image();im.src='/__vision_audit__/frame.jpg';await im.decode();
   const c=document.createElement('canvas');c.width=im.naturalWidth;c.height=im.naturalHeight;const ctx=c.getContext('2d');
   const draw=()=>{if(modelProbe.mode==='black'){ctx.fillStyle='#000';ctx.fillRect(0,0,c.width,c.height)}else ctx.drawImage(im,0,0)};draw();
   const timer=setInterval(draw,100),s=c.captureStream(10);modelProbe.streams.push(s);s.getTracks()[0].addEventListener('ended',()=>clearInterval(timer));return s;
  };
  const NativeWorker=window.Worker;
  window.Worker=class extends NativeWorker{constructor(...a){super(...a);const item={index:modelProbe.workers.length,closed:false};modelProbe.workers.push(item);this.addEventListener('message',e=>{if(e.data.evidence){const v=e.data.evidence;modelProbe.events.push({worker:item.index,mode:modelProbe.mode,at:performance.now(),delegate:v.delegate,sourceFrame:v.conditions.observedAt,conditions:v.conditions,sourceHeadBox:v.alignment.box})}});this.item=item}terminate(){this.item.closed=true;super.terminate()}};
 });
 await page.goto('http://127.0.0.1:3306/vision');const initial=await page.evaluate(()=>localStorage.getItem('togg_health_vision_history'));
 await page.getByRole('button',{name:'Başlat',exact:true}).click();
 await page.waitForFunction(()=>modelProbe.events.some(e=>e.conditions.faceCount===1&&e.conditions.distanceState==='stable'),null,{timeout:60000});
 const baseline=await page.evaluate(()=>({last:modelProbe.events.at(-1),width:document.querySelector('video').videoWidth,height:document.querySelector('video').videoHeight,letters:document.querySelectorAll('[data-letter-optotype]').length}));
 assert(baseline.last.conditions.right.state==='open'&&baseline.last.conditions.left.state==='open','Recorded source did not establish both-open reference');
 assert(baseline.letters===0,'Both-open source admitted a monocular trial');
 await page.setViewportSize({width:750,height:900});const mark=await page.evaluate(()=>modelProbe.events.length);
 await page.waitForFunction(n=>modelProbe.events.length>n+3,mark,{timeout:10000});
 const resized=await page.evaluate(()=>({last:modelProbe.events.at(-1),width:document.querySelector('video').videoWidth,height:document.querySelector('video').videoHeight}));
 assert(resized.width===baseline.width&&resized.height===baseline.height&&resized.last.conditions.distanceState==='stable','Window size changed source distance');
 await page.evaluate(()=>modelProbe.mode='black');
 await page.waitForFunction(()=>modelProbe.events.at(-1)?.conditions.faceCount===0,null,{timeout:15000});
 const black=await page.evaluate(()=>modelProbe.events.at(-1));
 assert(black.conditions.right.state==='uncertain'&&black.conditions.left.state==='uncertain','Lost face retained an eye state');
 await page.evaluate(()=>modelProbe.mode='photo');await page.waitForFunction(()=>modelProbe.events.at(-1)?.conditions.faceCount===1,null,{timeout:15000});
 await page.locator('video').evaluate(v=>v.pause());await page.waitForTimeout(1200);
 const stale=await page.evaluate(()=>({stage:document.querySelector('[data-vision-stage]').dataset.visionStage,letters:document.querySelectorAll('[data-letter-optotype]').length,last:modelProbe.events.at(-1),now:performance.now()}));
 assert(stale.letters===0&&stale.now-stale.last.sourceFrame>750,'Paused source remained fresh or exposed a trial');
 await page.locator('video').evaluate(v=>v.play());await page.waitForFunction(()=>performance.now()-modelProbe.events.at(-1).sourceFrame<600,null,{timeout:10000});
 const observedWorkers=await page.evaluate(()=>modelProbe.workers.length);await page.locator('a[href="/"]').first().click();
 await page.waitForFunction(n=>modelProbe.workers.length===n&&modelProbe.streams.every(s=>s.getTracks().every(t=>t.readyState==='ended'))&&modelProbe.workers.every(w=>w.closed),observedWorkers,{timeout:10000});
 const stopped=await page.evaluate(()=>({workers:modelProbe.workers,tracks:modelProbe.streams.map(s=>s.getTracks().map(t=>t.readyState)),micAttempts:modelProbe.micAttempts}));
 const result={kind:'existing licensed recorded pixels -> actual production MediaPipe Face/Hand worker; no landmark/eye override',physicalUserAcceptance:false,baseline,resized,black,stale,spaRouteCleanup:stopped,historyUnchanged:await page.evaluate(initial=>localStorage.getItem('togg_health_vision_history')===initial,initial)};
 assert(result.historyUnchanged,'Nonqualifying/cancelled source saved a result');
 const download=page.waitForEvent('download');await page.evaluate(value=>{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(value)],{type:'application/json'}));a.download='model-proof.json';a.click()},result);await(await download).saveAs('output/playwright/vision/models-proof.json');return result;
}
