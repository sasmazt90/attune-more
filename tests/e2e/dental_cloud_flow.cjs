// Cloud E2E for Diş Sağlığı — exits non-zero when any expectation fails.
//
// Fake camera (y4m) → real MediaPipe gate → real backend + ONNX → result →
// explicit save → history reopen → delete; plus uploads and lifecycle cases.
// Synthetic/virtual-camera inputs prove the workflow only, not clinical accuracy
// and not physical-camera usability.
//
// Usage: node tests/e2e/dental_cloud_flow.cjs <fixture.y4m|-> <outDir> <scenario>
//   scenarios: camera | no-photo-permission | skip-bite | skip-side | skip-race |
//              partial-response | cancel | park-change | revoke-camera |
//              revoke-consent | upload:<file>   (uploads: DENTAL_EXPECT=200|422:<detail>)
//   DENTAL_FAULT=block-photo-store|swap-photo-id|keep-delete-backup  injects a defect; the run must FAIL.
//   DENTAL_SECOND_UPLOAD=<photo>  a second real record (upload) that deletion must preserve (required for 'camera').
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path');
const [,,fixture,out,scenario='camera']=process.argv;
const BASE=process.env.DENTAL_BASE||'http://127.0.0.1:3310',API=process.env.DENTAL_API||'http://127.0.0.1:8310';
const FAULT=process.env.DENTAL_FAULT||'';
const ALL=['FRONT','RIGHT','LEFT','BITE'];
const SCENARIOS={
 camera:{poses:ALL,missing:[],measured:4,photos:true},
 'no-photo-permission':{poses:ALL,missing:[],measured:4,photos:false,photoPermission:false},
 'skip-bite':{poses:['FRONT','RIGHT','LEFT'],missing:['BITE'],measured:3,photos:true,skip:'BITE'},
 'skip-side':{poses:['FRONT','LEFT','BITE'],missing:['RIGHT'],measured:3,photos:true,skip:'RIGHT'},
 'skip-race':{poses:['FRONT','RIGHT','LEFT'],missing:['BITE'],measured:3,photos:true,skip:'BITE',race:true},
 'partial-response':{poses:ALL,missing:[],measured:3,unmeasured:['BITE'],photos:true},
 cancel:{withdraw:'cancel',status:/Geçici fotoğraf ve sonuçlar temizlendi/},
 'park-change':{withdraw:'park',status:/yalnız PARK durumunda/},
 'revoke-camera':{withdraw:'camera',status:/Kamera izni geri çekildi/},
 'revoke-consent':{withdraw:'consent'},
};
const upload=scenario.startsWith('upload:')?scenario.slice(7):null;
const spec=upload?{upload,expect:process.env.DENTAL_EXPECT||'200',photos:true,missing:[]}:SCENARIOS[scenario];
if(!spec){console.error('Unknown scenario '+scenario);process.exit(2);}
fs.mkdirSync(out,{recursive:true});
const failures=[],report={scenario,fixture,fault:FAULT||null,checks:[]};
const check=(ok,name,detail)=>{report.checks.push({ok:!!ok,name,detail:detail===undefined?undefined:detail});if(!ok)failures.push(name+(detail===undefined?'':' :: '+JSON.stringify(detail).slice(0,400)));};
const eq=(a,b)=>JSON.stringify(a)===JSON.stringify(b);

