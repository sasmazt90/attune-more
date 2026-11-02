const assert=require('assert/strict');const {open,tr}=require('./harness.cjs');
// Interruption boundaries of the DIN flow in the real browser. Visibility and device change
// are dispatched events, labelled as such; everything else uses the actual controls.
const API='http://127.0.0.1:8000';
const speed=v=>fetch(API+'/api/vehicle/speed',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({speedKmH:v})});
(async()=>{const h=await open('hearing'),{p,r,save}=h;let error;r.checks=[];const check=(what,pass,observed)=>{r.checks.push({what,pass:!!pass,observed,seconds:h.stamp()});save();console.log((pass?'PASS ':'FAIL ')+what);};
 const button=name=>p.getByRole('button',{name:tr(name),exact:true});const status=()=>p.locator('[data-hearing-page] p[role=status]').first().innerText();
 const records=()=>p.evaluate(()=>JSON.parse(localStorage.getItem('attune_hearing_history_v1')||'[]').length);
 async function prepared(){await button('Ses hazırlığını başlat').click();await p.waitForFunction(l=>[...document.querySelectorAll('[data-hearing-page] button')].some(b=>b.textContent===l&&!b.disabled),tr('Sol kanalı dinle'),{timeout:45000});
  for(const [play,confirm] of [['Sol kanalı dinle','Yalnız sol kulağımda duydum.'],['Sağ kanalı dinle','Yalnız sağ kulağımda duydum.']]){await button(play).click();await p.getByRole('checkbox',{name:tr(confirm),exact:true}).check({timeout:10000});}}
 async function digits(){await prepared();await button(r.language==='tr'?'Gürültüde Türkçe sayılar':'Gürültüde seçilen dilin sayıları').click();await p.waitForFunction(()=>{const e=document.querySelector('input[inputmode=numeric]');return e&&!e.disabled;},null,{timeout:60000});}
 const closed=()=>p.evaluate(()=>(window.__taskContexts||[]).every(c=>c.state!=='running'));
 try{
  await h.enter();const before=await records();
  await button('Ses hazırlığını başlat').click();
  const box=p.getByRole('checkbox',{name:tr('Yalnız sol kulağımda duydum.'),exact:true});await box.waitFor({timeout:45000});check('Channel confirmation is disabled before playback',await box.isDisabled());
  const start=button(r.language==='tr'?'Gürültüde Türkçe sayılar':'Gürültüde seçilen dilin sayıları');check('Assessment cannot start before both channels are confirmed',await start.isDisabled());
  await p.waitForFunction(l=>[...document.querySelectorAll('[data-hearing-page] button')].some(b=>b.textContent===l&&!b.disabled),tr('Sol kanalı dinle'),{timeout:45000});
  await button('Durdur').click();check('Stop during preparation returns to a safe paused state',(await status()).length>0,await status());

  await digits();check('Language selector is locked during scored trials',await p.locator('#attune-language').isDisabled());
  const bar=p.locator('[data-din-progress] [role=progressbar]');check('Progress starts at 0/24',await bar.getAttribute('aria-valuenow')==='0');
  await p.getByRole('textbox',{name:tr('Üç sayı yanıtı'),exact:true}).fill('12');check('Two digits cannot be submitted',await button('Yanıtı Gönder').isDisabled());
  await button('Durdur').click();check('Stop during scored trials: no record, output closed',await records()===before&&await closed(),{notice:await status(),records:await records()});check('Language selector unlocks after stop',!await p.locator('#attune-language').isDisabled());

  await digits();await speed(50);await p.waitForFunction(()=>document.querySelector('[data-vehicle-status]')?.textContent!=='PARK',null,{timeout:12000});await p.waitForTimeout(800);check('DRIVE during trials pauses with no record',await records()===before&&!(await p.locator('input[inputmode=numeric]').count()),{notice:await status()});await speed(0);await p.waitForFunction(()=>document.querySelector('[data-vehicle-status]')?.textContent==='PARK',null,{timeout:12000});
  check('Restart requires a new preparation after DRIVE',await button('Ses hazırlığını başlat').isEnabled());

  await digits();await p.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,get:()=>true});document.dispatchEvent(new Event('visibilitychange'));});await p.waitForTimeout(500);
  const hidden=await status();await p.evaluate(()=>{delete document.hidden;});check('Background transition (dispatched event) pauses with no record',hidden===tr('Pencere arka plana geçti; hazırlığı yeniden doğrulayın.')&&await records()===before,hidden);

  await digits();await p.evaluate(()=>navigator.mediaDevices.dispatchEvent(new Event('devicechange')));await p.waitForTimeout(500);const device=await status();check('Output device change (dispatched event) pauses with no record',device===tr('Ses aygıtı değişti; sol/sağ kanalı yeniden doğrulayın.')&&await records()===before,device);

  await digits();await p.evaluate(()=>{window.attuneOutputMuted=true;window.dispatchEvent(new Event('attune-guidance-muted'));});await p.waitForTimeout(500);const muted=await status();await p.evaluate(()=>{window.attuneOutputMuted=false;window.dispatchEvent(new Event('attune-guidance-muted'));});check('Muting output pauses the assessment with no record',muted===tr('Seslendirme kapatıldı. Test duraklatıldı; hazırlığı yeniden doğrulayın.')&&await records()===before,muted);

  await digits();await p.waitForTimeout(61500);const timeout=await status();check('Unanswered trial times out unscored after 60 s',timeout===tr('Yanıt bekleme süresi doldu. Yanıtsız deneme puanlanmadı; hazırlığı yeniden doğrulayın.')&&await records()===before,timeout);

  await prepared();await button('Saf ses testi').click();await p.waitForFunction(()=>/stop|durdur|stopp/i.test(document.querySelector('[data-hearing-page]')?.innerText||''),null,{timeout:45000});await button('Durdur').click().catch(()=>{});await p.waitForTimeout(400);check('Pure-tone start and stop save no record',await records()===before,await status());
  r.pureTone='Start/stop boundary only; a complete pure-tone assessment is NOT RUN (scope is the 24-trial DIN).';
  r.result=true;r.fullResultCoverage=r.checks.every(x=>x.pass);if(!r.fullResultCoverage)process.exitCode=1;
 }catch(e){error=e;console.error(String(e));process.exitCode=1;}finally{await speed(0).catch(()=>{});await h.close(error);}
})().catch(e=>{console.error(String(e));process.exitCode=1;});
