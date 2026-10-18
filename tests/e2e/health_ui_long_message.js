async page=>{
 const assert=(x,m)=>{if(!x)throw Error(m)},calls=[],compact=[],summaries=[];
 await page.addInitScript({path:'tests/e2e/mental_technical_boot.js'});
 await page.route('**/api/mental/converse',r=>{const p=r.request().postDataJSON();calls.push({messages:p.history.length,chars:p.history.reduce((n,m)=>n+m.content.length,0),memoryChars:p.memory.reduce((n,m)=>n+m.length,0),userChars:p.userMessage.length});return r.fulfill({json:{reply:'Teknik yanıt.',providerType:'LIVE_OPENAI'}})});
 await page.route('**/api/mental/compact-context',r=>{const p=r.request().postDataJSON();compact.push({messages:p.messages.length,chars:p.messages.reduce((n,m)=>n+m.content.length,0)});return r.fulfill({json:{memory:[p.messages.find(m=>m.role==='user').content.slice(0,100)],method:'extractive-user-quotes-v1'}})});
 await page.route('**/api/mental/analyze-session',r=>{const p=r.request().postDataJSON();summaries.push({messages:p.messages.length,chars:p.messages.reduce((n,m)=>n+m.content.length,0)});return r.fulfill({json:{summaryText:'Kontrollü uzun metin denemesi.',themes:['teknik kontrol'],providerType:'LIVE_OPENAI'}})});
 await page.route('**/api/mental/speech',r=>r.abort());
 await page.goto('http://127.0.0.1:3308/mental');await page.getByRole('dialog').waitFor();for(const b of await page.getByRole('dialog').getByRole('checkbox').all())await b.check();await page.getByRole('button',{name:'İzin ver ve devam et'}).click();await page.getByRole('button',{name:'Seslendirmeyi kapat',exact:true}).click();
 const listen=()=>page.waitForFunction(()=>document.querySelector('[data-conversation-phase]')?.dataset.conversationPhase==='listening');
 await page.getByRole('button',{name:'Görüşmeyi Başlat',exact:true}).click();await listen();
 for(let i=0;i<15;i++){await page.evaluate(i=>mentalProbe.current.emit(('Teknik '+i+'. '+'x'.repeat(6000)).slice(0,6000)),i);await listen();}
 assert(calls.length===15&&compact.length>0,'Long messages were not compacted');assert(calls.every(c=>c.messages<=40&&c.chars<=120000&&c.userChars<=6000&&c.memoryChars<=16000),'Request bounds exceeded');
 await page.getByRole('button',{name:'Görüşmeyi Bitir',exact:true}).click();await page.getByRole('dialog',{name:'Görüşme tamamlandı'}).waitFor();assert(summaries.length===1&&summaries[0].messages<=200&&summaries[0].chars<=120000,'Final bounds exceeded');
 const proof={controlledTurns:calls.length,userCharsPerTurn:6000,requests:calls,compactions:compact,summary:summaries[0],liveCalls:0,physicalAcceptance:false};
 const d=page.waitForEvent('download');await page.evaluate(v=>{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(v)],{type:'application/json'}));a.download='long-message-proof.json';a.click()},proof);await(await d).saveAs('../cdc-progress/health-ui-consent-audio-followup-20261017/long-message-proof.json');return {turns:calls.length,compactions:compact.length,maxRecentChars:Math.max(...calls.map(c=>c.chars)),summary:summaries[0]};
}
