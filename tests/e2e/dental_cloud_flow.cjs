// Cloud E2E for Diş Sağlığı: fake-camera (y4m) FRONT→RIGHT→LEFT→BITE through the
// real MediaPipe gate, real backend + real ONNX, explicit save, history reopen.
// Synthetic inputs prove workflow only; they are not clinical evidence.
// Usage: node tests/e2e/dental_cloud_flow.cjs <y4m> <outDir> [mode]
//   mode: camera (default) | gate-trace | upload:<file> | lifecycle
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path');
const [,,fixture,out,mode='camera']=process.argv;
const BASE=process.env.DENTAL_BASE||'http://127.0.0.1:3310';
const assert=(x,m)=>{if(!x)throw Error('ASSERT: '+m);};
fs.mkdirSync(out,{recursive:true});
(async()=>{
 const browser=await chromium.launch({args:['--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream',...(fixture&&fixture!=='-'?['--use-file-for-fake-video-capture='+fixture]:[]),'--enable-unsafe-swiftshader']});
 const context=await browser.newContext({viewport:{width:1280,height:900},permissions:['camera']});
 const page=await context.newPage();const log=[];
 page.on('console',m=>{if(m.type()==='error')log.push('console:'+m.text());});
 page.on('pageerror',e=>log.push('pageerror:'+e.message));
 await page.addInitScript(()=>{window.__dental={requests:[],responses:[],status:[],captures:[]};const native=window.fetch;window.fetch=async(...a)=>{const url=String(a[0]);const hit=/\/api\/local-health\/dental(-upload)?/.test(url);if(hit)__dental.requests.push({url,at:performance.now(),body:JSON.parse(a[1].body)});const r=await native(...a);if(hit)__dental.responses.push({url,status:r.status,body:await r.clone().json().catch(()=>null)});return r;};
  const t0=performance.now();setInterval(()=>{const s=document.querySelector('[data-dental-page] [role=status]')?.textContent||'';const step=document.querySelector('[data-dental-step]')?.getAttribute('data-dental-step')||'';const last=__dental.status[__dental.status.length-1];if(!last||last.s!==s||last.step!==step)__dental.status.push({t:Math.round(performance.now()-t0),s,step});},100);});
 if(mode==='partial-response'){
  // Real backend response; the BITE view is rewritten into the backend's own
  // "insufficient" shape (as returned for a blurred frame) to check the UI path.
  await page.route('**/api/local-health/dental',async route=>{const response=await route.fetch();const body=await response.json();const v=body.views[body.views.length-1];
   v.quality={...v.quality,valid:false,reasons:['BLURRY']};
   v.caries={...v.caries,value:null,quality:'insufficient',limitationCode:'CAPTURE_QUALITY',candidates:[]};
   v.accumulation={...v.accumulation,value:null,quality:'insufficient',limitationCode:'CAPTURE_QUALITY',candidates:[]};
   v.alignment={...v.alignment,value:null,quality:'insufficient',limitationCode:'CAPTURE_QUALITY',rows:null,contours:[]};
   await route.fulfill({response,json:body});});
 }
 const t0=Date.now();
 await page.goto(BASE+'/dental');
 const consent=page.getByRole('dialog');
 await consent.waitFor({timeout:15000}).catch(()=>{});
 if(await consent.count()){await consent.getByRole('checkbox').first().check();await page.getByRole('button',{name:'İzin ver ve devam et'}).click();}
 if(mode!=='no-photo-permission'){
  await page.goto(BASE+'/privacy');const permission=page.getByLabel('Yeni diş kayıtlarının fotoğraflarını bu cihazda sakla',{exact:true});
  await page.waitForLoadState('networkidle');if(await permission.count()&&!await permission.isChecked()){await permission.click();await page.waitForFunction(()=>localStorage.getItem('attune_privacy_dental_photos_allowed')==='true',null,{timeout:10000});}
  await page.goto(BASE+'/dental');
  await page.getByRole('dialog').waitFor({timeout:4000}).then(async()=>{const d=page.getByRole('dialog');await d.getByRole('checkbox').first().check();await page.getByRole('button',{name:'İzin ver ve devam et'}).click();}).catch(()=>{});
 }
 await page.waitForFunction(()=>document.querySelector('[data-vehicle-status]')?.textContent==='PARK',null,{timeout:30000});
 await page.screenshot({path:path.join(out,'01-ready.png'),fullPage:true});
 const result={mode,fixture};
 if(mode.startsWith('upload:')){
  const file=mode.slice(7);
  await page.locator('input[type=file]').setInputFiles(file);
  await page.locator('[data-dental-result],[data-dental-page] [role=alert]').first().waitFor({timeout:90000});
 }else{
  await page.getByRole('button',{name:'Diş Taramasını Başlat',exact:true}).click();
  if(mode==='skip-bite'){
   // Open-mouth frames only at the BITE step: must never be accepted as a bite.
   const t=Date.now();await page.locator('[data-dental-skip-bite]').waitFor({timeout:150000});result.skipVisibleAfterMs=Date.now()-t;
   result.beforeSkip=await page.evaluate(()=>({requests:__dental.requests.length,step:document.querySelector('[data-dental-step]')?.getAttribute('data-dental-step')}));
   await page.locator('[data-dental-skip-bite]').click();
  }
  if(mode==='revoke-consent'||mode==='park-change'||mode==='revoke-camera'){
   // Wait for the first accepted pose, then withdraw while capture continues.
   await page.waitForFunction(()=>/Başınızı kendi sağınıza/.test(document.querySelector('[data-dental-page] [role=status]')?.textContent||''),null,{timeout:120000});
   if(mode==='revoke-consent'){const other=await context.newPage();await other.goto(BASE+'/privacy');await other.evaluate(()=>{const raw=JSON.parse(localStorage.getItem('attune_health_processing_v1'));delete raw.services.dental;localStorage.setItem('attune_health_processing_v1',JSON.stringify(raw));});await other.close();}
   if(mode==='park-change')await page.evaluate(()=>fetch('http://127.0.0.1:8310/api/vehicle/toggle',{method:'POST'}));
   if(mode==='revoke-camera'){const other=await context.newPage();await other.goto(BASE+'/privacy');await other.evaluate(()=>{localStorage.setItem('attune_privacy_camera_allowed','false');});await other.close();}
   await page.waitForTimeout(45000);
   result.afterWithdrawal=await page.evaluate(()=>({requests:__dental.requests.length,status:document.querySelector('[data-dental-page] [role=status]')?.textContent,video:!!document.querySelector('[data-dental-live-video]'),tracks:document.querySelector('[data-dental-live-video]')?.srcObject?.getTracks().map(t=>t.readyState)}));
   console.log('AFTER_WITHDRAWAL',JSON.stringify(result.afterWithdrawal));
   if(mode==='park-change')await page.evaluate(()=>fetch('http://127.0.0.1:8310/api/vehicle/toggle',{method:'POST'}));
  }
  await page.waitForTimeout(4000);await page.screenshot({path:path.join(out,'02-camera.png'),fullPage:true});
  await page.locator('[data-dental-result],[data-dental-page] [role=alert]').first().waitFor({timeout:Number(process.env.DENTAL_CAMERA_TIMEOUT||240000)}).catch(()=>{});
 }
 result.elapsedMs=Date.now()-t0;
 const data=await page.evaluate(()=>({responses:__dental.responses.map(r=>({url:r.url,status:r.status,views:r.body?.views?.map(v=>({pose:v.pose,photoId:v.photoId,valid:v.quality?.valid,reasons:v.quality?.reasons,caries:v.caries?.value,cariesQuality:v.caries?.quality,accumulation:v.accumulation?.value,accumulationQuality:v.accumulation?.quality,alignment:v.alignment?.value,alignmentQuality:v.alignment?.quality,alignmentLimit:v.alignment?.limitationCode,opening:v.quality?.mouthOpeningRatio})),detail:r.body?.detail})),requests:__dental.requests.map(r=>({url:r.url,poses:r.body.captures?.map(c=>({pose:c.pose,photoId:c.photoId,w:c.width,h:c.height,landmarks:c.landmarks?.length,conditions:c.conditions}))})),status:__dental.status}));
 Object.assign(result,data);
 const resultVisible=await page.locator('[data-dental-result]').count();result.resultVisible=resultVisible;
 await page.screenshot({path:path.join(out,'03-result.png'),fullPage:true});
 if(resultVisible&&process.env.DENTAL_SAVE!=='0'){
  // explicit save
  const box=page.getByRole('checkbox',{name:/kaydet/i}).first();if(await box.count())await box.check();
  const save=page.getByRole('button',{name:'Sonucu kaydet'});if(await save.count()){await save.click();await page.waitForTimeout(1500);}
  result.afterSave=await page.locator('[data-dental-page] [role=status]').first().textContent();
  result.history=await page.evaluate(()=>JSON.parse(localStorage.getItem('attune_dental_history_v1')||'[]').map(r=>({id:r.id,views:r.measurements?.map(m=>({pose:m.pose,photoId:m.photoId,caries:m.caries?.value}))})));
  await page.screenshot({path:path.join(out,'04-saved.png'),fullPage:true});
 }
 if(resultVisible&&process.env.DENTAL_SCREENS!=='0'){
  // Result tabs, each pose slide, a single-layer filter and the reopened record.
  await page.locator('[data-dental-result]').first().scrollIntoViewIfNeeded();
  await page.locator('[data-dental-result]').first().screenshot({path:path.join(out,'05-overview.png')});
  await page.getByRole('button',{name:'Görünümler',exact:true}).first().click();
  const slides=await page.locator('[data-dental-result] [aria-roledescription=carousel] .'+'x').count();
  result.slides=[];
  for(let i=0;i<4;i++){
   const slide=page.locator('[data-dental-slide]').first();if(!await slide.count())break;
   const info=await slide.evaluate(e=>({pose:e.getAttribute('data-dental-slide'),status:e.getAttribute('data-dental-slide-status'),crop:e.querySelector('[data-dental-crop]')?.getAttribute('data-dental-crop'),photo:e.querySelector('[data-dental-photo]')?.getAttribute('data-dental-photo'),href:(e.querySelector('image')?.getAttribute('href')||'').slice(0,64),marks:[...e.querySelectorAll('[data-dental-mark]')].map(m=>m.getAttribute('data-dental-mark'))}));
   result.slides.push(info);
   await page.locator('[data-dental-result]').first().screenshot({path:path.join(out,`06-view-${i}-${info.pose}.png`)});
   if(i===3||info.pose==='BITE'){const row=page.locator('[data-dental-layer=caries]').first();if(await row.count()){await row.click();await page.locator('[data-dental-result]').first().screenshot({path:path.join(out,`07-view-${info.pose}-caries-only.png`)});result.cariesOnly=await page.locator('[data-dental-slide] [data-dental-mark]').evaluateAll(a=>a.map(m=>m.getAttribute('data-dental-mark')));await row.click();}}
   const next=page.getByRole('button',{name:'Sonraki diş görünümü'});if(!await next.count()||await next.isDisabled())break;await next.click();
  }
 }
 if(resultVisible&&process.env.DENTAL_LOCALES==='1'){
  // Same live result rendered in EN/DE (display-only translation) and at a narrow in-car width.
  await page.addStyleTag({content:'header{position:static!important}'});
  for(const [lang,width] of [['en',1280],['de',1280],['de',800],['tr',800]]){
   await page.setViewportSize({width,height:900});
   await page.evaluate(l=>{localStorage.setItem('attune.language.v1',l);window.dispatchEvent(new CustomEvent('attune-language-change',{detail:l}));},lang);
   await page.waitForTimeout(800);
   const tabs=page.locator('[data-dental-result] nav button');
   await tabs.nth(0).click();await page.locator('[data-dental-result]').first().screenshot({path:path.join(out,`10-${lang}-${width}-overview.png`)});
   await tabs.nth(1).click();await page.locator('[data-dental-result]').first().screenshot({path:path.join(out,`10-${lang}-${width}-views.png`)});
  }
  await page.setViewportSize({width:1280,height:900});
  await page.evaluate(()=>{localStorage.setItem('attune.language.v1','tr');window.dispatchEvent(new CustomEvent('attune-language-change',{detail:'tr'}));});await page.waitForTimeout(800);
  await page.locator('[data-dental-result] nav button').nth(0).click();
 }
 if(resultVisible&&process.env.DENTAL_SAVE!=='0'&&process.env.DENTAL_HISTORY!=='0'){
  // Reopen the saved record: it must show its own photos (or none), never the live scan.
  await page.waitForFunction(()=>/kaydedil|saklanamadı/.test(document.querySelector('[data-dental-save-status]')?.textContent||''),null,{timeout:30000}).catch(()=>{});
  result.saveStatus=await page.locator('[data-dental-save-status]').textContent().catch(()=>null);
  const record=result.history?.[result.history.length-1];
  if(process.env.DENTAL_RESCAN_BEFORE_OPEN==='1'){
   // Newer unsaved scan in memory, then open the older record.
   await page.getByRole('button',{name:'Geçici görüntüleri temizle'}).click();
  }
  await page.locator(`[data-record-id="${record.id}"] button[aria-label="Sonucu Aç"]`).click();
  const dialog=page.locator('[data-dental-record-carousel]');await dialog.waitFor({timeout:15000});
  await page.waitForTimeout(2500);
  await page.getByRole('dialog').screenshot({path:path.join(out,'08-history-overview.png')});
  await dialog.getByRole('button',{name:'Görünümler',exact:true}).click();await page.waitForTimeout(500);
  result.historySlides=[];
  for(let i=0;i<4;i++){
   const info=await dialog.locator('[data-dental-slide]').first().evaluate(e=>({pose:e.getAttribute('data-dental-slide'),status:e.getAttribute('data-dental-slide-status'),photo:e.querySelector('[data-dental-photo]')?.getAttribute('data-dental-photo')||null,empty:!!e.querySelector('[class*=photoEmpty]')}));
   result.historySlides.push(info);if(i===0)await page.getByRole('dialog').screenshot({path:path.join(out,'09-history-view.png')});
   const next=dialog.getByRole('button',{name:'Sonraki diş görünümü'});if(!await next.count()||await next.isDisabled())break;await next.click();
  }
  const expected=record.views.map(v=>v.photoId);
  result.historyPhotoCheck=result.historySlides.every((s,i)=>s.photo===null?s.empty:s.photo===expected[i]);
  await page.getByRole('button',{name:'Sonuç penceresini kapat'}).click();
  // Delete: numeric record and stored photos disappear together.
  await page.locator(`[data-record-id="${record.id}"] button[aria-label^="Diş Sağlığı kaydını sil"]`).click();
  await page.getByRole('button',{name:'Evet, sil'}).click();await page.waitForTimeout(1500);
  result.afterDelete=await page.evaluate(async id=>{const rows=JSON.parse(localStorage.getItem('attune_dental_history_v1')||'[]');const db=await new Promise(r=>{const q=indexedDB.open('attune-dental-photos',1);q.onsuccess=()=>r(q.result);q.onerror=()=>r(null);});let keys=[];if(db){keys=await new Promise(r=>{const tx=db.transaction('records','readonly');const g=tx.objectStore('records').getAllKeys();g.onsuccess=()=>r(g.result);g.onerror=()=>r(['ERR']);});db.close();}return {records:rows.length,photoKeys:keys};},record.id);
  console.log('HISTORY',JSON.stringify({saveStatus:result.saveStatus,historySlides:result.historySlides,historyPhotoCheck:result.historyPhotoCheck,afterDelete:result.afterDelete}));
 }
 result.log=log;
 if(process.env.DENTAL_PRIVATE_DUMP)fs.writeFileSync(process.env.DENTAL_PRIVATE_DUMP,JSON.stringify(await page.evaluate(()=>__dental.requests.map(r=>r.body))));
 fs.writeFileSync(path.join(out,'result.json'),JSON.stringify(result,null,1));
 console.log(JSON.stringify({elapsedMs:result.elapsedMs,resultVisible,responses:result.responses,history:result.history,afterSave:result.afterSave,lastStatus:result.status.slice(-3),errors:log.slice(0,5)},null,1));
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1);});
