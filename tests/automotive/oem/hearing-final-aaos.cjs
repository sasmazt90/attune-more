const assert=require('assert/strict');const {open}=require('./aaos-harness.cjs');const {deleteSynthetic,referral}=require('./result-coverage.cjs');
(async()=>{const h=await open('hearing'),{p,r,tr,act,observe,inventory,save}=h;let error;r.assessments=[];r.finalCandidate=true;r.listener='Controlled synthetic listener observes the original unchanged random seed; enters alternating correct/incorrect responses through the UI. No calibrated human hearing claim.';
 async function info(button,label){await act(label,button,()=>p.getByRole('button',{name:tr('Bilgi penceresini kapat'),exact:true}).waitFor());const dialog=p.getByRole('dialog').filter({has:p.getByRole('button',{name:tr('Bilgi penceresini kapat'),exact:true})});await observe(label+' content',dialog);await act(label+' close',dialog.getByRole('button',{name:tr('Bilgi penceresini kapat'),exact:true}),()=>dialog.waitFor({state:'hidden'}));}
 async function assessment(){
  const beforeIds=await p.evaluate(()=>JSON.parse(localStorage.getItem('attune_hearing_history_v1')||'[]').map(x=>x.id));
  await act('Start sound preparation',p.getByRole('button',{name:tr('Ses hazırlığını başlat'),exact:true}));
  for(const [button,checkbox] of [['Sol kanalı dinle','Yalnız sol kulağımda duydum.'],['Sağ kanalı dinle','Yalnız sağ kulağımda duydum.']]){await act(button,p.getByRole('button',{name:tr(button),exact:true}));await p.getByRole('checkbox',{name:tr(checkbox),exact:true}).check();}
  await act('Start original Turkish DIN sequence',p.getByRole('button',{name:tr('Gürültüde Türkçe sayılar'),exact:true}));let seed=await p.evaluate(()=>window.__observedDinSeed);assert.equal(typeof seed,'number');const run={seed,trials:[]};r.assessments.push(run);
  const random=()=>{seed=(1664525*seed+1013904223)>>>0;return seed/4294967296;},answer=p.getByRole('textbox',{name:tr('Üç sayı yanıtı'),exact:true});
  for(let i=0;i<24;i++){
   await answer.waitFor();await p.waitForFunction(()=>{const e=document.querySelector('input[aria-label="Üç sayı yanıtı"]');return e&&!e.disabled;},null,{timeout:45000});const digits=Array.from({length:3},()=>Math.floor(random()*10));random();const response=i%2?digits.map(x=>(x+1)%10):digits;
   await answer.fill(response.join(''));await p.getByRole('button',{name:tr('Yanıtı Gönder'),exact:true}).click();run.trials.push({trial:i+1,digits,response,seconds:h.stamp()});save();console.log('DIN',r.assessments.length,i+1,'/24');
  }
  const result=p.locator('[data-hearing-result]');await result.waitFor();await observe('Genuine DIN result',result);
  await p.waitForFunction(ids=>JSON.parse(localStorage.getItem('attune_hearing_history_v1')||'[]').filter(x=>!ids.includes(x.id)).length===1,beforeIds);
  const records=await p.evaluate(()=>JSON.parse(localStorage.getItem('attune_hearing_history_v1')||'[]')),generated=records.filter(x=>!beforeIds.includes(x.id));assert.equal(generated.length,1);run.record=generated[0];run.beforeIds=beforeIds;assert.equal(run.record.validTrials,24);assert.equal(run.record.history.filter(x=>x.correct).length,12);r.result=true;save();
 }
 try{
  await h.record();await h.enter();r.before=await p.evaluate(()=>JSON.parse(localStorage.getItem('attune_hearing_history_v1')||'[]').length);
  await p.evaluate(()=>{const original=crypto.getRandomValues.bind(crypto);crypto.getRandomValues=function(a){const result=original(a);if(a instanceof Uint32Array&&a.length===1)window.__observedDinSeed=a[0];return result;};});
  await observe('Preparation and controlled headset-channel confirmation',p.locator('[data-hearing-page]'));await assessment();await inventory('Live DIN result controls',p.locator('[data-hearing-page]'));await info(p.locator('[data-hearing-page] > div').first().locator('button[aria-haspopup=dialog]'),'Hearing task and limits');
  await act('New Test after completed assessment',p.getByRole('button',{name:tr('Yeni Test'),exact:true}),()=>p.getByRole('button',{name:tr('Ses hazırlığını başlat'),exact:true}).waitFor());assert.equal(await p.evaluate(()=>JSON.parse(localStorage.getItem('attune_hearing_history_v1')||'[]').length),r.before+1);
  await assessment();await referral(h,p.getByRole('link',{name:tr('Hizmet seçenekleri'),exact:true}),'hearing','Live hearing services');
  await p.getByRole('link',{name:tr('Sağlık Geçmişim'),exact:true}).click();const id=r.assessments.at(-1).record.id,row=p.locator('[data-record-id="'+id+'"]');
  await act('Open saved DIN result',row.getByRole('button',{name:tr('Sonucu Aç'),exact:true}),()=>p.getByRole('dialog').waitFor());await inventory('Saved DIN result controls',p.getByRole('dialog'));await observe('Actual saved DIN scores',p.getByRole('dialog'));await info(p.getByRole('dialog').locator('button[aria-haspopup=dialog]'),'Saved hearing information');
  await act('Close saved result',p.getByRole('button',{name:tr('Sonuç penceresini kapat'),exact:true}),()=>p.getByRole('dialog').waitFor({state:'hidden'}));await row.getByRole('button',{name:tr('Sonucu Aç'),exact:true}).click();await referral(h,p.getByRole('dialog').getByRole('link',{name:tr('Uzman seçenekleri'),exact:true}),'hearing','Saved hearing referral');
  for(const run of r.assessments)await deleteSynthetic(h,run.record.id,'hearing');assert.equal(await p.evaluate(()=>JSON.parse(localStorage.getItem('attune_hearing_history_v1')||'[]').length),r.before);
  await p.locator('nav a[href="/"]').click();await observe('Clean cockpit ending',p.locator('main'));r.fullResultCoverage=true;r.remaining=[];r.notApplicable=['Pure-tone audiogram controls: this complete run uses the implemented DIN protocol'];
 }catch(e){error=e;console.error(String(e));process.exitCode=1;}finally{await h.close(error);}
})().catch(e=>{console.error(String(e));process.exitCode=1;});
