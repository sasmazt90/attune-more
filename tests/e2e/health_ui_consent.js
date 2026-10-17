async page=>{
 const assert=(x,m)=>{if(!x)throw Error(m)},rows=[];let requests=[];
 await page.addInitScript(()=>{window.mediaAttempts=0;navigator.mediaDevices.getUserMedia=()=>{window.mediaAttempts++;throw Error('Physical hardware forbidden')};});
 await page.route('**/api/mental/speech',r=>r.fulfill({status:503,json:{detail:'CONTROLLED_TTS_FAILURE'}}));
 page.on('request',r=>{if(r.url().includes('/api/')&&!r.url().includes('/api/vehicle/'))requests.push(new URL(r.url()).pathname)});
 const authorize=async()=>{const modal=page.getByRole('dialog');for(const box of await modal.getByRole('checkbox').all()){assert(!await box.isChecked(),'Consent prechecked');await box.check();}await modal.getByRole('button',{name:'İzin ver ve devam et'}).click();await modal.waitFor({state:'detached'});};
 for(const [id,name] of [['skin','Cilt Sağlığı'],['vision','Göz Sağlığı'],['dental','Diş Sağlığı'],['hearing','İşitme Sağlığı'],['mental','Ruh Sağlığı']]){
  requests=[];await page.goto('http://127.0.0.1:3308/'+id);await page.getByRole('dialog').waitFor();const beforeConsentCalls=requests.length;assert(beforeConsentCalls===0,'Health request before consent');
  const boxes=await page.getByRole('dialog').getByRole('checkbox').count();assert(await page.getByRole('button',{name:'İzin ver ve devam et'}).isDisabled(),'Ungated permission');assert(await page.evaluate(()=>mediaAttempts)===0,'Media before consent');
  await authorize();assert(await page.evaluate(()=>mediaAttempts)===0,'Consent auto-started media');
  await page.reload();await page.waitForTimeout(350);assert(await page.getByRole('dialog').count()===0,'Repeated modal after reload');
  await page.goto('http://127.0.0.1:3308/');await page.goto('http://127.0.0.1:3308/'+id);await page.waitForTimeout(250);assert(await page.getByRole('dialog').count()===0,'Repeated modal on reentry');
  const other=await page.context().newPage();await other.goto('http://127.0.0.1:3308/privacy');const row=other.locator('[data-service-settings]>div').filter({has:other.getByRole('heading',{name,exact:true})});await row.getByRole('button',{name:'İzni kaldır'}).click();await page.getByRole('dialog').waitFor();
  assert(await page.evaluate(()=>mediaAttempts)===0,'Revocation leaked media');await other.close();
  rows.push({module:id,checkboxes:boxes,beforeConsentCalls,firstEntry:true,unchecked:true,consentNoAutostart:true,reload:true,reentry:true,crossTabPrivacyRevoke:true});
  await page.getByRole('button',{name:'Şimdi değil'}).click();await page.waitForURL('http://127.0.0.1:3308/');
 }
 await page.goto('http://127.0.0.1:3308/dental');await page.getByRole('dialog').waitFor();
 await page.evaluate(()=>{const old=Storage.prototype.setItem;Storage.prototype.setItem=function(k,v){if(k==='attune_health_processing_v1')throw new DOMException('Test storage failure','QuotaExceededError');return old.call(this,k,v)}});
 await page.getByRole('dialog').getByRole('checkbox').check();await page.getByRole('button',{name:'İzin ver ve devam et'}).click();await page.getByRole('alert').filter({hasText:'İzin kaydedilemedi'}).waitFor();
 assert(await page.getByRole('dialog').count()===1,'Storage failure opened app');assert(await page.evaluate(()=>mediaAttempts)===0,'Storage failure started media');
 const proof={rows,storageFailureClosed:true,denialSafeExit:true,physicalMediaAttempts:0,healthCallsBeforeConsent:Math.max(...rows.map(r=>r.beforeConsentCalls))};
 const d=page.waitForEvent('download');await page.evaluate(v=>{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(v)],{type:'application/json'}));a.download='consent-proof.json';a.click()},proof);await(await d).saveAs('../cdc-progress/health-ui-consent-audio-followup-20261017/consent-proof.json');return proof;
}
