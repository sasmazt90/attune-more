/** Network fault only in this test; no provider call, changed prompt or fake audio. */
async page=>{
 const before=await page.evaluate(()=>localStorage.getItem('togg_health_vision_history'));
 const base=await page.evaluate(()=>probe.events.filter(e=>e.combinedCorrect!==undefined).length);
 await page.route('http://127.0.0.1:8306/api/vision/speech',r=>r.fulfill({status:503,body:'Controlled unavailable bank response'}));
 await page.getByRole('button',{name:'Başlat',exact:true}).click();
 await page.waitForFunction(()=>document.querySelector('[data-vision-stage]').dataset.visionStage==='error',null,{timeout:10000});
 const fault=await page.evaluate(()=>({stage:document.querySelector('[data-vision-stage]').dataset.visionStage,letters:document.querySelectorAll('[data-letter-optotype]').length,valid:probe.events.filter(e=>e.combinedCorrect!==undefined).length,recognitionLive:probe.recognitions.some(r=>!r.aborted),message:document.querySelector('[role=alert]')?.textContent}));
 if(fault.valid!==base||fault.letters||fault.recognitionLive)throw Error('Voice failure admitted an answer');
 await page.getByRole('button',{name:'Bitir',exact:true}).click();await page.getByRole('button',{name:'Tamam',exact:true}).click();
 const result={kind:'test-only 503 speech transport failure through actual production controller',physicalUserAcceptance:false,fault,historyUnchanged:await page.evaluate(before=>localStorage.getItem('togg_health_vision_history')===before,before),allTracksEnded:await page.evaluate(()=>probe.streams.every(s=>s.getTracks().every(t=>t.readyState==='ended')))};
 if(!result.historyUnchanged||!result.allTracksEnded)throw Error('Voice failure cancel leaked or saved');
 const download=page.waitForEvent('download');await page.evaluate(v=>{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(v)],{type:'application/json'}));a.download='voice-failure-proof.json';a.click()},result);await(await download).saveAs('output/playwright/vision/voice-failure-proof.json');return result;
}
