async page=>{
 const assert=(x,m)=>{if(!x)throw Error(m)},receipt={};
 await page.addInitScript({path:'tests/e2e/mental_technical_boot.js'});
 await page.route('**/api/mental/converse',route=>route.fulfill({json:{reply:'Merhaba. Sizi dinliyorum.',providerType:'LIVE_OPENAI'}}));
 let speechRequests=0;page.on('request',r=>{if(r.url().endsWith('/api/mental/speech'))speechRequests++});
 await page.reload();await page.waitForSelector('[data-conversation-phase], [role=dialog]',{state:'attached'});const dialog=page.getByRole('dialog');if(await dialog.count()){for(const checkbox of await dialog.getByRole('checkbox').all())await checkbox.check();await dialog.getByRole('button',{name:'İzin ver ve devam et'}).click();}
 await page.locator('[data-conversation-phase]').waitFor({state:'attached'});
 assert(await page.getByRole('textbox').count()===0,'Text composer remains');assert(await page.getByRole('button',{name:'Gönder',exact:true}).count()===0,'Send remains');
 await page.getByRole('button',{name:'Görüşmeyi Başlat',exact:true}).click();await page.waitForFunction(()=>mentalProbe.current&&!mentalProbe.current.aborted);
 await page.evaluate(()=>mentalProbe.current.emit('Kişisel olmayan teknik ses kontrolü.'));
 await page.waitForFunction(()=>document.querySelector('[data-conversation-phase]')?.dataset.conversationPhase==='speaking',{timeout:30000});
 receipt.samples=await page.evaluate(async()=>{const a=[];for(let i=0;i<35;i++){a.push({at:performance.now(),amplitude:Number(document.querySelector('[data-playback-wave]').dataset.amplitude),phase:document.querySelector('[data-conversation-phase]').dataset.conversationPhase});await new Promise(r=>setTimeout(r,70))}return a});
 await page.waitForFunction(()=>document.querySelector('[data-conversation-phase]').dataset.conversationPhase==='listening');
 receipt.idle=Number(await page.locator('[data-playback-wave]').getAttribute('data-amplitude'));
 receipt.speechRequests=speechRequests;receipt.nativeEvents=await page.evaluate(()=>mentalProbe.events.filter(x=>x.kind==='native-audio'));
 receipt.noTextEntry=await page.getByRole('textbox').count()===0;receipt.peak=Math.max(...receipt.samples.map(s=>s.amplitude));receipt.dynamicApiStatus=200;
 assert(receipt.peak>.003,'No real waveform');assert(receipt.idle===0,'Wave leaked after end');assert(speechRequests===1,'Unexpected live TTS count');
 await page.getByRole('button',{name:'Duraklat',exact:true}).click();
 receipt.pausedAmplitude=Number(await page.locator('[data-playback-wave]').getAttribute('data-amplitude'));
 const d=page.waitForEvent('download');await page.evaluate(v=>{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(v)],{type:'application/json'}));a.download='tts-third-browser.json';a.click()},receipt);await(await d).saveAs('../cdc-progress/health-ui-consent-audio-followup-20261017/tts-third-browser.json');
 console.log(JSON.stringify({requests:speechRequests,peak:receipt.peak,idle:receipt.idle,nativeEvents:receipt.nativeEvents.length}));
}
