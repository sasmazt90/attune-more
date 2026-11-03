const path=require('path');const {open,tr}=require('./harness.cjs');
// Cross-module regression: real upload through the shared native worker, real model, automatic
// save, history, reopen and delete. The photo is a repository fixture; no clinical claim.
const HISTORY='attune_dental_history_v1';
(async()=>{const h=await open('dental'),{p,r,save}=h;let error;r.checks=[];const check=(what,pass,observed)=>{r.checks.push({what,pass:!!pass,observed,seconds:h.stamp()});save();console.log((pass?'PASS ':'FAIL ')+what);};
 const records=()=>p.evaluate(key=>JSON.parse(localStorage.getItem(key)||'[]'),HISTORY);
 try{
  await h.enter();const before=(await records()).map(x=>x.id);
  await p.locator('input[type=file]').first().setInputFiles(path.resolve(__dirname,'../../../tests/fixtures/dental-intraoral/cdc-19465.jpg'));
  await p.locator('[data-dental-auto-save=saved]').waitFor({timeout:120000});
  const rows=await records(),created=rows.filter(x=>!before.includes(x.id));check('Real analysis saved exactly one record automatically',created.length===1,{records:rows.length});
  const record=created[0];r.recordId=record.id;
  const replies=r.responses.filter(x=>x.path.startsWith('/api/local-health/dental'));check('The real backend answered 200',replies.length>0&&replies.every(x=>x.status===200),replies.map(x=>x.status));
  await p.screenshot({path:path.join(h.out,'dental-result.png')});
  await p.getByRole('link',{name:tr('Sağlık Geçmişim'),exact:true}).click();const row=p.locator(`[data-record-id="${record.id}"]`);
  await row.getByRole('button',{name:tr('Sonucu Aç'),exact:true}).click();const d=p.getByRole('dialog');await d.waitFor();check('History reopens the saved result',(await d.innerText()).length>40);
  await d.getByRole('button',{name:/kapat|close|schlie/i}).last().click();await d.waitFor({state:'hidden'});
  await row.getByRole('button',{name:/sil|delete|lösch/i}).click();await p.getByRole('button',{name:tr('Evet, sil'),exact:true}).click();await row.waitFor({state:'detached'});
  await p.reload();await p.locator('#attune-language').waitFor();await p.waitForTimeout(1500);check('Deletion survives reload',!(await records()).some(x=>x.id===record.id));
  check('No page errors',r.errors.length===0,r.errors);r.result=true;r.fullResultCoverage=r.checks.every(x=>x.pass);if(!r.fullResultCoverage)process.exitCode=1;
 }catch(e){error=e;console.error(String(e));process.exitCode=1;}finally{await h.close(error);}
})().catch(e=>{console.error(String(e));process.exitCode=1;});
