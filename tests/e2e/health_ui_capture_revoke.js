async page=>{
 const assert=(x,m)=>{if(!x)throw Error(m)},rows=[];
 await page.addInitScript(()=>{window.pendingMedia=null;window.mediaCalls=[];navigator.mediaDevices.getUserMedia=constraints=>new Promise(resolve=>{window.mediaCalls.push(constraints);window.pendingMedia=()=>{const canvas=document.createElement('canvas');canvas.width=640;canvas.height=480;canvas.getContext('2d').fillRect(0,0,640,480);window.controlledStream=canvas.captureStream(1);resolve(window.controlledStream)}});});
 for(const [module,name,start] of [['dental','Diş Sağlığı','Diş Taramasını Başlat'],['vision','Göz Sağlığı','Başlat'],['skin','Cilt Sağlığı','Analizi Başlat']]){
  await page.goto('http://127.0.0.1:3308/'+module);await page.waitForSelector('main button,[role=dialog]');const modal=page.getByRole('dialog');if(await modal.count()){for(const b of await modal.getByRole('checkbox').all())await b.check();await modal.getByRole('button',{name:'İzin ver ve devam et'}).click();}
  await page.waitForFunction(()=>document.querySelector('[data-vehicle-status]')?.textContent==='PARK');await page.getByRole('button',{name:start,exact:true}).click();await page.waitForFunction(()=>typeof pendingMedia==='function');
  const other=await page.context().newPage();await other.goto('http://127.0.0.1:3308/privacy');await other.locator('[data-service-settings]>div').filter({has:other.getByRole('heading',{name,exact:true})}).getByRole('button',{name:'İzni kaldır'}).click();await page.getByRole('dialog').waitFor();
  await page.evaluate(()=>pendingMedia());await page.waitForFunction(()=>controlledStream.getTracks().every(t=>t.readyState==='ended'));
  const actual=await page.evaluate(()=>({requested:mediaCalls,trackStates:controlledStream.getTracks().map(t=>t.readyState),records:Object.entries(localStorage).filter(([k])=>/health_.*history$/.test(k)).map(([k,v])=>({key:k,count:JSON.parse(v).length}))}));
  assert(actual.trackStates.every(s=>s==='ended'),'Late camera stream alive');assert(actual.records.every(r=>r.count===0),'Rejected capture saved record');rows.push({module,...actual});await other.close();
 }
 const proof={kind:'real product capture callback, native canvas MediaStream fixture; no physical camera, no frame analysis',rows};
 const d=page.waitForEvent('download');await page.evaluate(v=>{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(v)],{type:'application/json'}));a.download='capture-revocation-proof.json';a.click()},proof);await(await d).saveAs('../cdc-progress/health-ui-consent-audio-followup-20261017/capture-revocation-proof.json');return proof;
}
