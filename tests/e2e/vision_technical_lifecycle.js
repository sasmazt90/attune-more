/** Run after the narrow controller case in the same isolated test realm. */
async page=>{
 const assert=(v,m)=>{if(!v)throw Error(m)},checks={};
 const records=()=>page.evaluate(()=>localStorage.getItem('togg_health_vision_history'));
 const count=()=>page.evaluate(()=>probe.events.filter(e=>e.combinedCorrect!==undefined).length);
 const wait=()=>page.waitForFunction(()=>document.querySelector('[data-vision-stage]')?.dataset.visionStage==='listening'&&probe.current&&!probe.current.aborted&&document.querySelector('[data-letter-optotype]'),null,{timeout:40000});
 const stopped=()=>page.evaluate(()=>probe.streams.every(s=>s.getTracks().every(t=>t.readyState==='ended'))&&probe.recognitions.every(r=>r.aborted)&&probe.audios.every(a=>a.paused));
 const before=await records(),base=await count();
 await page.getByRole('button',{name:'Başlat',exact:true}).click();await wait();
 await page.getByRole('button',{name:'Sesi kapat',exact:true}).click();
 await page.waitForFunction(()=>document.querySelector('[data-vision-stage]').dataset.visionStage==='user-paused'&&probe.current.aborted);
 assert(await page.locator('[data-letter-optotype]').count()===0,'Mute kept target visible');checks.muteStopsRecognition=true;
 await page.getByRole('button',{name:'Sesi aç',exact:true}).click();await wait();
 await page.evaluate(()=>{probe.failedCallback=probe.current.onresult;probe.current.onerror({error:'not-allowed'})});
 await page.waitForFunction(()=>document.querySelector('[data-vision-stage]').dataset.visionStage==='error');
 assert(await count()===base,'ASR permission error scored');checks.asrPermissionErrorUnscored=true;
 await page.getByRole('button',{name:'Tekrar dene',exact:true}).click();await wait();
 await page.evaluate(()=>probe.failedCallback({resultIndex:0,results:[Object.assign([{transcript:'F düz',confidence:.99}],{isFinal:true})]}));
 assert(await count()===base,'Old failed callback scored');checks.retryIgnoresOldCallback=true;
 await page.evaluate(()=>{probe.previous=probe.current;probe.previousCallback=probe.current.onresult});
 await page.getByRole('button',{name:'Yeni konumla yeniden başlat',exact:true}).click();
 await page.waitForFunction(()=>probe.previous.aborted&&probe.streams.at(-2)?.getTracks().every(t=>t.readyState==='ended'));
 await page.evaluate(()=>probe.previousCallback({resultIndex:0,results:[Object.assign([{transcript:'F düz',confidence:.99}],{isFinal:true})]}));
 assert(await count()===base,'Old session response scored');checks.newSessionIsolatesOldMediaAndASR=true;
 await page.evaluate(()=>{localStorage.setItem('attune_privacy_microphone_allowed','false');window.dispatchEvent(new Event('attune-privacy'))});
 await page.waitForFunction(()=>document.querySelector('[data-vision-stage]').dataset.visionStage==='idle');assert(await stopped(),'Privacy did not close owned media');checks.privacyRevocationStopsAll=true;
 await page.evaluate(()=>localStorage.setItem('attune_privacy_microphone_allowed','true'));
 await page.getByRole('button',{name:'Başlat',exact:true}).click();await page.waitForFunction(()=>probe.streams.at(-1)?.getTracks()[0].readyState==='live');
 try{
  const drive=await page.request.post('http://127.0.0.1:8306/api/vehicle/speed',{data:{speedKmH:25}});assert(drive.ok(),'Isolated drive API failed');
  await page.waitForFunction(()=>document.body.textContent.includes('Sürüş sırasında görev kapalıdır.'),null,{timeout:8000});assert(await stopped(),'Drive lock did not stop owned media');checks.actualDriveApiStopsAll=true;
 }finally{await page.request.post('http://127.0.0.1:8306/api/vehicle/speed',{data:{speedKmH:0}})}
 await page.getByRole('button',{name:'Başlat',exact:true}).waitFor();
 await page.evaluate(()=>{probe.getCamera=navigator.mediaDevices.getUserMedia;navigator.mediaDevices.getUserMedia=async()=>{throw new DOMException('Controlled permission denial','NotAllowedError')}});
 await page.getByRole('button',{name:'Başlat',exact:true}).click();await page.getByRole('alert').filter({hasText:'Kamera görüntüsü alınamadı.'}).waitFor();
 checks.cameraPermissionDenialUnscored=await count()===base&&await records()===before;assert(checks.cameraPermissionDenialUnscored,'Camera denial scored/saved');
 await page.evaluate(()=>navigator.mediaDevices.getUserMedia=probe.getCamera);
 const result={kind:'test-only camera/model/ASR failures; actual controller, local vehicle API and native bank audio',physicalUserAcceptance:false,checks,historyUnchanged:await records()===before,allOwnedResourcesStopped:await stopped()};
 const download=page.waitForEvent('download');await page.evaluate(value=>{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(value)],{type:'application/json'}));a.download='lifecycle-proof.json';a.click()},result);await(await download).saveAs('output/playwright/vision/lifecycle-proof.json');return result;
}