(async()=>{
 const browser=await chromium.launch({args:['--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream',...(fixture&&fixture!=='-'?['--use-file-for-fake-video-capture='+fixture]:[]),'--enable-unsafe-swiftshader']});
 const context=await browser.newContext({viewport:{width:1280,height:900},permissions:['camera']});
 const page=await context.newPage();const consoleErrors=[],pageErrors=[];
 page.on('console',m=>{if(m.type()==='error')consoleErrors.push(m.text());});
 page.on('pageerror',e=>pageErrors.push(e.message));
 await page.addInitScript(({fault,race})=>{
  window.__dental={requests:[],responses:[],status:[]};const native=window.fetch;
  window.fetch=async(...a)=>{const url=String(a[0]);const hit=/\/api\/local-health\/dental(-upload)?(\?|$)/.test(url);if(hit)__dental.requests.push({url,at:performance.now(),body:JSON.parse(a[1].body)});const r=await native(...a);if(hit)__dental.responses.push({url,status:r.status,body:await r.clone().json().catch(()=>null)});return r;};
  const t0=performance.now();setInterval(()=>{const s=document.querySelector('[data-dental-page] [role=status]')?.textContent||'';const step=document.querySelector('[data-dental-step]')?.getAttribute('data-dental-step')||'';const last=__dental.status[__dental.status.length-1];if(!last||last.s!==s||last.step!==step)__dental.status.push({t:Math.round(performance.now()-t0),s,step});},100);
  if(race){
   // Delay the photo-identity hash of full camera frames (captureDental) once the
   // skip button is visible, so "skip" can be pressed while a BITE capture is pending.
   const digest=crypto.subtle.digest.bind(crypto.subtle);window.__capture={pending:false,release:null,delayed:0};
   crypto.subtle.digest=async(alg,data)=>{const big=(data?.byteLength||0)>1e6;if(big&&document.querySelector('[data-dental-skip-bite]')&&!__capture.delayed){__capture.delayed++;__capture.pending=true;await new Promise(r=>{__capture.release=r;});__capture.pending=false;}return digest(alg,data);};
  }
  if(fault==='keep-delete-backup'){
   // Only the transient delete backup survives: every other step of deletion completes.
   const del=IDBObjectStore.prototype.delete;IDBObjectStore.prototype.delete=function(key){if(typeof key==='string'&&key.startsWith('delete-backup:'))return this.get(key);return del.call(this,key);};
  }
  if(fault==='block-photo-store'){const open=indexedDB.open.bind(indexedDB);indexedDB.open=(name,...rest)=>{if(name==='attune-dental-photos'){const req=open('__blocked__'+Date.now(),1);req.addEventListener('upgradeneeded',()=>req.transaction.abort());return req;}return open(name,...rest);};}
 },{fault:FAULT,race:!!spec.race});
 if(scenario==='partial-response'||FAULT==='swap-photo-id'){
  await page.route('**/api/local-health/dental',async route=>{const response=await route.fetch();const body=await response.json();
   if(FAULT==='swap-photo-id'&&body.views?.length>1)body.views[0].photoId=body.views[1].photoId;
   if(scenario==='partial-response'){const v=body.views[body.views.length-1];
    // The backend's own "insufficient" view shape (as returned for a blurred frame).
    v.quality={...v.quality,valid:false,reasons:['BLURRY']};
    v.caries={...v.caries,value:null,quality:'insufficient',limitationCode:'CAPTURE_QUALITY',candidates:[]};
    v.accumulation={...v.accumulation,value:null,quality:'insufficient',limitationCode:'CAPTURE_QUALITY',candidates:[]};
    v.alignment={...v.alignment,value:null,quality:'insufficient',limitationCode:'CAPTURE_QUALITY',rows:null,contours:[]};}
   await route.fulfill({response,json:body});});
 }
 const acceptConsent=async()=>{const d=page.getByRole('dialog');if(await d.waitFor({timeout:6000}).then(()=>true,()=>false)){await d.getByRole('checkbox').first().check();await page.getByRole('button',{name:'İzin ver ve devam et'}).click();}};
 const t0=Date.now();
 try{
  await page.goto(BASE+'/dental');await acceptConsent();
  const photoPermission=spec.photoPermission!==false;
  if(photoPermission){
   await page.goto(BASE+'/privacy');await page.waitForLoadState('networkidle');
   const permission=page.getByLabel('Yeni diş kayıtlarının fotoğraflarını bu cihazda sakla',{exact:true});
   if(!await permission.isChecked()){await permission.click();}
   await page.waitForFunction(()=>localStorage.getItem('attune_privacy_dental_photos_allowed')==='true',null,{timeout:10000});
   await page.goto(BASE+'/dental');await acceptConsent();
  }
  check(await page.evaluate(()=>localStorage.getItem('attune_privacy_dental_photos_allowed')==='true')===photoPermission,'photo permission set as scenario requires');
  await page.waitForFunction(()=>document.querySelector('[data-vehicle-status]')?.textContent==='PARK',null,{timeout:30000});
  await page.screenshot({path:path.join(out,'01-ready.png'),fullPage:true});
  const requests=()=>page.evaluate(()=>__dental.requests.map(r=>({url:r.url,captures:r.body.captures?.map(c=>({pose:c.pose,photoId:c.photoId,width:c.width,height:c.height,landmarks:c.landmarks?.length})),photo:!!r.body.photo})));
  const responses=()=>page.evaluate(()=>__dental.responses.map(r=>({url:r.url,status:r.status,detail:r.body?.detail,missingViews:r.body?.missingViews,views:r.body?.views?.map(v=>({pose:v.pose,photoId:v.photoId,valid:v.quality?.valid}))})));

  if(spec.withdraw){
   await page.getByRole('button',{name:'Diş Taramasını Başlat',exact:true}).click();
   await page.waitForFunction(()=>document.querySelector('[data-dental-step]')?.getAttribute('data-dental-step')==='1',null,{timeout:120000});
   if(spec.withdraw==='cancel')await page.getByRole('button',{name:'İptal et',exact:true}).click();
   if(spec.withdraw==='park')await page.evaluate(api=>fetch(api+'/api/vehicle/toggle',{method:'POST'}),API);
   if(spec.withdraw==='camera'||spec.withdraw==='consent'){const other=await context.newPage();await other.goto(BASE+'/privacy');await other.evaluate(kind=>{if(kind==='camera')localStorage.setItem('attune_privacy_camera_allowed','false');else{const raw=JSON.parse(localStorage.getItem('attune_health_processing_v1'));delete raw.services.dental;localStorage.setItem('attune_health_processing_v1',JSON.stringify(raw));}},spec.withdraw);await other.close();}
   await page.waitForTimeout(20000);
   const state=await page.evaluate(()=>({status:document.querySelector('[data-dental-page] [role=status]')?.textContent||'',video:document.querySelector('[data-dental-live-video]'),liveTracks:[...document.querySelectorAll('video')].flatMap(v=>v.srcObject?v.srcObject.getTracks().filter(t=>t.readyState==='live').map(t=>t.kind):[])}));
   check((await requests()).length===0,'no analysis request after withdrawal',await requests());
   check(!state.video&&state.liveTracks.length===0,'camera stopped after withdrawal',state.liveTracks);
   if(spec.status)check(spec.status.test(state.status),'withdrawal status shown',state.status);
   if(spec.withdraw==='park')await page.evaluate(api=>fetch(api+'/api/vehicle/toggle',{method:'POST'}),API);
   if(spec.withdraw==='cancel')check(await page.getByRole('button',{name:'Diş Taramasını Başlat',exact:true}).isVisible(),'back to ready state');
  }else{
   if(spec.upload){
    await page.locator('input[type=file]').setInputFiles(spec.upload);
    await page.locator('[data-dental-result],[data-dental-page] [role=alert]').first().waitFor({timeout:120000});
   }else{
    await page.getByRole('button',{name:'Diş Taramasını Başlat',exact:true}).click();
    if(spec.skip){
     const button=page.locator(spec.skip==='BITE'?'[data-dental-skip-pose="BITE"],[data-dental-skip-bite]':`[data-dental-skip-pose="${spec.skip}"]`).first();
     const t=Date.now();await button.waitFor({timeout:150000});report.skipVisibleAfterMs=Date.now()-t;
     if(spec.race){
      await page.waitForFunction(()=>window.__capture?.pending,null,{timeout:120000});   // BITE frame is encoding
      await button.click();                                                                // skip during the await
      await page.evaluate(()=>window.__capture.release());                                 // capture completes afterwards
      await page.waitForTimeout(8000);
     }else await button.click();
    }
    await page.waitForTimeout(3000);await page.screenshot({path:path.join(out,'02-camera.png'),fullPage:true});
    await page.locator('[data-dental-result],[data-dental-page] [role=alert]').first().waitFor({timeout:Number(process.env.DENTAL_CAMERA_TIMEOUT||240000)});
    if(spec.race)await page.waitForTimeout(5000); // a second analysis would have been sent by now
   }
   report.elapsedMs=Date.now()-t0;
   const req=await requests(),res=await responses();report.requests=req;report.responses=res;
   await page.screenshot({path:path.join(out,'03-result.png'),fullPage:true});
   if(spec.upload){
    const [status,detail]=spec.expect.split(':');
    check(req.length===1&&res.length===1,'exactly one upload request',req.length);
    check(String(res[0]?.status)===status,'upload API status',res[0]);
    if(detail)check(res[0]?.detail===detail,'upload rejection reason',res[0]?.detail);
    const visible=await page.locator('[data-dental-result]').count();
    check(status==='200'?visible===1:visible===0,'result screen only for a measured upload',visible);
    if(status!=='200')check(await page.locator('[data-dental-page] [role=alert]').count()>0,'rejection shown to the user');
   }else{
    check(req.length===1,'exactly one analysis request',req.map(r=>r.captures?.map(c=>c.pose)));
    const caps=req[0]?.captures||[];
    check(eq(caps.map(c=>c.pose),spec.poses),'request poses',caps.map(c=>c.pose));
    check(new Set(caps.map(c=>c.photoId)).size===caps.length,'one distinct photo per pose');
    check(caps.every(c=>c.landmarks>=468&&c.width>=640&&c.height>=360),'native frame + landmarks per capture',caps);
    check(res.length===1&&res[0].status===200,'analysis API 200',res.map(r=>[r.status,r.detail]));
    const views=res[0]?.views||[];
    check(eq(views.map(v=>[v.pose,v.photoId]),caps.map(c=>[c.pose,c.photoId])),'response views match their own photos');
    check(eq(res[0]?.missingViews||[],spec.missing),'missingViews',res[0]?.missingViews);
   }
   const visible=await page.locator('[data-dental-result]').count();
   if(spec.upload&&!spec.expect.startsWith('200'))return;
   check(visible===1,'result screen visible');
   if(!visible)return;
   const measured=Number(await page.locator('[data-dental-result]').getAttribute('data-dental-measured'));
   check(measured===(spec.measured??1),'measured view count on screen',measured);
   // Every slide shows its own source photo (pixels identical to the analysed capture).
   await page.getByRole('button',{name:'Görünümler',exact:true}).first().click();
   const slides=[];
   for(let i=0;i<4;i++){
    const info=await page.locator('[data-dental-slide]').first().evaluate(e=>({pose:e.getAttribute('data-dental-slide'),status:e.getAttribute('data-dental-slide-status'),photo:e.querySelector('[data-dental-photo]')?.getAttribute('data-dental-photo')||null,href:e.querySelector('image')?.getAttribute('href')||null,marks:[...e.querySelectorAll('[data-dental-mark]')].map(m=>m.getAttribute('data-dental-mark'))}));
    const source=await page.evaluate(({pose})=>{const r=__dental.requests[0];if(r.body.captures)return r.body.captures.find(c=>c.pose===pose)?.photo||null;return null;},{pose:info.pose});
    slides.push({...info,hrefMatchesCapture:source?info.href===source:null,href:undefined});
    await page.locator('[data-dental-result]').first().screenshot({path:path.join(out,`06-view-${i}-${info.pose}.png`)});
    const next=page.getByRole('button',{name:'Sonraki diş görünümü'});if(!await next.count()||await next.isDisabled())break;await next.click();
   }
   report.slides=slides;
   if(!spec.upload){
    const caps=report.requests[0].captures;
    for(const pose of ALL){
     const s=slides.find(x=>x.pose===pose),c=caps.find(x=>x.pose===pose);
     if(c){check(s&&s.photo===c.photoId&&s.hrefMatchesCapture===true,`${pose} slide shows its own photo`,s);
      check(s&&s.status===((spec.unmeasured||[]).includes(pose)?'unmeasured':'measured'),`${pose} status`,s?.status);
      if((spec.unmeasured||[]).includes(pose))check(s&&s.marks.length===0,`${pose} unmeasured view has no marks`,s?.marks);}
     else check(s&&s.status==='missing'&&!s.photo,`${pose} reported as not taken`,s);
    }
   }
   // Explicit save.
   if(process.env.DENTAL_SAVE!=='0'){
    check(await page.getByRole('button',{name:'Sonucu kaydet'}).isDisabled(),'save disabled until the user opts in');
    await page.getByRole('checkbox',{name:/Sayısal sonucu yerel geçmişime kaydet/}).check();
    await page.getByRole('button',{name:'Sonucu kaydet'}).click();
    await page.locator('[data-dental-save-status]').waitFor({timeout:30000});
    const saveStatus=await page.locator('[data-dental-save-status]').textContent(),saveError=await page.locator('[data-dental-save-status]').getAttribute('data-dental-save-error');
    report.saveStatus=saveStatus;
    const stored=await page.evaluate(()=>JSON.parse(localStorage.getItem('attune_dental_history_v1')||'[]'));
    check(stored.length===1,'one record stored',stored.length);
    const record=stored[0]||{measurements:[]};
    const resViews=report.responses[0].views;
    check(eq(record.measurements.map(m=>[m.pose,m.photoId]),resViews.map(v=>[v.pose,v.photoId])),'record keeps pose/photo identity');
    check(eq(record.missingViews||[],spec.missing||[]),'record keeps missing views',record.missingViews);
    const idbKeys=async()=>page.evaluate(async()=>{const db=await new Promise(r=>{const q=indexedDB.open('attune-dental-photos',1);q.onsuccess=()=>r(q.result);q.onerror=()=>r(null);q.onupgradeneeded=()=>q.result.createObjectStore('records',{keyPath:'id'});});if(!db)return ['IDB_ERROR'];const keys=await new Promise(r=>{const g=db.transaction('records','readonly').objectStore('records').getAllKeys();g.onsuccess=()=>r(g.result);g.onerror=()=>r(['IDB_ERROR']);});db.close();return keys;});
    const keys=await idbKeys();report.photoKeysAfterSave=keys;
    if(spec.photos){
     check(/fotoğraflar.*kaydedildi/.test(saveStatus)&&!saveError,'photos saved when permission is on',saveStatus);
     check(keys.includes(record.id),'stored photos belong to the record',keys);
    }else{
     check(/Yalnız sayısal/.test(saveStatus),'numeric-only save without photo permission',saveStatus);
     check(!keys.includes(record.id),'no photo stored without permission',keys);
    }
    // Reopen from history: only this record's own photos (or none), never the live scan.
    if(process.env.DENTAL_HISTORY!=='0'){
     await page.getByRole('button',{name:'Geçici görüntüleri temizle'}).click();
     await page.locator(`[data-record-id="${record.id}"] button[aria-label="Sonucu Aç"]`).click();
     const dialog=page.locator('[data-dental-record-carousel]');await dialog.waitFor({timeout:15000});await page.waitForTimeout(2500);
     await page.getByRole('dialog').screenshot({path:path.join(out,'08-history.png')});
     await dialog.getByRole('button',{name:'Görünümler',exact:true}).click();
     const hist=[];
     for(let i=0;i<4;i++){
      hist.push(await dialog.locator('[data-dental-slide]').first().evaluate(e=>({pose:e.getAttribute('data-dental-slide'),status:e.getAttribute('data-dental-slide-status'),photo:e.querySelector('[data-dental-photo]')?.getAttribute('data-dental-photo')||null})));
      const next=dialog.getByRole('button',{name:'Sonraki diş görünümü'});if(!await next.count()||await next.isDisabled())break;await next.click();
     }
     report.historySlides=hist;
     for(const m of record.measurements){const h=hist.find(x=>x.pose===m.pose);check(h&&(spec.photos?h.photo===m.photoId:h.photo===null),`history ${m.pose} shows ${spec.photos?'its own photo':'no photo'}`,h);}
     for(const pose of spec.missing||[])check(hist.find(x=>x.pose===pose)?.status==='missing','history keeps '+pose+' as not taken');
     await page.getByRole('button',{name:'Sonuç penceresini kapat'}).click();
     // A second, independent record that deleting the first one must not touch.
     const secondUpload=process.env.DENTAL_SECOND_UPLOAD||'';let other=null;
     if(scenario==='camera')check(!!secondUpload,'DENTAL_SECOND_UPLOAD provided for the preservation check');
     if(secondUpload){
      await page.locator('input[type=file]').setInputFiles(secondUpload);
      await page.locator('[data-dental-result]').waitFor({timeout:120000});
      await page.getByRole('checkbox',{name:/Sayısal sonucu yerel geçmişime kaydet/}).check();
      await page.getByRole('button',{name:'Sonucu kaydet'}).click();
      await page.locator('[data-dental-save-status]').waitFor({timeout:30000});
      const rows=await page.evaluate(()=>JSON.parse(localStorage.getItem('attune_dental_history_v1')||'[]'));
      other=rows.find(r=>r.id!==record.id)||null;
      check(rows.length===2&&other,'second independent record saved',rows.length);
      if(spec.photos)check(other&&(await idbKeys()).includes(other.id),'second record photo stored',await idbKeys());
      await page.getByRole('button',{name:'Geçici görüntüleri temizle'}).click();
     }
     // Delete the first record and wait for the real operation to finish:
     // UI outcome + photo-delete journal and record transaction journal cleared.
     // Observe the operation: transient backups and every status text shown (the shared
     // history list may clear its notice on refresh, so the notice is not the completion signal).
     const watch=page.evaluate(async id=>{const seen=new Set(),notices=new Set();const t=performance.now();let started=false;while(performance.now()-t<25000){const db=await new Promise(r=>{const q=indexedDB.open('attune-dental-photos',1);q.onsuccess=()=>r(q.result);q.onerror=()=>r(null);});if(db){const keys=await new Promise(r=>{const g=db.transaction('records','readonly').objectStore('records').getAllKeys();g.onsuccess=()=>r(g.result);g.onerror=()=>r([]);});db.close();keys.filter(k=>String(k).startsWith('delete-backup:')).forEach(k=>seen.add(k));}document.querySelectorAll('[data-record-history] [role=status]').forEach(e=>e.textContent&&notices.add(e.textContent));const gone=!JSON.parse(localStorage.getItem('attune_dental_history_v1')||'[]').some(r=>r.id===id);if(!gone)started=true;if(started&&gone&&!localStorage.getItem('attune_dental_photo_delete_v1')&&!localStorage.getItem('attune_health_transaction_v1')){await new Promise(r=>setTimeout(r,300));document.querySelectorAll('[data-record-history] [role=status]').forEach(e=>e.textContent&&notices.add(e.textContent));break;}await new Promise(r=>setTimeout(r,20));}return {backups:[...seen],notices:[...notices]};},record.id);
     await page.locator(`[data-record-id="${record.id}"] button[aria-label^="Diş Sağlığı kaydını sil"]`).click();
     await page.getByRole('button',{name:'Evet, sil'}).click();
     const observed=await watch,backupSeenDuringDelete=observed.backups;   // a transient backup during the operation is expected
     // Completion = record gone and both journals cleared; the photo journal is removed only
     // after the backup-delete transaction has completed (deleteDentalPhotosWithRecords).
     const outcome=await page.waitForFunction(id=>!JSON.parse(localStorage.getItem('attune_dental_history_v1')||'[]').some(r=>r.id===id)&&!localStorage.getItem('attune_dental_photo_delete_v1')&&!localStorage.getItem('attune_health_transaction_v1'),record.id,{timeout:30000}).then(()=>true,()=>false);
     check(outcome,'delete operation completed (record gone, journals cleared)');
     const notice=observed.notices.join(' | ');
     check(!/silinemedi/.test(notice),'no deletion failure reported (transient in-progress notices allowed)',notice);
     const after=await page.evaluate(()=>({rows:JSON.parse(localStorage.getItem('attune_dental_history_v1')||'[]').map(r=>r.id),pending:localStorage.getItem('attune_dental_photo_delete_v1'),journal:localStorage.getItem('attune_health_transaction_v1')}));
     const afterKeys=await idbKeys();
     report.afterDelete={notice,rows:after.rows,photoKeys:afterKeys,pending:after.pending,journal:after.journal,backupSeenDuringDelete};
     check(!after.rows.includes(record.id),'numeric record deleted',after.rows);
     check(!afterKeys.includes(record.id),'record photos deleted',afterKeys);
     check(!afterKeys.includes('delete-backup:'+record.id),'delete backup removed',afterKeys);
     check(!afterKeys.some(k=>String(k).startsWith('delete-backup:')),'no delete backup left at all',afterKeys);
     check(after.pending===null,'photo-delete journal cleared',after.pending);
     check(after.journal===null,'record transaction journal cleared',after.journal);
     if(other){
      check(eq(after.rows,[other.id]),'other record preserved',after.rows);
      if(spec.photos)check(afterKeys.includes(other.id),'other record photos preserved',afterKeys);
      // The preserved record still opens with its own photo.
      await page.locator(`[data-record-id="${other.id}"] button[aria-label="Sonucu Aç"]`).click();
      const d2=page.locator('[data-dental-record-carousel]');await d2.waitFor({timeout:15000});await page.waitForTimeout(2000);
      await d2.getByRole('button',{name:'Görünümler',exact:true}).click();
      const shown=await d2.locator('[data-dental-slide]').first().evaluate(e=>e.querySelector('[data-dental-photo]')?.getAttribute('data-dental-photo')||null);
      check(shown===(spec.photos?other.measurements[0].photoId:null),'preserved record still shows its own photo (or none without permission)',shown);
      await page.getByRole('button',{name:'Sonuç penceresini kapat'}).click();
     }
    }
   }
  }
 }catch(error){check(false,'scenario completed without timeout/exception',String(error.message||error).split('\n')[0]);}
 finally{
  report.status=await page.evaluate(()=>window.__dental?.status||[]).catch(()=>[]);
  const allowed=[/XNNPACK delegate/];if(spec.upload&&!String(spec.expect).startsWith('200'))allowed.push(/status of 422/);
  const unexpected=consoleErrors.filter(m=>!allowed.some(r=>r.test(m)));
  check(pageErrors.length===0,'no page errors',pageErrors);
  check(unexpected.length===0,'no unexpected console errors',unexpected);
  if(process.env.DENTAL_PRIVATE_DUMP)fs.writeFileSync(process.env.DENTAL_PRIVATE_DUMP,JSON.stringify(await page.evaluate(()=>__dental.requests.map(r=>r.body)).catch(()=>[])));
  report.failures=failures;report.result=failures.length?'FAIL':'PASS';
  fs.writeFileSync(path.join(out,'result.json'),JSON.stringify(report,null,1));
  console.log(`${report.result} ${scenario}${FAULT?' fault='+FAULT:''} (${report.checks.length} checks)`);
  for(const f of failures)console.log('  ✗ '+f);
  await browser.close();
  process.exit(failures.length?1:0);
 }
})();
