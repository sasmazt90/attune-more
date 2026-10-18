async page=>{
 const assert=(x,m)=>{if(!x)throw Error(m)},calls=[],compactions=[],summaries=[];let failNext=true,delay=false,release;
 await page.addInitScript({path:'tests/e2e/mental_technical_boot.js'});
 await page.route('**/api/mental/speech',r=>r.fulfill({status:503,json:{detail:'NO_LIVE_TTS_IN_CONTROLLED_TEST'}}));
 await page.route('**/api/mental/converse',async r=>{const body=r.request().postDataJSON();calls.push(body);if(delay){await new Promise(resolve=>release=resolve);}try{await r.fulfill({json:{reply:'Teknik yanıt.',providerType:'LIVE_OPENAI'}})}catch{}});
 await page.route('**/api/mental/compact-context',async r=>{const body=r.request().postDataJSON();compactions.push(body);if(failNext){failNext=false;await r.fulfill({status:503,json:{detail:'CONTROLLED_CONTEXT_FAILURE'}});return;}const candidates=[...body.memory,...body.messages.filter(m=>m.role==='user').map(m=>m.content)];const important=candidates.filter(c=>c.includes('etiket'));await r.fulfill({json:{memory:[...new Set([...important,...candidates.slice(-4)])].slice(-32),method:'extractive-user-quotes-v1'}})});
 await page.route('**/api/mental/analyze-session',r=>{summaries.push(r.request().postDataJSON());return r.fulfill({json:{summaryText:'Kişisel veri içermeyen kontrollü teknik görüşme.',themes:['teknik kontrol'],providerType:'LIVE_OPENAI',moodTrend:'NEUTRAL'}})});
 await page.goto('http://127.0.0.1:3308/mental');await page.getByRole('dialog').waitFor();for(const c of await page.getByRole('dialog').getByRole('checkbox').all())await c.check();await page.getByRole('button',{name:'İzin ver ve devam et'}).click();
 await page.getByRole('button',{name:'Seslendirmeyi kapat',exact:true}).click();
 const listening=()=>page.waitForFunction(()=>document.querySelector('[data-conversation-phase]')?.dataset.conversationPhase==='listening'&&mentalProbe.current&&!mentalProbe.current.aborted);
 await page.getByRole('button',{name:'Görüşmeyi Başlat',exact:true}).click();await listening();let failureChecked=false;
 for(let i=0;i<110;i++){
  const text=i===0?'Önceki teknik etiket mavi oda.':i===43?'Düzeltme: teknik etiket yeşil oda.':`Teknik kontrol turu ${i}.`;
  await page.evaluate(t=>mentalProbe.current.emit(t),text);
  await page.waitForFunction(()=>['listening','paused','error'].includes(document.querySelector('[data-conversation-phase]').dataset.conversationPhase));
  const phase=await page.locator('[data-conversation-phase]').getAttribute('data-conversation-phase');
  if(phase==='paused'){assert(!failureChecked,'Unexpected second failure pause');failureChecked=true;assert(calls.length===i,'Context failure dispatched converse');await page.getByRole('button',{name:'Devam et',exact:true}).click();}
  assert(phase!=='error','Long session failed');await listening();
 }
 assert(calls.length===110,'Turn count changed');assert(calls[109].memory.some(x=>x.includes('yeşil oda')),'Correction lost');assert(calls[109].memory.some(x=>x.includes('mavi oda')),'Early detail lost');
 assert(calls.every(c=>c.history.length<=40),'Unbounded recent context');assert(compactions.length>1,'No rolling compaction');assert(JSON.stringify(compactions[0])===JSON.stringify(compactions[1]),'Failed update changed prior memory');
 await page.getByRole('button',{name:'Görüşmeyi Bitir',exact:true}).click();await page.getByRole('dialog',{name:'Görüşme tamamlandı'}).waitFor();
 assert(summaries.length===1&&summaries[0].messages.length<=32&&summaries[0].memory.length>0,'Final summary overflow');
 const records=await page.evaluate(()=>JSON.parse(localStorage.getItem('togg_health_mental_history')||'[]'));assert(records.length===1&&!records[0].transcript,'Unexpected transcript persistence');
 await page.getByRole('button',{name:'Tamam',exact:true}).click();
 await page.getByRole('button',{name:'Görüşmeyi Başlat',exact:true}).click();await listening();delay=true;
 await page.evaluate(()=>mentalProbe.current.emit('Yeni oturum teknik kontrol.'));await page.waitForFunction(()=>document.querySelector('[data-conversation-phase]').dataset.conversationPhase==='preparing');
 assert(calls[110].memory.length===0&&calls[110].history.length===0,'Prior session memory leaked');
 const other=await page.context().newPage();await other.goto('http://127.0.0.1:3308/privacy');await other.locator('[data-service-settings]>div').filter({has:other.getByRole('heading',{name:'Ruh Sağlığı',exact:true})}).getByRole('button',{name:'İzni kaldır'}).click();await page.getByRole('dialog',{name:'Ruh Sağlığı hizmet izni'}).waitFor();release();await page.waitForTimeout(200);
 assert(await page.evaluate(()=>mentalProbe.recognitions.every(r=>r.aborted)&&mentalProbe.audios.every(a=>a.paused)),'Revocation leaked media');assert(await page.evaluate(()=>JSON.parse(localStorage.getItem('togg_health_mental_history')||'[]').length)===1,'Late response wrote history');await other.close();
 const proof={controlledTurns:110,liveProviderCalls:0,liveTtsCalls:0,compactions:compactions.map(c=>({memoryQuotes:c.memory.length,messages:c.messages.length})),contextFailureRetainedPrior:failureChecked&&JSON.stringify(compactions[0])===JSON.stringify(compactions[1]),maxRecentMessages:Math.max(...calls.map(c=>c.history.length)),earlyDetailRetained:calls[109].memory.some(x=>x.includes('mavi oda')),correctionRetained:calls[109].memory.some(x=>x.includes('yeşil oda')),noTurnAutoFinish:summaries.length===1,finalSummaryMessages:summaries[0].messages.length,summaryMemory:summaries[0].memory.length,recordCount:records.length,transcriptStored:!!records[0].transcript,newSessionEmptyMemory:calls[110].memory.length===0,lateResponseRecordCount:1,revocationStoppedOwnedMedia:true};
 const d=page.waitForEvent('download');await page.evaluate(v=>{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(v)],{type:'application/json'}));a.download='long-session-proof.json';a.click()},proof);await(await d).saveAs('../cdc-progress/health-ui-consent-audio-followup-20261017/long-session-proof.json');return proof;
}
