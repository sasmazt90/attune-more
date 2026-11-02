const fs=require('fs'),path=require('path');const {open,root,fixtureRoot,tr}=require('./harness.cjs');
// Interruptions of a running Vision task in the real browser with the controlled fake camera.
// No assessment completes here: each boundary must end without a stored result.
const API='http://127.0.0.1:8000',HISTORY='togg_health_vision_history';
const speed=v=>fetch(API+'/api/vehicle/speed',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({speedKmH:v})});
(async()=>{const camera=path.join(root,'runtime/vision-boundary.y4m');fs.mkdirSync(path.dirname(camera),{recursive:true});fs.copyFileSync(path.join(fixtureRoot,'vision-native-input/visionFront.y4m'),camera);
 const h=await open('vision',{camera,microphone:path.join(fixtureRoot,'synthetic-speech/vision-not-visible.wav')}),{p,r,save}=h;let error;r.checks=[];const check=(what,pass,observed)=>{r.checks.push({what,pass:!!pass,observed,seconds:h.stamp()});save();console.log((pass?'PASS ':'FAIL ')+what);};
 const button=name=>p.getByRole('button',{name:tr(name),exact:true});const count=()=>p.evaluate(key=>JSON.parse(localStorage.getItem(key)||'[]').length,HISTORY);const stage=()=>p.locator('[data-vision-stage]').getAttribute('data-vision-stage');
 const running=async()=>{await button('Başlat').click();await p.waitForFunction(()=>!['idle','preparing'].includes(document.querySelector('[data-vision-stage]')?.dataset.visionStage),null,{timeout:90000});};
 const liveTracks=()=>p.evaluate(()=>{const v=document.querySelector('video');return v?.srcObject?v.srcObject.getTracks().filter(t=>t.readyState==='live').length:0;});
 try{
  await p.getByRole('link',{name:tr('Gizlilik & İzinler'),exact:true}).click();await p.getByRole('checkbox',{name:tr('Yön hizalama sonuçlarını bu cihazda sakla'),exact:true}).check();await p.locator('nav a[href="/"]').click();await h.enter();const base=await count();
  await running();check('Language selector is locked while the task runs',await p.locator('#attune-language').isDisabled());
  await button('Duraklat').click();await p.waitForFunction(()=>document.querySelector('[data-vision-stage]')?.dataset.visionStage==='user-paused',null,{timeout:8000});check('Pause hides the stimulus',await p.locator('[data-letter-area] svg').count()===0);check('Language selector unlocks while paused',!await p.locator('#attune-language').isDisabled());
  await button('Devam et').click();await p.waitForFunction(()=>document.querySelector('[data-vision-stage]')?.dataset.visionStage!=='user-paused',null,{timeout:8000});check('Resume leaves the paused stage',await stage()!=='user-paused',await stage());
  await button('Bitir').click();const d=p.getByRole('dialog');await d.waitFor({timeout:8000});const finished=await d.innerText();check('Finish early: incomplete result not stored',finished.includes(tr('Görev bitirildi. Tamamlanmamış sonuç kaydedilmedi.'))&&await count()===base,finished.slice(0,160));check('Camera released after finish',await liveTracks()===0);await d.getByRole('button',{name:tr('Tamam'),exact:true}).click();

  await running();await speed(50);await p.waitForFunction(()=>document.querySelector('[data-vehicle-status]')?.textContent!=='PARK',null,{timeout:12000});await p.waitForTimeout(800);check('DRIVE stops the task, no record, stimulus gone',await count()===base&&await p.locator('[data-letter-area]').count()===0,await p.locator('main').innerText().then(t=>t.slice(0,160)));await speed(0);await p.waitForFunction(()=>document.querySelector('[data-vehicle-status]')?.textContent==='PARK',null,{timeout:12000});

  await button('Başlat').waitFor({timeout:12000});await running();await p.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,get:()=>true});document.dispatchEvent(new Event('visibilitychange'));});await p.waitForFunction(()=>document.querySelector('[data-vision-stage]')?.dataset.visionStage==='user-paused',null,{timeout:8000});await p.evaluate(()=>{delete document.hidden;});check('Background (dispatched event) pauses the task',true);await button('Bitir').click();await p.getByRole('dialog').getByRole('button',{name:tr('Tamam'),exact:true}).click();

  await running();await p.evaluate(()=>{localStorage.setItem('attune_privacy_camera_allowed','false');window.dispatchEvent(new Event('attune-privacy'));});await p.getByRole('alert').first().waitFor({timeout:8000});check('Revoking camera permission stops the task with no record',await count()===base&&await liveTracks()===0,await p.getByRole('alert').first().innerText());await p.evaluate(()=>{localStorage.removeItem('attune_privacy_camera_allowed');window.dispatchEvent(new Event('attune-privacy'));});
  r.result=true;r.fullResultCoverage=r.checks.every(x=>x.pass);if(!r.fullResultCoverage)process.exitCode=1;
 }catch(e){error=e;console.error(String(e));process.exitCode=1;}finally{await speed(0).catch(()=>{});await h.close(error);}
})().catch(e=>{console.error(String(e));process.exitCode=1;});
