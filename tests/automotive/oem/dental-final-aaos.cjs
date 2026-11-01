const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const {open,root}=require('./aaos-harness.cjs');const {deleteSynthetic,referral}=require('./result-coverage.cjs');
(async()=>{
 const poses=['FRONT','RIGHT','LEFT','BITE'],labels=['Ön','Anatomik sağ','Anatomik sol','Kapanış görünümü'];
 const frames=poses.map((v,i)=>fs.readFileSync(path.join(root,`fixtures/dental/0${i+1}_${v}.y4m`))),camera=path.join(root,'runtime/dental-final-camera.y4m');fs.writeFileSync(camera,frames[0]);const fd=fs.openSync(camera,'r+');
 const h=await open('dental',{camera}).catch(e=>{fs.closeSync(fd);throw e;});const {p,r,tr,act,observe,inventory,save}=h;let error;r.capture=[];r.finalCandidate=true;
 async function info(button,label){await act(label,button,()=>p.getByRole('button',{name:tr('Bilgi penceresini kapat'),exact:true}).waitFor());const dialog=p.getByRole('dialog').filter({has:p.getByRole('button',{name:tr('Bilgi penceresini kapat'),exact:true})});await observe(label+' content',dialog);await act(label+' close',dialog.getByRole('button',{name:tr('Bilgi penceresini kapat'),exact:true}),()=>dialog.waitFor({state:'hidden'}));}
 async function scan(){
  fs.writeSync(fd,frames[0],0,frames[0].length,0);let current=0;await p.getByRole('button',{name:tr('Diş Taramasını Başlat'),exact:true}).click();const end=Date.now()+150000;
  while(Date.now()<end&&!await p.locator('[data-dental-result]').count()){
   const capture=p.locator('[data-dental-capture]');if(await capture.count()){const text=await capture.innerText({timeout:800}).catch(()=>''),match=text.match(/\b([1-4])\s*\/\s*4/);if(match){const target=Number(match[1])-1;if(target!==current){fs.writeSync(fd,frames[target],0,frames[target].length,0);current=target;r.capture.push({pose:poses[target],seconds:h.stamp()});save();}}}
   const alerts=(await p.getByRole('alert').allTextContents()).map(x=>x.trim()).filter(Boolean);if(alerts.length)throw Error(alerts.join('\n'));await p.waitForTimeout(600);
  }
  await p.locator('[data-dental-result]').waitFor();assert.equal(await p.locator('[data-dental-result]').getAttribute('data-dental-measured'),'4');r.result=true;save();
 }
 async function details(result,label){
  await inventory(label,result);const overview=result.getByRole('button',{name:tr('Genel bakış'),exact:true});
  await act(label+' overview',overview,()=>result.locator('[data-dental-overview]').waitFor());await observe(label+' generated measurements',result);
  for(let i=0;i<4;i++)await info(result.locator('[data-dental-card] button[aria-haspopup=dialog]').nth(i),label+' explanation '+i);
  for(let i=0;i<4;i++){
   await act(label+' overview pose '+poses[i],result.locator('[data-dental-pose-status^="'+poses[i]+':"]'),()=>result.locator('[data-dental-slide='+poses[i]+']').waitFor());await observe(label+' actual photo '+poses[i],result.locator('[data-dental-slide]'));
   const layers=result.locator('button[data-dental-layer]');for(let j=0;j<await layers.count();j++){
    const button=layers.nth(j),kind=await button.getAttribute('data-dental-layer');await act(label+' '+poses[i]+' '+kind+' on',button,async()=>assert.equal(await button.getAttribute('aria-pressed'),'true'));await observe(label+' selected overlay',result.locator('[data-dental-slide]'),900);await act(label+' '+poses[i]+' '+kind+' off',button,async()=>assert.equal(await button.getAttribute('aria-pressed'),'false'));
   }
   await overview.click();
  }
  await act(label+' views tab',result.getByRole('button',{name:tr('Görünümler'),exact:true}),()=>result.locator('[data-dental-views]').waitFor());
  for(let i=0;i<4;i++)await act(label+' dot '+poses[i],result.getByRole('button',{name:tr(labels[i]),exact:true}),()=>result.locator('[data-dental-slide='+poses[i]+']').waitFor());
  for(let i=2;i>=0;i--)await act(label+' previous '+poses[i],result.getByRole('button',{name:tr('Önceki diş görünümü'),exact:true}),()=>result.locator('[data-dental-slide='+poses[i]+']').waitFor());assert.equal(await result.getByRole('button',{name:tr('Önceki diş görünümü'),exact:true}).isEnabled(),false);
  for(let i=1;i<4;i++)await act(label+' next '+poses[i],result.getByRole('button',{name:tr('Sonraki diş görünümü'),exact:true}),()=>result.locator('[data-dental-slide='+poses[i]+']').waitFor());assert.equal(await result.getByRole('button',{name:tr('Sonraki diş görünümü'),exact:true}).isEnabled(),false);
  await overview.click();r.notApplicable??=[];r.notApplicable.push({label,control:'measurement note',reason:'All four views are measured; no unavailable-view dialog is rendered'});assert.equal(await result.locator('[data-dental-measurement-note]').count(),0);save();
 }
 try{
  await p.getByRole('link',{name:tr('Gizlilik & İzinler'),exact:true}).click();await p.getByRole('checkbox',{name:tr('Yeni diş kayıtlarının fotoğraflarını bu cihazda sakla'),exact:true}).check();await p.locator('nav a[href="/"]').click();
  r.before=await p.evaluate(()=>JSON.parse(localStorage.getItem('attune_dental_history_v1')||'[]').map(x=>x.id));await h.record();await h.enter();await info(p.locator('main button[aria-haspopup=dialog]').first(),'Dental service information');await scan();
  const result=p.locator('[data-dental-result]');await details(result,'Live');const permission=p.getByRole('checkbox',{name:tr('Sayısal sonucu yerel geçmişime kaydet.'),exact:true}),saveButton=p.getByRole('button',{name:tr('Sonucu kaydet'),exact:true});
  await permission.uncheck();assert.equal(await saveButton.isEnabled(),false);await permission.check();await act('Save numerical result and separately consented test photos',saveButton,()=>p.locator('[data-dental-save-status]').waitFor());assert.equal(await p.locator('[data-dental-save-status]').getAttribute('data-dental-save-error'),null);assert.equal(await saveButton.isEnabled(),false);
  r.records=await p.evaluate(()=>JSON.parse(localStorage.getItem('attune_dental_history_v1')||'[]'));const generated=r.records.filter(x=>!r.before.includes(x.id));assert.equal(generated.length,1);r.recordId=generated[0].id;save();
  await act('Clear temporary images',p.getByRole('button',{name:tr('Geçici görüntüleri temizle'),exact:true}),()=>p.getByRole('button',{name:tr('Diş Taramasını Başlat'),exact:true}).waitFor());assert.equal(await result.count(),0);assert.equal(await p.locator('[data-record-id="'+r.recordId+'"]').count(),1);
  await scan();await observe('Second genuine scan proves restart',result);await referral(h,p.getByRole('link',{name:tr('Diş hekimi seçenekleri'),exact:true}),'dental','Live dentist options');
  await p.getByRole('link',{name:tr('Sağlık Geçmişim'),exact:true}).click();const row=p.locator('[data-record-id="'+r.recordId+'"]');await act('Reopen saved result',row.getByRole('button',{name:tr('Sonucu Aç'),exact:true}),()=>p.getByRole('dialog').waitFor());await details(p.getByRole('dialog').locator('[data-dental-result]'),'Saved');await info(p.getByRole('dialog').locator('button[aria-haspopup=dialog]').first(),'Saved record information');
  await act('Close saved result',p.getByRole('button',{name:tr('Sonuç penceresini kapat'),exact:true}),()=>p.getByRole('dialog').waitFor({state:'hidden'}));await row.getByRole('button',{name:tr('Sonucu Aç'),exact:true}).click();await referral(h,p.getByRole('dialog').getByRole('link',{name:tr('Uzman seçenekleri'),exact:true}),'dental','Saved dentist options');
  await deleteSynthetic(h,r.recordId,'dental');await p.locator('nav a[href="/"]').click();await observe('Clean cockpit ending',p.locator('main'));r.fullResultCoverage=true;r.remaining=[];
 }catch(e){error=e;console.error(String(e));process.exitCode=1;}finally{fs.closeSync(fd);await h.close(error);}
})().catch(e=>{console.error(String(e));process.exitCode=1;});

