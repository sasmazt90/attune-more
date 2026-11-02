const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const {open,root,fixtureRoot}=require('./harness.cjs');const {deleteSynthetic,referral}=require('./result-coverage.cjs');
(async()=>{
 const frames=Object.fromEntries(['FRONT','RIGHT','LEFT'].map(k=>[k,fs.readFileSync(path.join(fixtureRoot,'skin-native-input/skin'+k[0]+k.slice(1).toLowerCase()+'.y4m'))]));
 const camera=path.join(root,'runtime/skin-'+process.pid+'.y4m');fs.writeFileSync(camera,frames.FRONT);const fd=fs.openSync(camera,'r+');
 const h=await open('skin',{camera}),{p,r,tr,act,observe,inventory,save}=h;let error;r.camera=[];r.finalCandidate=false;r.computeProfile='Standard 90s server / 95s transport; unchanged weights and quality gates';
 const captureDir=process.env.ATTUNE_QA_CAPTURE_DIR;if(captureDir){fs.mkdirSync(captureDir,{recursive:true});p.on('request',req=>{if(new URL(req.url()).pathname==='/api/local-health/skin'){const body=req.postDataBuffer();if(body)fs.writeFileSync(path.join(captureDir,JSON.parse(body).pose+'.json'),body);}});}
 const button=(name,scope=p)=>scope.getByRole('button',{name:tr(name),exact:true});
 async function closeDialog(label){const d=p.getByRole('dialog').last();await act(label+' close',d.getByRole('button',{name:/^(Close|Close information dialog)$/}),()=>d.waitFor({state:'hidden'}));}
 async function popup(loc,label){await act(label,loc,()=>p.getByRole('dialog').last().waitFor());await inventory(label,p.getByRole('dialog').last());await observe(label+' content',p.getByRole('dialog').last());for(const row of await p.getByRole('dialog').last().locator('[data-skin-unmeasured-item],[data-skin-inconclusive-item]').all())await observe(label+' item',row,650);}
 async function savedModal(){await p.getByRole('link',{name:tr('Sağlık Geçmişim'),exact:true}).click();await act('Open genuine saved Skin record',p.locator('[data-record-id="'+r.recordId+'"]').getByRole('button',{name:tr('Sonucu Aç'),exact:true}),()=>p.getByRole('dialog').waitFor());}
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

 const t=tr,report=r;r.steps=[];r.checks=[];
 const run=async code=>new (Object.getPrototypeOf(async function(){}).constructor)('page',code)(p);
 const shot=async name=>p.screenshot({path:path.join(h.out,name+'.png')});
 const step=async(name,code)=>{await run(code);r.steps.push({name,seconds:h.stamp()});save();};
async function active(){return await run("return await page.evaluate(()=>({view:document.querySelector('[data-skin-region-tab][aria-current=page]')?.getAttribute('data-skin-region-tab'),photo:document.querySelector('[data-skin-snapshot]')?.getAttribute('data-snapshot-photoid'),sourcePose:document.querySelector('[data-skin-snapshot]')?.getAttribute('data-snapshot-angle'),crop:document.querySelector('[data-skin-snapshot]')?.getAttribute('viewBox'),empty:document.querySelector('[data-skin-findings-empty]')?.getAttribute('data-skin-findings-empty'),card:document.querySelector('[data-skin-finding-card]')?.getAttribute('data-skin-finding-card'),callouts:document.querySelectorAll('[data-skin-callout]').length,connectors:document.querySelectorAll('[data-skin-callout-connectors] line').length}));");}
const order=['overview','forehead','periorbital','rightCheek','leftCheek','chin'];
async function walk(label){
 await p.locator('[data-skin-region-tab][aria-current=page]').waitFor();
 for(const direction of [1,-1])for(let i=0;i<6;i++){
  const before=await active();await run(`await page.locator('[data-health-result-navigation]').getByRole('button',{name:${JSON.stringify(t(direction>0?'Sonraki bölge':'Önceki bölge'))},exact:true}).click(); return {};`);
  assert(order.includes(before.view), 'selected tab is a valid anatomical region');const expected=order[(order.indexOf(before.view)+direction+6)%6];await p.locator('[data-skin-region-tab='+expected+'][aria-current=page]').waitFor();const state=await active();assert.equal(state.view,expected);report.checks.push({label,direction,...state});save();
 }
 for(const view of order){
  await run(`await page.locator('[data-skin-region-tab=${view}]').click(); return {};`);const state=await active();assert.equal(state.view,view);
  assert.equal(state.photo,report.record.captures[state.sourcePose].captureId,'selected finding photo belongs to this admitted session and pose'); if(view==='periorbital'&&state.card)assert(state.callouts>0,'eye finding has its own source-bound callout');
  report.checks.push({label,tab:view,...state});await shot(label+'-'+view);
  const callouts=await run("return await page.locator('[data-skin-callout]').evaluateAll(es=>es.map(e=>e.getAttribute('data-skin-callout')));");
  for(const key of callouts){const id=key.split(':')[1];const selected=await run(`await page.locator('[data-skin-callout="${key}"]').click(); return {pressed:await page.locator('[data-skin-callout="${key}"]').getAttribute('aria-pressed'),card:await page.locator('[data-skin-finding-card]').count()?await page.locator('[data-skin-finding-card]').getAttribute('data-skin-finding-card'):null,overview:await page.locator('[data-skin-overview-finding=${id}]').count()?await page.locator('[data-skin-overview-finding=${id}]').getAttribute('aria-pressed'):null};`);assert.equal(selected.pressed,'true');assert.equal(view==='overview'?selected.overview:selected.card,view==='overview'?'true':id);report.checks.push({label,callout:key,...selected});save();}
  if(await run("return await page.locator('[data-skin-open-recommendations]').count();")){
   await run("await page.locator('[data-skin-open-recommendations]').click(); return {};");
   const rec=await run("return {finding:await page.locator('[data-skin-recommendations]').getAttribute('data-skin-recommendations'),text:await page.getByRole('dialog').innerText()};");assert(rec.finding&&rec.text.length>40);report.checks.push({label,recommendations:rec.finding});await shot(label+'-recommendations-'+view);
   await run("await page.locator('[data-skin-recommendations] button').click(); return {};");
  }
  const next=await run(`return await page.getByRole('button',{name:${JSON.stringify(t('Sonraki bulgu'))},exact:true}).count();`);
  if(next){const a=await active();await run(`await page.getByRole('button',{name:${JSON.stringify(t('Sonraki bulgu'))},exact:true}).click(); return {};`);assert.equal((await active()).view,view);report.checks.push({label,innerFindingNavigation:true,before:a,after:await active()});}
 }
 await run("await page.locator('[data-skin-region-tab=overview]').click(); await page.keyboard.press('ArrowRight'); return {};");assert.equal((await active()).view,'forehead');await run("await page.keyboard.press('ArrowLeft'); return {};");assert.equal((await active()).view,'overview');
 for(const selector of ['[data-skin-findings-unmeasured]','[data-skin-findings-inconclusive]']){
  if(!await run(`return await page.locator('${selector}').count();`))continue;
  await run(`await page.locator('${selector}').click(); return {};`);await shot(label+'-measurement-details');await run("await page.getByRole('dialog').getByRole('button',{name:/^Close$|^Close information dialog$/}).click(); return {};");
 }
}
 try{
  await p.getByRole('link',{name:tr('Gizlilik & İzinler'),exact:true}).click();for(const name of ['Cilt ölçümlerini ve kişisel sayısal referansı bu tarayıcıda sakla','Yeni cilt kayıtlarının fotoğraflarını bu cihazda sakla']){const box=p.getByRole('checkbox',{name:tr(name),exact:true});if(!await box.isChecked())await box.click();await p.waitForFunction(label=>[...document.querySelectorAll('label')].find(e=>e.textContent.trim()===label)?.querySelector('input')?.checked,tr(name));};await p.locator('nav a[href="/"]').click();
  r.before=await p.evaluate(()=>JSON.parse(localStorage.getItem('togg_health_skin_history')||'[]').map(x=>x.id));await h.record();await h.enter();
  await popup(p.locator('main button[aria-haspopup=dialog]').first(),'Skin preparation information');const three=p.getByRole('checkbox',{name:tr('Üç açılı tarama'),exact:true});assert(await three.isChecked());await closeDialog('Skin preparation');
  await button('Analizi Başlat').click();let pose='FRONT';const end=Date.now()+780000;
  while(Date.now()<end&&!await p.locator('[data-skin-result]').count()){
   const canvas=p.locator('canvas[data-angle]');const data=await canvas.evaluate(e=>({...e.dataset}));const target=data.angle;if(frames[target]&&target!==pose){fs.writeSync(fd,frames[target],0,frames[target].length,0);pose=target;console.log('Skin',pose);}
   r.camera.push({pose,data,seconds:h.stamp()});r.current=await p.locator('main').innerText();save();if(r.current.includes(tr('Cilt Sağlığı Başlatılamadı')))throw Error(r.current);await p.waitForTimeout(1000);
  }
  await p.locator('[data-skin-result]').waitFor();r.result=true;assert.equal(r.responses.filter(x=>x.path==='/api/local-health/skin'&&x.status===200).length,3);
 report.record=await run("return await page.evaluate(()=>JSON.parse(localStorage.getItem('togg_health_latest_skin')||'null'));");assert(report.record?.id);assert.equal(Object.keys(report.record.captures).length,3);save();
 await walk('live');
 await run("await page.setViewportSize({width:390,height:844}); return {};");await shot('mobile');report.mobile=await run("return await page.evaluate(()=>({overflow:document.documentElement.scrollWidth>innerWidth,photoWidth:document.querySelector('[data-face-panel]')?.getBoundingClientRect().width}));");assert(!report.mobile.overflow);await run("await page.setViewportSize({width:1920,height:1080}); return {};");
 await step('Rescan from result',"await page.locator('[data-skin-rescan]').click(); await page.getByRole('button',{name:'Start analysis',exact:true}).waitFor()");
 await step('Cancel reassessment without saving',`await page.getByRole('button',{name:'Start analysis',exact:true}).click(); await page.getByRole('button',{name:${JSON.stringify(t('Taramayı İptal Et'))},exact:true}).click()`);
 report.afterCancel=await run("return await page.evaluate(()=>JSON.parse(localStorage.getItem('togg_health_skin_history')||'[]').map(r=>r.id));");assert.deepEqual(report.afterCancel,[report.record.id]);report.checks.push({reassessmentCancelPreservedOnlyAcceptedRecord:true});save();
 await step('Open health history',"await page.getByRole('link',{name:'My Health History',exact:true}).click()");
 await step('Open saved comparison',`await page.locator('[data-record-id="${report.record.id}"]').getByRole('button',{name:${JSON.stringify(t('Sonucu Aç'))},exact:true}).click()`);
 await step('Reopen exact saved result',"await page.locator('[data-skin-open-result]').click()");await walk('saved');
 await step('Specialist options',`await page.getByRole('button',{name:${JSON.stringify(t('Uzman seçenekleri'))},exact:true}).click()`);report.specialist=await run("return {url:page.url()};");await shot('specialist');
 await step('Delete history row',`await page.getByRole('link',{name:'My Health History',exact:true}).click(); await page.locator('[data-record-id="${report.record.id}"]').getByRole('button',{name:/delete/i}).click()`);
 await step('Confirm delete',`await page.getByRole('dialog').getByRole('button',{name:${JSON.stringify(t('Evet, sil'))},exact:true}).click(); await page.locator('[data-record-id="${report.record.id}"]').waitFor({state:'detached'})`);
 await h.seal();await run("await page.reload(); return {};");report.afterDelete=await run(`return await page.evaluate(id=>({survives:JSON.parse(localStorage.getItem('togg_health_skin_history')||'[]').some(r=>r.id===id)}),${JSON.stringify(report.record.id)});`);assert.equal(report.afterDelete.survives,false);await shot('deleted');

 assert.equal(r.errors.length,0);
 assert(!r.responses.some(x=>x.status>=500));r.recordId=r.record.id;
 const replies=r.responses.filter(x=>x.path==='/api/local-health/skin'&&x.status===200);
 r.concordance=Object.fromEntries(Object.entries(r.record.captures).map(([pose,c])=>{
   const reply=replies.find(x=>x.body.photoId===c.captureId);
   assert(reply,pose+' capture ID must resolve to one actual backend measurement');
   return [pose,{captureId:c.captureId,sourceWidth:reply.body.sourceWidth,sourceHeight:reply.body.sourceHeight,measurements:Object.keys(reply.body.measurements)}];
 }));
 r.fullResultCoverage=true;r.pass=true;save();
 }catch(e){error=e;console.error(String(e));process.exitCode=1;}finally{fs.closeSync(fd);await h.close(error);}
})().catch(e=>{console.error(String(e));process.exitCode=1;});


