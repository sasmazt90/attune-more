async page=>{
 const assert=(v,m)=>{if(!v)throw Error(m)},checks={};let fail=false;
 await page.addInitScript({path:'tests/e2e/mental_technical_boot.js'});
 await page.route('**/api/mental/converse',r=>r.fulfill({json:{reply:'Kısa teknik yanıt.',providerType:'LIVE_OPENAI'}}));
 await page.route('**/api/mental/speech',r=>fail?r.fulfill({status:503,json:{detail:'CONTROLLED_PROVIDER_FAILURE'}}):r.fulfill({path:'apps/vehicle-app/public/audio/guidance/mental-entry-voice-only-v1.mp3',contentType:'audio/mpeg'}));
 await page.goto('http://127.0.0.1:3308/mental');await page.getByRole('dialog').waitFor();for(const b of await page.getByRole('dialog').getByRole('checkbox').all())await b.check();await page.getByRole('button',{name:'İzin ver ve devam et'}).click();
 const listening=()=>page.waitForFunction(()=>document.querySelector('[data-conversation-phase]')?.dataset.conversationPhase==='listening');
 const speaking=()=>page.waitForFunction(()=>document.querySelector('[data-conversation-phase]')?.dataset.conversationPhase==='speaking'&&Number(document.querySelector('[data-playback-wave]').dataset.amplitude)>.003);
 await page.getByRole('button',{name:'Görüşmeyi Başlat',exact:true}).click();await listening();
 await page.evaluate(()=>mentalProbe.current.emit('Teknik ilk kontrol.'));await speaking();
 assert(!(await page.locator('main').innerText()).includes('Seslendiriliyor'),'Speaking visual label remains');
 await page.getByRole('button',{name:'Seslendirmeyi kapat',exact:true}).click();await listening();
 assert(await page.evaluate(()=>mentalProbe.audios.every(a=>a.paused)),'Mute left audio running');assert(Number(await page.locator('[data-playback-wave]').getAttribute('data-amplitude'))===0,'Mute meter nonzero');checks.headerMuteKeepsInput=true;
 await page.getByRole('button',{name:'Seslendirmeyi aç',exact:true}).click();await page.evaluate(()=>mentalProbe.current.emit('İkinci teknik kontrol.'));await speaking();
 await page.getByRole('button',{name:'Duraklat',exact:true}).click();assert(Number(await page.locator('[data-playback-wave]').getAttribute('data-amplitude'))===0,'Pause meter nonzero');assert(await page.evaluate(()=>mentalProbe.recognitions.every(r=>r.aborted)&&mentalProbe.audios.every(a=>a.paused)),'Pause leaked media');checks.pauseStopsBoth=true;
 await page.getByRole('button',{name:'Devam et',exact:true}).click();await speaking();await listening();fail=true;
 await page.evaluate(()=>mentalProbe.current.emit('Kontrollü ses hatası.'));await page.waitForFunction(()=>document.querySelector('[data-conversation-phase]')?.dataset.conversationPhase==='error');
 assert(Number(await page.locator('[data-playback-wave]').getAttribute('data-amplitude'))===0,'Failure meter nonzero');assert(await page.getByRole('textbox').count()===0,'Hidden written fallback');assert((await page.locator('main').innerText()).includes('Sesli görüşme durduruldu'),'No honest voice error');checks.voiceFailureStopsConversation=true;
 assert(await page.evaluate(()=>mentalProbe.recognitions.every(r=>r.aborted)&&mentalProbe.audios.every(a=>a.paused)),'Failure leaves recognizer');checks.failureStopsInputAndAudio=true;
 fail=false;await page.getByRole('button',{name:'Görüşmeyi Başlat',exact:true}).click();await listening();await page.evaluate(()=>mentalProbe.current.emit('Sayfa çıkışı kontrolü.'));await speaking();
 await page.getByRole('link',{name:'Kokpit',exact:true}).click();await page.waitForURL('http://127.0.0.1:3308/');assert(Number(await page.locator('[data-playback-wave]').getAttribute('data-amplitude'))===0,'Route left waveform');assert(await page.evaluate(()=>mentalProbe.audios.every(a=>a.paused)),'Route left audio');checks.routeCleanup=true;
 const proof={kind:'production app, controlled ASR/provider/HTTP errors; native audio and MediaSource; no live calls',checks,mediaAttempts:await page.evaluate(()=>mentalProbe.cameraAttempts),liveTtsCalls:0,recordCount:await page.evaluate(()=>JSON.parse(localStorage.getItem('togg_health_mental_history')||'[]').length)};
 const d=page.waitForEvent('download');await page.evaluate(v=>{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(v)],{type:'application/json'}));a.download='audio-lifecycle-proof.json';a.click()},proof);await(await d).saveAs('../cdc-progress/health-ui-consent-audio-followup-20261017/audio-lifecycle-proof.json');return proof;
}
