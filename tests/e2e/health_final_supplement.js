async page=>{
 const base='http://127.0.0.1:3311',assert=(x,m)=>{if(!x)throw Error(m)},proof={storageFailures:[],physicalUserAcceptance:false};
 await page.addInitScript({path:'tests/e2e/mental_technical_boot.js'});
 await page.route('**/api/mental/speech',r=>r.fulfill({path:'apps/vehicle-app/public/audio/guidance/mental-entry-voice-only-v1.mp3',contentType:'audio/mpeg'}));
 // Shared permission failure must fail closed in every module.
 for(const id of ['skin','vision','dental','hearing','mental']){
  await page.goto(base+'/'+id);await page.getByRole('dialog').waitFor();await page.evaluate(()=>{const old=Storage.prototype.setItem;Storage.prototype.setItem=function(k,v){if(k==='attune_health_processing_v1')throw new DOMException('controlled quota','QuotaExceededError');return old.call(this,k,v)}});
  for(const c of await page.getByRole('dialog').getByRole('checkbox').all())await c.check();await page.getByRole('button',{name:'İzin ver ve devam et'}).click();await page.getByRole('alert').filter({hasText:'İzin kaydedilemedi'}).waitFor();assert(await page.getByRole('dialog').count()===1&&await page.evaluate(()=>mentalProbe.cameraAttempts)===0,'Storage failure opened media');proof.storageFailures.push(id);
 }
 // A delayed old conversation response cannot alter a different module.
 await page.goto(base+'/mental');for(const c of await page.getByRole('dialog').getByRole('checkbox').all())await c.check();await page.getByRole('button',{name:'İzin ver ve devam et'}).click();let pending,received=false;
 await page.route('**/api/mental/converse',r=>{received=true;pending=r});await page.getByRole('button',{name:'Görüşmeyi Başlat',exact:true}).click();await page.waitForFunction(()=>document.querySelector('[data-conversation-phase]')?.dataset.conversationPhase==='listening');await page.evaluate(()=>mentalProbe.current.emit('Kontrollü gecikmiş yanıt.'));await page.waitForFunction(()=>document.querySelector('[data-conversation-phase]')?.dataset.conversationPhase==='preparing');assert(received,'No pending request');
 await page.getByRole('link',{name:'Kokpit',exact:true}).click();await page.waitForURL(base+'/');try{await pending.fulfill({json:{reply:'OLD RESPONSE MUST NOT APPEAR',providerType:'LIVE_OPENAI'}})}catch{/* Native abort is a valid terminal state. */}
 assert(!(await page.locator('main').innerText()).includes('OLD RESPONSE MUST NOT APPEAR'),'Late response entered new page');assert(Number(await page.locator('[data-playback-wave]').getAttribute('data-amplitude'))===0,'Late response played');assert(await page.evaluate(()=>mentalProbe.recognitions.every(r=>r.aborted)&&mentalProbe.audios.every(a=>a.paused)),'Owned media survived route');assert(await page.evaluate(()=>JSON.parse(localStorage.getItem('togg_health_mental_history')||'[]').length)===0,'Late callback saved');proof.pendingTurnRouteAbort=true;
 const d=page.waitForEvent('download');await page.evaluate(v=>{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(v)],{type:'application/json'}));a.download='supplement.json';a.click()},proof);await(await d).saveAs('../cdc-progress/health-final-technical-closeout-20261017/supplement-proof.json');return proof;
}
