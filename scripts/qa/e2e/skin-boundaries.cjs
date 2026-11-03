const path=require('path');const {open,fixtureRoot,tr}=require('./harness.cjs');
// Skin interruption boundaries with the controlled file camera and real permission state.
// The 503/504 screens use an intercepted /skin response, labelled as such in the evidence:
// they prove the user-facing handling of a failure, not that the failure occurred.
// apiFetch adds ?language= outside Turkish.
const PREPARE=/\/api\/local-health\/skin\/prepare/;
(async()=>{const h=await open('skin',{camera:path.join(fixtureRoot,'skin-native-input/skinFront.y4m')}),{p,r,save}=h;let error;r.checks=[];const check=(what,pass,observed)=>{r.checks.push({what,pass:!!pass,observed,seconds:h.stamp()});save();console.log((pass?'PASS ':'FAIL ')+what);};
 const start=()=>p.getByRole('button',{name:tr('Analizi Başlat'),exact:true}),retry=()=>p.getByRole('button',{name:tr('Tekrar Dene'),exact:true});
 const live=()=>p.waitForFunction(()=>Array.from(document.querySelectorAll('video')).some(v=>v.srcObject?.getVideoTracks().some(t=>t.readyState==='live')),null,{timeout:180000});
 const records=()=>p.evaluate(()=>JSON.parse(localStorage.getItem('togg_health_skin_history')||'[]').length);
 try{
  await h.enter();const base=await records();
  await start().click();await live();check('Real live track acquired',true);
  await p.evaluate(()=>document.querySelectorAll('video').forEach(v=>v.srcObject?.getVideoTracks().forEach(t=>t.stop())));await retry().waitFor({timeout:20000});check('Ended camera track shows a recoverable error',true,(await p.locator('main').innerText()).slice(0,240));
  await retry().click();await start().waitFor();check('Retry returns to the start',true);await start().click();await live();check('The retry reacquires a live camera',true);
  const privacy=await p.context().newPage();await privacy.goto(new URL('/privacy',p.url()).href);const card=privacy.locator('div.rounded-2xl').filter({has:privacy.getByRole('heading',{name:tr('Kabin Kamerası'),exact:true})});await card.getByRole('button',{name:tr('Erişimi Kapat'),exact:true}).click();await p.waitForFunction(()=>!Array.from(document.querySelectorAll('video')).some(v=>v.srcObject?.active),null,{timeout:15000});check('Revoking camera permission stops capture',true);await card.getByRole('button',{name:tr('İzin Ver'),exact:true}).click();await privacy.close();
  check('No result or history after the interruptions',await records()===base);
  for(const [status,detail,text] of [[503,'LOCAL_MEMORY_RESERVE','Bu cihazda yeterli boş bellek yok. Açık uygulamaları kapatıp yeniden deneyin.'],[503,'LOCAL_MODEL_OR_RESOURCE_UNAVAILABLE','Yerel analiz şu anda kullanılamıyor. Yeniden deneyin; sorun sürerse destek alın.'],[504,'LOCAL_ANALYSIS_TIMEOUT','Analiz zamanında tamamlanamadı. İşlem durduruldu; yeniden deneyebilirsiniz.']]){
   await p.reload();await p.locator('#attune-language').waitFor();await p.locator('[data-health-start]').waitFor();
   const handler=route=>route.fulfill({status,contentType:'application/json',headers:{'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'*'},body:JSON.stringify({detail})});await p.route(PREPARE,handler);
   await start().click();await retry().waitFor({timeout:30000});const shown=await p.locator('main').innerText();check(`Intercepted ${status} ${detail}: honest message, retry offered`,shown.includes(tr(text)),shown.slice(0,260));await p.unroute(PREPARE,handler);check(`No result stored after ${detail}`,await records()===base);await retry().click();
  }
  r.result=true;r.fullResultCoverage=r.checks.every(x=>x.pass);if(!r.fullResultCoverage)process.exitCode=1;
 }catch(e){error=e;console.error(String(e));process.exitCode=1;}finally{await h.close(error);}
})().catch(e=>{console.error(String(e));process.exitCode=1;});
