/** At most two existing-provider turns + one summary. No ASR hardware or retries. */
async page=>{
 const result={kind:'actual production frontend/API/provider and isolated history; nonpersonal text only',physicalUserAcceptance:false,turns:[],summary:null,tts:null};
 await page.addInitScript(()=>{navigator.mediaDevices.getUserMedia=()=>{throw Error('No physical media in bounded text test')};window.SpeechRecognition=window.webkitSpeechRecognition=class{start(){throw Error('No physical ASR in bounded text test')}}});
 await page.goto('http://127.0.0.1:3307/mental');await page.getByLabel('TOGG Attune hizmet onayı',{exact:true}).check();await page.getByRole('button',{name:'Sesli yanıtı kapat',exact:true}).click();await page.getByRole('button',{name:'İsterseniz yazabilirsiniz',exact:true}).click();
 const texts=['Bu kişisel veri içermeyen teknik kontrolde konu etiketimiz mavi defter. Yalnız kitaplardan konuşalım.','Bir önceki turda kullandığımız konu etiketi neydi?'];
 let successful=true;
 for(const text of texts){
  const received=page.waitForResponse(r=>r.url().endsWith('/api/mental/converse')&&r.request().method()==='POST');await page.getByRole('textbox',{name:'Görüşme mesajı'}).fill(text);await page.getByRole('button',{name:'Gönder',exact:true}).click();const response=await received,data=await response.json();
  const entry={httpStatus:response.status(),contextLength:response.request().postDataJSON().history.length,providerType:data.providerType||null};result.turns.push(entry);
  if(!response.ok()){entry.errorCategory=data.detail;successful=false;break}
  await page.waitForFunction(()=>document.querySelector('[data-conversation-phase]').dataset.conversationPhase==='ready',null,{timeout:35000});
  entry.visibleReplyMatches=(await page.locator('[data-chat-author=AI]').last().locator('p').nth(1).textContent()).trim()===data.reply.trim();
  if(result.turns.length===2)entry.contextLabelRecalled=/mavi\s+defter/i.test(data.reply);
 }
 if(successful){
  const received=page.waitForResponse(r=>r.url().endsWith('/api/mental/analyze-session')&&r.request().method()==='POST');await page.getByRole('button',{name:'Görüşmeyi Bitir',exact:true}).click();const response=await received,data=await response.json();result.summary={httpStatus:response.status(),providerType:data.providerType||null,messageRoles:response.request().postDataJSON().messages.map(m=>m.role)};
  if(response.ok()){
   await page.getByRole('dialog',{name:'Görüşme tamamlandı',exact:true}).waitFor();await page.getByRole('button',{name:'Tamam',exact:true}).click();const record=await page.evaluate(()=>JSON.parse(localStorage.getItem('togg_health_mental_history')||'[]').at(-1));
   result.summary.recordStored=!!record;result.summary.transcriptStored=!!record?.transcript;result.summary.inventedMeasures=!!record&&('durationSeconds' in record||'moodBefore' in record||'moodAfter' in record);result.summary.moodSource=record?.moodTrendSource||null;
   // One existing Edge operation, not paid TTS or a different voice/provider.
   result.tts=await page.evaluate(async()=>{
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),35000);let audio,url;
    try{
     const response=await fetch('http://127.0.0.1:8307/api/mental/speech',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:'Merhaba.',cloudConsent:true}),signal:controller.signal});
     if(!response.ok)return {httpStatus:response.status,errorCategory:(await response.json()).detail};
     const bytes=await response.arrayBuffer(),sha256=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))).map(v=>v.toString(16).padStart(2,'0')).join('');audio=new Audio();url=URL.createObjectURL(new Blob([bytes],{type:'audio/mpeg'}));audio.src=url;
     const ended=new Promise((resolve,reject)=>{audio.onended=()=>resolve(true);audio.onerror=()=>reject(Error('NATIVE_PLAYBACK_ERROR'));setTimeout(()=>reject(Error('NATIVE_PLAYBACK_TIMEOUT')),15000)});await audio.play();await ended;return {httpStatus:response.status,bytes:bytes.byteLength,sha256,nativeEnded:audio.ended};
    }catch(e){return {errorCategory:e.name||'TTS_UNAVAILABLE'}}finally{clearTimeout(timer);audio?.pause();if(url)URL.revokeObjectURL(url)}
   });
   const saved=JSON.stringify(record);await page.reload();await page.locator(`[data-record-id="${record.id}"] [aria-haspopup="dialog"]`).click();const dialog=page.getByRole('dialog',{name:'Ruh Sağlığı sonucu',exact:true});await dialog.waitFor();result.summary.sameHistory=(await dialog.textContent()).includes(record.summaryText)&&await page.evaluate(v=>JSON.stringify(JSON.parse(localStorage.getItem('togg_health_mental_history')).at(-1))===v,saved);await page.screenshot({path:'output/playwright/mental/live-history.png',fullPage:true});await dialog.getByRole('button',{name:'Sonuç penceresini kapat'}).click();
  }else result.summary.errorCategory=data.detail;
 }
 const d=page.waitForEvent('download');await page.evaluate(v=>{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(v)],{type:'application/json'}));a.download='live-proof.json';a.click()},result);await(await d).saveAs('output/playwright/mental/live-proof.json');return result;
}
