const fs=require('fs'),path=require('path'),assert=require('assert/strict');const {open,root}=require('./aaos-harness.cjs');
const {deleteSynthetic,referral}=require('./result-coverage.cjs');
(async()=>{
 const frames=Object.fromEntries(['Front','Right','Left'].map(k=>[k,fs.readFileSync(path.join(root,'fixtures/vision-anbox-input/vision'+k+'.y4m'))]));
 const camera=path.join(root,'runtime/vision-camera.y4m');fs.writeFileSync(camera,frames.Front);const fd=fs.openSync(camera,'r+');
 const h=await open('vision',{camera,controlledAudio:true});const {p,q,r,tr,save,act,observe,inventory}=h;r.states=[];let error;
 async function info(button,label){await act(label,button,()=>p.getByRole('button',{name:tr('Bilgi penceresini kapat'),exact:true}).waitFor());const d=p.getByRole('dialog').filter({has:p.getByRole('button',{name:tr('Bilgi penceresini kapat'),exact:true})});await observe(label+' text',d);await act(label+' close',d.getByRole('button',{name:tr('Bilgi penceresini kapat'),exact:true}),()=>d.waitFor({state:'hidden'}));}
 async function details(root,label){
  await inventory(label,root);
  for(const eye of ['RIGHT','LEFT']){const card=root.locator('[data-eye-result='+eye+']');await observe(label+' '+eye,card);const detail=card.locator('details');await act(label+' '+eye+' size table open',detail.locator('summary'),async()=>assert.equal(await detail.getAttribute('open'),''));for(const row of await detail.locator('tbody tr').all())await observe(label+' actual size row',row,500);await act(label+' '+eye+' size table close',detail.locator('summary'),async()=>assert.equal(await detail.getAttribute('open'),null));}
  for(const text of ['Sonraki kartlar','Önceki kartlar']){const button=root.getByRole('button',{name:tr(text),exact:true}),id=await button.getAttribute('aria-controls'),rail=p.locator('[id="'+id+'"]');const before=await rail.evaluate(e=>({left:e.scrollLeft,width:e.clientWidth,total:e.scrollWidth}));if(await button.isEnabled())await act(label+' '+text,button,async()=>{await p.waitForFunction(({id,left})=>Math.abs(document.getElementById(id).scrollLeft-left)>1,{id,left:before.left});});else{assert(before.total<=before.width+2||(text==='Önceki kartlar'?before.left<=2:before.left+before.width>=before.total-2));r.actions.push({label:label+' '+text,status:'DISABLED_VERIFIED',reason:'Measured scroll geometry confirms both cards fit or the boundary is reached',geometry:before,seconds:h.stamp()});}}
 }
 async function assessment(){
  fs.writeSync(fd,frames.Front,0,frames.Front.length,0);let completed=false;
  await p.getByRole('button',{name:tr('Başlat'),exact:true}).click();
  let pose='Front',lastTrial='',lastProgress=Date.now(),spokenTrial='',spokenAt=0;const end=Date.now()+900000;
  while(Date.now()<end){
   const state=await p.locator('[data-vision-stage]').evaluate(e=>({stage:e.dataset.visionStage,trial:e.dataset.visionTrial,text:e.innerText,voice:e.querySelector('[data-vision-voice]')?.getAttribute('data-vision-voice'),readiness:e.querySelector('[data-vision-readiness]')?.textContent,evidence:JSON.parse(document.querySelector('canvas[data-vision-evidence]')?.getAttribute('data-vision-evidence')||'null')}));
   state.seconds=h.stamp();r.states.push(state);save();if(state.stage==='result'){completed=true;r.result=true;break;}if(state.stage==='error')throw Error(state.text);
   let target='Front';if(!['idle','preparing'].includes(state.stage)){if(/Sağ göz\s*[·•]/.test(state.text))target='Right';else if(/Sol göz\s*[·•]/.test(state.text))target='Left';}
   if(target!==pose){fs.writeSync(fd,frames[target],0,frames[target].length,0);pose=target;r.states.push({cameraSwitch:pose,seconds:h.stamp()});}
   if(state.trial&&state.trial!==lastTrial){lastTrial=state.trial;lastProgress=Date.now();console.log('Vision presentation',lastTrial);}
   if(state.voice==='listening'&&state.readiness==='Dinliyor'&&(spokenTrial!==state.trial||Date.now()-spokenAt>25000)){
    await q.waitForTimeout(500);spokenTrial=state.trial;spokenAt=Date.now();await q.evaluate(()=>window.playFixture('vision-not-visible-tr.wav'));
   }
   if(Date.now()-lastProgress>120000)throw Error('Actual camera/voice gate stalled for 120 seconds');await p.waitForTimeout(600);
  }
  assert(completed,'Vision did not complete');const dialog=p.getByRole('dialog');if(await dialog.count()){await observe('Actual completion notice',dialog);await act('Completion acknowledgement',dialog.getByRole('button',{name:tr('Tamam'),exact:true}),()=>dialog.waitFor({state:'hidden'}));}
 }
 try{
  await p.getByRole('link',{name:tr('Gizlilik & İzinler'),exact:true}).click();await p.getByRole('checkbox',{name:tr('Yön hizalama sonuçlarını bu cihazda sakla'),exact:true}).check();await p.locator('nav a[href="/"]').click();
  r.beforeIds=await p.evaluate(()=>JSON.parse(localStorage.getItem('togg_health_vision_history')||'[]').map(x=>x.id));r.recordsBefore=r.beforeIds.length;
  await h.record();await h.enter();await assessment();
  await details(p.locator('[data-letter-result]'),'live');await info(p.locator('[data-vision-stage] button[aria-haspopup=dialog]').first(),'Vision information');
  // Retry clears only transient result; the genuinely generated record survives.
  await act('New analysis',p.getByRole('button',{name:tr('Yeni Analiz'),exact:true}),()=>p.getByRole('button',{name:tr('Başlat'),exact:true}).waitFor());
  assert.equal(await p.evaluate(()=>JSON.parse(localStorage.getItem('togg_health_vision_history')||'[]').length),r.recordsBefore+1);
  await assessment();await observe('Second genuine assessment after retry',p.locator('[data-letter-result]'));
  await referral(h,p.locator('[data-letter-result]').getByRole('link',{name:tr('Uzman seçenekleri'),exact:true}),'vision','Live result referral');
  await p.getByRole('link',{name:tr('Sağlık Geçmişim'),exact:true}).click();const row=p.locator('[data-record-category=vision]').first();await observe('Saved result',row);await row.getByRole('button',{name:tr('Sonucu Aç'),exact:true}).click();await details(p.getByRole('dialog').locator('[data-letter-result]'),'saved');await info(p.getByRole('dialog').locator('button[aria-haspopup=dialog]'),'Saved information');
  r.records=await p.evaluate(()=>JSON.parse(localStorage.getItem('togg_health_vision_history')||'[]'));assert.equal(r.records.length,r.recordsBefore+2);const generated=r.records.filter(x=>!r.beforeIds.includes(x.id));assert.equal(generated.length,2);for(const record of generated){assert.equal(record.trials.length,24);assert(record.trials.every(t=>t.valid&&t.notVisible));for(const eye of ['RIGHT','LEFT'])assert.equal(record.trials.filter(t=>t.eye===eye).length,12);}
  await act('Close saved Vision result',p.getByRole('button',{name:tr('Sonuç penceresini kapat'),exact:true}),()=>p.getByRole('dialog').waitFor({state:'hidden'}));
  await act('Reopen saved Vision result',row.getByRole('button',{name:tr('Sonucu Aç'),exact:true}),()=>p.getByRole('dialog').waitFor());
  await referral(h,p.getByRole('dialog').getByRole('link',{name:tr('Uzman seçenekleri'),exact:true}),'vision','Saved result referral');
  r.generated=generated;save();for(const record of generated)await deleteSynthetic(h,record.id,'vision');
  await p.locator('nav a[href="/"]').click();await observe('Clean cockpit ending',p.locator('main'));
  r.remaining=[];r.fullResultCoverage=true;
 }catch(e){error=e;process.exitCode=1;console.error(String(e));}finally{fs.closeSync(fd);await h.close(error);}
})().catch(e=>{console.error(String(e));process.exitCode=1;});

