/** Actual production API/UI. Controlled ASR/provider failures, recorded native Emel. */
async page=>{
 const START=0,proof=[],assert=(v,m)=>{if(!v)throw Error(m)};
 const phase=()=>page.locator('[data-conversation-phase]').getAttribute('data-conversation-phase');
 const waitPhase=value=>page.waitForFunction(v=>document.querySelector('[data-conversation-phase]')?.dataset.conversationPhase===v,value,{timeout:15000});
 const mode=v=>page.request.post('http://127.0.0.1:8307/__test__/mode',{data:v});
 const saved=()=>page.evaluate(()=>JSON.parse(localStorage.getItem('togg_health_mental_history')||'[]').length);
 const closed=()=>page.evaluate(()=>mentalProbe.recognitions.every(r=>r.aborted||r.ended)&&mentalProbe.audios.every(a=>a.paused));
 const begin=async(text=false)=>{await page.getByLabel('TOGG Attune hizmet onayı',{exact:true}).check();if(text){await page.getByRole('button',{name:'Sesli yanıtı kapat',exact:true}).click();await page.getByRole('button',{name:'İsterseniz yazabilirsiniz',exact:true}).click()}else{await page.getByRole('button',{name:'Görüşmeyi Başlat',exact:true}).click();await waitPhase('listening')}};
 const send=async()=>{await page.getByRole('textbox',{name:'Görüşme mesajı'}).fill('Kişisel olmayan teknik kontrol.');await page.getByRole('button',{name:'Gönder',exact:true}).click()};
 const consentOff=()=>page.getByLabel('TOGG Attune hizmet onayı',{exact:true}).uncheck();
 const cases=[
  ['asr-errors',async()=>{
   await begin();await page.evaluate(()=>{mentalProbe.old=mentalProbe.current;mentalProbe.current.onerror({error:'no-speech'});mentalProbe.current.ended=true;mentalProbe.current.onend()});
   await page.waitForFunction(()=>mentalProbe.current!==mentalProbe.old&&!mentalProbe.current.aborted);await page.evaluate(()=>mentalProbe.current.onerror({error:'not-allowed'}));await waitPhase('ready');
   assert(await page.getByRole('textbox',{name:'Görüşme mesajı'}).isEnabled(),'ASR error not recoverable via existing text input');
   assert(await page.evaluate(()=>mentalProbe.requests.filter(r=>r.path.endsWith('/converse')).length)===0,'No-speech/error dispatched');await consentOff();
  }],
  ['permission-start-cancel',async()=>{
   await page.evaluate(()=>mentalProbe.suppressStart=true);await page.getByLabel('TOGG Attune hizmet onayı',{exact:true}).check();await page.getByRole('button',{name:'Görüşmeyi Başlat',exact:true}).click();await waitPhase('permission');
   await page.evaluate(()=>mentalProbe.oldStart=mentalProbe.current.onstart);await page.getByRole('button',{name:'Başlatmayı iptal et',exact:true}).click();await page.evaluate(()=>mentalProbe.oldStart());await waitPhase('error');
   assert(!await page.getByRole('dialog',{name:'Görüşme tamamlandı',exact:true}).count(),'Cancelled startup completed');
  }],
  ['provider-error',async()=>{
   await mode({reply:'error'});await begin(true);await send();await waitPhase('error');
   assert((await page.locator('[data-chat-author=AI]').textContent()).includes('bağlantı kurulamadı'),'Provider error hidden');
   await page.getByRole('button',{name:'Görüşmeyi Bitir',exact:true}).click();await waitPhase('error');assert(await page.evaluate(()=>mentalProbe.requests.filter(r=>r.path.endsWith('/analyze-session')).length)===0,'Failed turn summarized');
  }],
  ['speech-error',async()=>{
   await mode({speech:'error'});await begin();await page.evaluate(()=>mentalProbe.current.emit('Kişisel olmayan ses hata kontrolü.'));await page.waitForFunction(()=>document.querySelector('[data-voice-state]')?.dataset.voiceState==='failed');await waitPhase('ready');
   assert(await page.getByRole('textbox',{name:'Görüşme mesajı'}).isEnabled(),'Audio failure did not expose text recovery');assert(await page.evaluate(()=>mentalProbe.recognitions.every(r=>r.aborted)),'ASR reopened after failed audio');await consentOff();
  }],
  ['summary-error',async()=>{
   await begin(true);await send();await waitPhase('ready');await mode({summary:'error'});await page.getByRole('button',{name:'Görüşmeyi Bitir',exact:true}).click();await waitPhase('error');assert(!await page.getByRole('dialog',{name:'Görüşme tamamlandı',exact:true}).count(),'Summary failure presented as complete');
  }],
  ['summary-cancel',async()=>{
   await begin(true);await send();await waitPhase('ready');await mode({summary:'delay'});await page.getByRole('button',{name:'Görüşmeyi Bitir',exact:true}).click();await waitPhase('ending');await page.getByRole('button',{name:'Özet hazırlamayı iptal et',exact:true}).click();await mode({summary:'normal',release:true});await waitPhase('ready');await page.waitForTimeout(250);
  }],
  ['summary-consent-revoke',async()=>{
   await begin(true);await send();await waitPhase('ready');await mode({summary:'delay'});await page.getByRole('button',{name:'Görüşmeyi Bitir',exact:true}).click();await waitPhase('ending');await consentOff();await mode({summary:'normal',release:true});await waitPhase('error');await page.waitForTimeout(250);
  }],
  ['microphone-revoke',async()=>{
   await begin();await page.evaluate(()=>{localStorage.setItem('attune_privacy_microphone_allowed','false');window.dispatchEvent(new Event('attune-privacy'))});await waitPhase('error');assert(await closed(),'Mic revocation leaked owned media');await page.evaluate(()=>localStorage.removeItem('attune_privacy_microphone_allowed'));
  }],
  ['drive-lock',async()=>{
   await begin();try{await page.request.post('http://127.0.0.1:8307/api/vehicle/speed',{data:{speedKmH:25}});await page.waitForFunction(()=>document.body.textContent.includes('Sürüş sırasında görüşme kapalıdır.'),null,{timeout:8000});assert(await closed(),'Drive leaked owned media')}finally{await page.request.post('http://127.0.0.1:8307/api/vehicle/speed',{data:{speedKmH:0}})}
  }],
  ['route-cleanup',async()=>{
   await begin();await page.locator('a[href="/"]').first().click();assert(await closed(),'SPA exit leaked owned media');
  }],
  ['old-session-response',async()=>{
   const calls=[];page.on('request',r=>{if(r.url().endsWith('/api/mental/converse'))calls.push(r.postDataJSON())});await mode({reply:'delay'});await begin();await page.evaluate(()=>{mentalProbe.old=mentalProbe.current;mentalProbe.oldCallback=mentalProbe.current.onresult;mentalProbe.current.emit('Kişisel olmayan eski tur.')});await waitPhase('preparing');await page.getByRole('button',{name:'Görüşmeyi Bitir',exact:true}).click();await waitPhase('error');
   await mode({reply:'normal',release:true});await page.getByRole('button',{name:'Görüşmeyi Başlat',exact:true}).click();await waitPhase('listening');await page.evaluate(()=>mentalProbe.oldCallback({resultIndex:0,results:[Object.assign([{transcript:'Geç kalan eski yanıt',confidence:.99}],{isFinal:true})]}));await page.evaluate(()=>mentalProbe.current.emit('Kişisel olmayan yeni tur.'));await waitPhase('listening');
   assert(calls.length===2&&calls[0].sessionId!==calls[1].sessionId&&calls.every(c=>c.history.length===0),'Old session contaminated new context');assert(await page.locator('[data-chat-author=USER]').count()===1,'Old user turn returned');await consentOff();
  }],
 ];
 for(const [name,run] of cases.slice(START)){
  await mode({reply:'normal',summary:'normal',speech:'normal',release:true});await page.goto('http://127.0.0.1:3307/mental');await run();assert(await saved()===0,name+' saved an incomplete/failed record');assert(await closed(),name+' leaked owned media');
  const result={name,kind:'controlled ASR/provider seam; real production controller/API/native recorded audio',physicalUserAcceptance:false,realProviderCalls:0,records:await saved(),ownedMediaClosed:await closed()};proof.push(result);
  const d=page.waitForEvent('download');await page.evaluate(v=>{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(v)],{type:'application/json'}));a.download='lifecycle.json';a.click()},result);await(await d).saveAs(`output/playwright/mental/lifecycle-${name}.json`);
 }
 return proof;
}
