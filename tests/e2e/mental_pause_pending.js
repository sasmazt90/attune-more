/** Actual page; declared provider fixtures; no device or live provider call. */
async page=>{
 await page.addInitScript(()=>{navigator.mediaDevices.getUserMedia=()=>{throw Error('No hardware in controlled test')};window.SpeechRecognition=window.webkitSpeechRecognition=class{start(){throw Error('No hardware ASR')}}});
 const calls=[],summaries=[];let held;
 await page.route('**/api/mental/converse',r=>{calls.push(r.request().postDataJSON());if(calls.length===2){held=r;return}return r.fulfill({json:{reply:'Kontrollü tamamlanmış yanıt.',providerType:'LIVE_OPENAI'}})});
 await page.route('**/api/mental/analyze-session',r=>{summaries.push(r.request().postDataJSON());return r.fulfill({json:{summaryText:'Kontrollü oturum özeti.',themes:['kontrol'],providerType:'LIVE_OPENAI'}})});
 await page.goto('http://127.0.0.1:3307/mental');await page.getByLabel('TOGG Attune hizmet onayı',{exact:true}).check();await page.getByRole('button',{name:'Sesli yanıtı kapat',exact:true}).click();await page.getByRole('button',{name:'İsterseniz yazabilirsiniz',exact:true}).click();
 const send=async text=>{await page.getByRole('textbox',{name:'Görüşme mesajı'}).fill(text);await page.getByRole('button',{name:'Gönder',exact:true}).click()};
 await send('Kontrollü ilk test turu.');await page.waitForFunction(()=>document.querySelector('[data-conversation-phase]').dataset.conversationPhase==='ready');
 await send('Kontrollü bekleyen test turu.');await page.waitForFunction(()=>document.querySelector('[data-conversation-phase]').dataset.conversationPhase==='preparing');
 await page.getByRole('button',{name:'Duraklat',exact:true}).click();await page.getByRole('button',{name:'Devam et',exact:true}).click();await page.waitForTimeout(600);
 const resumed={requests:calls.length,users:await page.locator('[data-chat-author=USER]').count(),assistants:await page.locator('[data-chat-author=AI]').count(),phase:await page.locator('[data-conversation-phase]').getAttribute('data-conversation-phase')};
 if(held){await held.fulfill({json:{reply:'CANCELLED OLD REPLY',providerType:'LIVE_OPENAI'}}).catch(()=>{})}
 await page.waitForTimeout(200);await page.getByRole('button',{name:'Görüşmeyi Bitir',exact:true}).click();await page.waitForTimeout(500);
 const result={kind:'controlled provider responses, real frontend; pending pause/resume',resumed,summaryRequests:summaries.length,finalPhase:await page.locator('[data-conversation-phase]').getAttribute('data-conversation-phase'),saved:await page.evaluate(()=>JSON.parse(localStorage.getItem('togg_health_mental_history')||'[]').length),physicalUserAcceptance:false};
 const d=page.waitForEvent('download');await page.evaluate(v=>{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(v)],{type:'application/json'}));a.download='pause-pending.json';a.click()},result);await(await d).saveAs('output/playwright/mental/pause-pending-before.json');return result;
}
