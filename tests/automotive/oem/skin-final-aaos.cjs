const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const {open,root}=require('./aaos-harness.cjs');const {deleteSynthetic,referral}=require('./result-coverage.cjs');
(async()=>{
 const frames=Object.fromEntries(['FRONT','RIGHT','LEFT'].map(k=>[k,fs.readFileSync(path.join(root,'fixtures/skin-anbox-input/skin'+k[0]+k.slice(1).toLowerCase()+'.y4m'))]));
 const camera=path.join(root,'runtime/skin-final-camera.y4m');fs.writeFileSync(camera,frames.FRONT);const fd=fs.openSync(camera,'r+');
 const h=await open('skin',{camera}),{p,r,tr,act,observe,inventory,save}=h;let error;r.camera=[];r.finalCandidate=true;r.computeProfile='extended-cpu: 180s server / 185s transport, cancellation and quality unchanged';
 const button=(name,scope=p)=>scope.getByRole('button',{name:tr(name),exact:true});
 async function closeDialog(label){const d=p.getByRole('dialog').last();await act(label+' close',d.getByRole('button',{name:/^(Kapat|Bilgi penceresini kapat)$/}),()=>d.waitFor({state:'hidden'}));}
 async function popup(loc,label){await act(label,loc,()=>p.getByRole('dialog').last().waitFor());await inventory(label,p.getByRole('dialog').last());await observe(label+' content',p.getByRole('dialog').last());for(const row of await p.getByRole('dialog').last().locator('[data-skin-unmeasured-item],[data-skin-inconclusive-item]').all())await observe(label+' item',row,650);}
 async function savedModal(){await p.getByRole('link',{name:'Sağlık Geçmişim',exact:true}).click();await act('Open genuine saved Skin record',p.locator('[data-record-id="'+r.recordId+'"]').getByRole('button',{name:'Sonucu Aç',exact:true}),()=>p.getByRole('dialog').waitFor());}
 async function reopen(){await savedModal();await act('Open saved result screen',p.locator('[data-skin-open-result]'),()=>p.locator('[data-skin-result]').waitFor());}
 async function care(loc,label){await act(label,loc,()=>p.waitForURL('**/care**'));assert.equal(new URL(p.url()).searchParams.get('from'),'skin');await observe(label+' real destination',p.locator('main'));r.referrals??=[];r.referrals.push({label,seconds:h.stamp(),url:p.url()});save();}
 async function dateRange(loc,label,full){
  await popup(loc,label);const d=p.getByRole('dialog'),heading=d.locator('[data-skin-date-range]');
  for(const name of ['Son 30 gün','Son 3 ay','Son 6 ay','Tümü'])await act(label+' '+name,button(name,d),async()=>assert((await heading.innerText()).length>10));
  const before=await d.innerText();await act(label+' previous month',button('Önceki ay',d),async()=>assert.notEqual(await d.innerText(),before));await act(label+' next month',button('Sonraki ay',d),async()=>assert.equal(await d.innerText(),before));
  const days=d.getByRole('button',{name:/^\d{1,2}$/,exact:true});const count=await days.count();
  if(full){for(let i=0;i<count;i++)if(await days.nth(i).isEnabled())await act(label+' day '+await days.nth(i).innerText(),days.nth(i),async()=>assert.equal(await days.nth(i).getAttribute('aria-pressed'),'true'));}
  else{const first=days.first();await act(label+' start day',first,async()=>assert.equal(await first.getAttribute('aria-pressed'),'true'));}
  await act(label+' apply',button('Uygula',d),()=>d.waitFor({state:'hidden'}));await popup(loc,label+' reopen');await closeDialog(label+' cancel');
 }
 async function details(label){
  const result=p.locator('[data-skin-result]');await inventory(label,result);const ids=await result.locator('[data-skin-region-tab]').evaluateAll(es=>es.map(e=>e.dataset.skinRegionTab));let testedCalendar=false;
  for(const id of ids){
   await act(label+' view '+id,result.locator('[data-skin-region-tab="'+id+'"]'),async()=>assert.equal(await result.locator('[data-skin-region-tab="'+id+'"]').getAttribute('aria-current'),'page'));
   await observe(label+' '+id,result);
   if(id==='overview'){
    const type=result.locator('[data-skin-type-card]');if(await type.count())await act(label+' skin type',type,async()=>assert.equal(await type.getAttribute('aria-pressed'),'true'));
    const maps=result.locator('[data-skin-type-region][role=button],[data-skin-type-tag][role=button]');
    for(let i=0;i<await maps.count();i++){await popup(maps.nth(i),label+' mapped region '+i);await closeDialog(label+' map');}
    const page=result.locator('[data-skin-overview-page]'),pages=await page.count()?Number((await page.innerText()).split('/')[1]):1;
    for(let n=0;n<pages;n++){
     const cards=result.locator('[data-skin-overview-finding]');for(let j=0;j<await cards.count();j++){const c=cards.nth(j);await act(label+' finding '+await c.getAttribute('data-skin-overview-finding'),c,async()=>assert.equal(await c.getAttribute('aria-pressed'),'true'));await observe(label+' selected finding map',result.locator('[data-skin-result-layout]'));const rec=result.locator('[data-skin-open-recommendations]');if(await rec.count()){await popup(rec,label+' recommendations');await closeDialog(label+' recommendations');}await act(label+' deselect finding',c,async()=>assert.equal(await c.getAttribute('aria-pressed'),'false'));}
     if(pages>1){const old=await page.innerText();await act(label+' next overview page',button('Sonraki bulgular',result),async()=>assert.notEqual(await page.innerText(),old));}
    }
    if(pages>1){const old=await page.innerText();await act(label+' previous overview page',button('Önceki bulgular',result),async()=>assert.notEqual(await page.innerText(),old));await button('Sonraki bulgular',result).click();}else{assert.equal(await button('Önceki bulgular',result).isEnabled(),false);assert.equal(await button('Sonraki bulgular',result).isEnabled(),false);}
   }else{
    const seen=new Set();for(let n=0;n<30;n++){
     const card=result.locator('[data-skin-finding-card]');if(!await card.count())break;const fid=await card.getAttribute('data-skin-finding-card');if(seen.has(fid))break;seen.add(fid);await inventory(label+' '+id+' '+fid,card);await observe(label+' real finding '+fid,card);
     const expand=card.locator('[data-skin-acne-subtypes] > button');if(await expand.count()){await act(label+' expand acne subtypes',expand,async()=>assert.equal(await expand.getAttribute('aria-expanded'),'true'));const types=card.locator('[data-skin-acne-subtype] button');for(let j=0;j<await types.count();j++){const t=types.nth(j);if(await t.isEnabled()){await act(label+' acne subtype '+j,t,async()=>assert.equal(await t.getAttribute('aria-pressed'),'true'));await observe(label+' selected subtype map',result.locator('[data-skin-result-layout]'));await act(label+' clear subtype '+j,t,async()=>assert.equal(await t.getAttribute('aria-pressed'),'false'));}}await act(label+' collapse subtypes',expand,async()=>assert.equal(await expand.getAttribute('aria-expanded'),'false'));}
     const range=card.locator('[data-skin-history-range]');if(await range.count()){await dateRange(range,label+' '+id+' '+fid+' history',!testedCalendar);testedCalendar=true;}
     const rec=result.locator('[data-skin-open-recommendations]');if(await rec.count()){await popup(rec,label+' '+fid+' advice');await closeDialog(label+' advice');}
     const next=button('Sonraki bulgu',result),prev=button('Önceki bulgu',result);if(!await next.isEnabled()){assert.equal(await prev.isEnabled(),false);break;}
     const old=await card.getAttribute('data-skin-finding-card');await act(label+' previous finding',prev,async()=>assert.notEqual(await card.getAttribute('data-skin-finding-card'),old));await next.click();await act(label+' next finding',next,async()=>assert.notEqual(await card.getAttribute('data-skin-finding-card'),old));
    }
   }
   for(const selector of ['[data-skin-findings-inconclusive]','[data-skin-findings-unmeasured]']){const loc=result.locator(selector);if(await loc.count()){await popup(loc,label+' '+id+' uncertainty');await closeDialog(label+' uncertainty');}}
  }
  await result.locator('[data-skin-region-tab=overview]').click();save();
 }
 try{
  await p.getByRole('link',{name:'Gizlilik & İzinler',exact:true}).click();for(const name of ['Cilt ölçümlerini ve kişisel sayısal referansı bu tarayıcıda sakla','Yeni cilt kayıtlarının fotoğraflarını bu cihazda sakla'])await p.getByRole('checkbox',{name,exact:true}).check();await p.locator('nav a[href="/"]').click();
  r.before=await p.evaluate(()=>JSON.parse(localStorage.getItem('togg_health_skin_history')||'[]').map(x=>x.id));await h.record();await h.enter();
  await popup(p.locator('main button[aria-haspopup=dialog]').first(),'Skin preparation information');const three=p.getByRole('checkbox',{name:'Üç açılı tarama',exact:true});assert(await three.isChecked());await closeDialog('Skin preparation');
  await button('Analizi Başlat').click();let pose='FRONT';const end=Date.now()+780000;
  while(Date.now()<end&&!await p.locator('[data-skin-result]').count()){
   const canvas=p.locator('canvas[data-angle]');const data=await canvas.evaluate(e=>({...e.dataset}));const target=data.angle;if(frames[target]&&target!==pose){fs.writeSync(fd,frames[target],0,frames[target].length,0);pose=target;console.log('Skin',pose);}
   r.camera.push({pose,data,seconds:h.stamp()});r.current=await p.locator('main').innerText();save();if(r.current.includes('Cilt Sağlığı Başlatılamadı'))throw Error(r.current);await p.waitForTimeout(1000);
  }
  await p.locator('[data-skin-result]').waitFor();r.result=true;assert.equal(r.responses.filter(x=>x.path==='/api/local-health/skin'&&x.status===200).length,3);
  r.records=await p.evaluate(()=>JSON.parse(localStorage.getItem('togg_health_skin_history')||'[]'));const generated=r.records.filter(x=>!r.before.includes(x.id));assert.equal(generated.length,1);r.recordId=generated[0].id;save();await details('Live');
  await care(button('Uzman seçenekleri',p.locator('[data-skin-result]')),'Live dermatologist options');await savedModal();await inventory('Saved Skin comparison',p.getByRole('dialog'));await observe('Actual comparison',p.getByRole('dialog'));
  const expand=p.getByRole('dialog').locator('button[aria-expanded]');if(await expand.count()){await act('Expand saved unavailable findings',expand,async()=>assert.equal(await expand.getAttribute('aria-expanded'),'true'));await observe('Saved unavailable causes',p.getByRole('dialog'));await act('Collapse saved unavailable findings',expand,async()=>assert.equal(await expand.getAttribute('aria-expanded'),'false'));}
  await popup(p.getByRole('dialog').locator('button[aria-haspopup=dialog]'),'Saved record information');await button('Bilgi penceresini kapat').click();
  await act('Close saved comparison',button('Sonuç penceresini kapat'),()=>p.getByRole('dialog').waitFor({state:'hidden'}));await savedModal();await referral(h,p.getByRole('dialog').getByRole('link',{name:'Uzman seçenekleri',exact:true}),'skin','Saved comparison referral');await reopen();await details('Saved');
  // The recommendation dialog has its own distinct referral action.
  const finding=p.locator('[data-skin-overview-finding]').first();if(await finding.count()){await finding.click();await popup(p.locator('[data-skin-open-recommendations]'),'Recommendation specialist action');await care(button('Uzman seçenekleri',p.getByRole('dialog')),'Recommendation dermatologist options');await reopen();}
  const unclear=p.locator('[data-skin-findings-inconclusive]');if(await unclear.count()){await popup(unclear,'Retry inconclusive scan');await act('Restart scan',button('Tekrar tara',p.getByRole('dialog')),()=>button('Analizi Başlat').waitFor());await button('Analizi Başlat').click();await act('Cancel new scan after restart',button('Taramayı İptal Et'),()=>button('Analizi Başlat').waitFor());}else{r.notApplicable=['Rescan action is conditionally rendered only for inconclusive findings; absent from this measured result'];}
  await deleteSynthetic(h,r.recordId,'skin');await p.locator('nav a[href="/"]').click();await observe('Clean cockpit ending',p.locator('main'));r.fullResultCoverage=true;r.remaining=[];
 }catch(e){error=e;console.error(String(e));process.exitCode=1;}finally{fs.closeSync(fd);await h.close(error);}
})().catch(e=>{console.error(String(e));process.exitCode=1;});

