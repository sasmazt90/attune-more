const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const {open,fixtureRoot}=require('./harness.cjs');
const {deleteSynthetic,referral}=require('./result-coverage.cjs');

function makeShortWav(durationSec=0.25,sampleRate=16000){
 const numSamples=Math.floor(durationSec*sampleRate);
 const dataSize=numSamples*2;
 const buf=Buffer.alloc(44+dataSize);
 buf.write('RIFF',0);buf.writeUInt32LE(36+dataSize,4);buf.write('WAVE',8);
 buf.write('fmt ',12);buf.writeUInt32LE(16,16);buf.writeUInt16LE(1,20);buf.writeUInt16LE(1,22);
 buf.writeUInt32LE(sampleRate,24);buf.writeUInt32LE(sampleRate*2,28);buf.writeUInt16LE(2,32);buf.writeUInt16LE(16,34);
 buf.write('data',36);buf.writeUInt32LE(dataSize,40);
 return buf;
}
const wavBytes=makeShortWav(0.25,16000);
const corsHeaders={'Access-Control-Allow-Origin':'*','Access-Control-Allow-Methods':'GET,POST,DELETE,OPTIONS','Access-Control-Allow-Headers':'*','Access-Control-Expose-Headers':'*','Cache-Control':'no-store'};

(async()=>{
 const h=await open('mental',{microphone:path.join(fixtureRoot,'synthetic-speech/mental-browser.wav')});
 const {p,r,tr,act,observe,inventory,save}=h;
 r.states=[];r.testMode='Deterministic provider route interception for /api/mental/* and /api/mental-neural-speech (zero paid OpenAI calls); real browser SpeechRecognition, UI state machine, consent gates, and localStorage history persistence';
 let error,analyzeMode='success',analyzeCalls=0,converseCalls=0,delayAnalyzeMs=0;

 await p.route(/\/api\/mental\/(provider-status|compact-context|converse|analyze-session|speech)/,async route=>{
  if(route.request().method()==='OPTIONS'){
   await route.fulfill({status:204,headers:corsHeaders});
   return;
  }
  const pathname=new URL(route.request().url()).pathname;
  if(pathname.endsWith('/provider-status')){
   await route.fulfill({status:200,contentType:'application/json',headers:corsHeaders,body:JSON.stringify({isLiveLLM:true,apiKeyConfigured:true,providerName:'OpenAI Canlı (GPT-4o-mini)'})});
   return;
  }
  if(pathname.endsWith('/compact-context')){
   await route.fulfill({status:200,contentType:'application/json',headers:corsHeaders,body:JSON.stringify({memory:['User values quiet personal space and calm pacing.'],method:'extractive-user-quotes-v1'})});
   return;
  }
  if(pathname.endsWith('/converse')){
   converseCalls++;
   const reply=converseCalls%2===1
    ?'Thank you for sharing that. Taking a quiet pause in the cabin can help restore your sense of personal space. How has your energy felt during today\'s drive?'
    :'That makes complete sense. Pacing your schedule and allowing short breaks between stops can make the rest of your day feel much lighter.';
   await route.fulfill({
    status:200,
    contentType:'application/json',
    headers:corsHeaders,
    body:JSON.stringify({reply,isCrisis:false,providerType:'LIVE_OPENAI'})
   });
   return;
  }
  if(pathname.endsWith('/speech')){
   await route.fulfill({status:200,contentType:'audio/wav',headers:corsHeaders,body:wavBytes});
   return;
  }
  if(pathname.endsWith('/analyze-session')){
   analyzeCalls++;
   if(delayAnalyzeMs>0)await new Promise(res=>setTimeout(res,delayAnalyzeMs));
   if(analyzeMode==='fail503'){
    await route.fulfill({status:503,contentType:'application/json',headers:corsHeaders,body:JSON.stringify({detail:'SUMMARY_PROVIDER_UNAVAILABLE'})});
    return;
   }
   await route.fulfill({
    status:200,
    contentType:'application/json',
    headers:corsHeaders,
    body:JSON.stringify({
     providerType:'LIVE_OPENAI',
     summaryText:'You reflected on needing quiet personal space, maintaining calm focus, and taking restorative breaks between stops.',
     spokenSummary:'You reflected on calm focus and taking a restorative break.',
     themes:['Stres Yönetimi','Odaklanma'],
     moodTrend:'RELAXED',
     recommendations:[
      'Take a short breathing pause before your next trip.',
      'Maintain regular rest intervals on long drives.'
     ],
     relatedSessionIds:[],
     recurringThemes:['Stres Yönetimi']
    })
   });
  }
 });
 await p.route(/\/api\/mental-neural-speech/,async route=>{
  if(route.request().method()==='OPTIONS'){
   await route.fulfill({status:204,headers:corsHeaders});
   return;
  }
  let body={};
  try{body=JSON.parse(route.request().postData()||'{}');}catch{}
  const locale=body.language==='tr'?'tr-TR':body.language==='de'?'de-DE':'en-US';
  const headers={...corsHeaders,'X-TTS-Source':'chatterbox-multilingual-v3','X-TTS-Locale':locale};
  if(body.speakerProfile)headers['X-TTS-Speaker-Profile']=body.speakerProfile;
  await route.fulfill({status:200,contentType:'audio/wav',headers,body:wavBytes});
 });

 async function stateUntil(test,seconds=180){
  const end=Date.now()+seconds*1000;
  while(Date.now()<end){
   const el=p.locator('[data-conversation-phase]'),phase=await el.getAttribute('data-conversation-phase'),voice=await el.getAttribute('data-voice-state');
   r.states.push({phase,voice,seconds:h.stamp()});save();
   if(phase==='error'&&analyzeMode!=='fail503')throw Error(await p.locator('body').innerText());
   const play=p.locator('[data-neural-play-response]');
   if(await play.count()&&await play.isEnabled())await play.click();
   if(await test(phase,voice))return;
   await p.waitForTimeout(400);
  }
  throw Error('Mental state deadline');
 }
 async function info(button,label){
  await button.click();
  const d=p.getByRole('dialog').filter({has:p.getByRole('button',{name:tr('Bilgi penceresini kapat'),exact:true})});
  await d.waitFor();await inventory(label,d);await observe(label,d);
  await act(label+' close',d.getByRole('button',{name:tr('Bilgi penceresini kapat'),exact:true}),()=>d.waitFor({state:'hidden'}));
 }

 try{
  await p.getByRole('link',{name:tr('Gizlilik & İzinler'),exact:true}).click();
  const memory=p.locator('div.bg-cockpit-surface.flex.flex-col.justify-between').filter({has:p.getByRole('heading',{name:tr('Seans Hafızası'),exact:true})});
  const enable=memory.getByRole('button',{name:tr('Etkinleştir'),exact:true});
  if(await enable.count())await enable.click();
  await p.getByRole('checkbox',{name:tr('Tam konuşma dökümünü bu cihazda sakla'),exact:true}).check();
  await p.locator('nav a[href="/"]').click();

  r.beforeIds=await p.evaluate(()=>JSON.parse(localStorage.getItem('togg_health_mental_history')||'[]').map(x=>x.id));
  r.before=r.beforeIds.length;
  await h.record();await h.enter();
  await info(p.locator('main button[aria-haspopup=dialog]').first(),'Mental service information');
  await p.evaluate(()=>{window.__observedMentalTiming=[];window.addEventListener('attune-speech-timing',e=>window.__observedMentalTiming.push({...e.detail,observedAt:Date.now()}));});

  // 1. Complete 2-turn conversation -> End Session -> Automatic Save without Save button/checkbox
  await p.getByRole('button',{name:tr('Görüşmeyi Başlat'),exact:true}).click();
  for(let i=0;i<2;i++){
   await stateUntil(async phase=>(await p.locator('[data-chat-author=USER]').count())>=i+1,120);
   await stateUntil(async phase=>phase==='listening'&&(await p.locator('[data-chat-author=AI]').count())>=i+1,120);
   console.log('Mental turn',i+1,'completed');
  }
  await act('Finish conversation',p.getByRole('button',{name:tr('Görüşmeyi Bitir'),exact:true}),()=>p.locator('[data-conversation-phase=ending],[data-conversation-phase=completed]').first().waitFor({state:'attached'}));
  await stateUntil(phase=>phase==='completed',120);
  r.result=true;

  const completion=p.getByRole('dialog');
  if(await completion.count()){
   await observe('Actual completion',completion);
   await act('Acknowledge completion',completion.getByRole('button',{name:tr('Tamam'),exact:true}),()=>completion.waitFor({state:'hidden'}));
  }
  await observe('Actual completed-session result area',await p.locator('[data-mental-current-summary]').count()?p.locator('[data-mental-current-summary]'):p.locator('[data-mental-history]'),1200);
  for(const item of await p.locator('[data-mental-current-summary] li').all())await observe('Summary recommendation',item,400);

  // Verify automatic single save & duplicate prevention
  r.records=await p.evaluate(()=>JSON.parse(localStorage.getItem('togg_health_mental_history')||'[]'));
  assert.equal(r.records.length,r.before+1,'Completed session must automatically save exactly once');
  assert.equal(analyzeCalls,1,'Summarize endpoint must be called once for the completed session');
  const generated=r.records.filter(x=>!r.beforeIds.includes(x.id));
  assert.equal(generated.length,1);
  const record=generated[0];
  r.recordId=record.id;
  assert.equal(record.providerType,'LIVE_OPENAI');
  assert(record.consented===true);
  assert(record.transcriptConsented===true);
  assert(record.transcript.filter(x=>x.sender==='USER').length>=2);

  // Verify no separate Save button exists on the completed summary view
  const saveButtons=await p.locator('[data-mental-current-summary] button').evaluateAll(bs=>bs.map(b=>(b.innerText||b.textContent||'').trim()).filter(t=>/^(save|kaydet)$/i.test(t)));
  assert.deepEqual(saveButtons,[],'No separate Save button is required or rendered for automatic summary persistence');

  // Verify theme exploration
  const themes=p.locator('[data-mental-history]');
  await inventory('Completed mental results',p.locator('main'));
  await info(themes.locator('button[aria-haspopup=dialog]'),'Theme explanation');
  const buttons=themes.locator('button[aria-pressed]');
  for(let i=0;i<await buttons.count();i++){
   await act('Theme '+i,buttons.nth(i),()=>themes.locator('[data-selected-theme]').waitFor());
   await observe('Selected theme details',themes.locator('[data-selected-theme]'),400);
  }

  // 2. Verify History -> Reopen -> Transcript & Summary inspection -> Referral
  await p.getByRole('link',{name:tr('Sağlık Geçmişim'),exact:true}).click();
  const row=()=>p.locator('[data-record-id="'+r.recordId+'"]');
  await row().getByRole('button',{name:tr('Sonucu Aç'),exact:true}).click();
  await inventory('Saved mental result',p.getByRole('dialog'));
  for(const message of await p.getByRole('dialog').locator('[data-session-author]').all())await observe('Saved conversation message',message,300);
  await observe('Saved generated summary',p.getByRole('dialog').locator('[data-summary-provider]'),400);
  await info(p.getByRole('dialog').locator('button[aria-haspopup=dialog]'),'Saved result information');
  await p.getByRole('button',{name:tr('Sonuç penceresini kapat'),exact:true}).click();

  await row().getByRole('button',{name:tr('Sonucu Aç'),exact:true}).click();
  await referral(h,p.getByRole('dialog').getByRole('link',{name:tr('Uzman seçenekleri'),exact:true}),'mental','Saved Mental referral');

  // 3. Verify empty session / pause / resume does not save duplicate or empty record
  await p.getByRole('button',{name:tr('Sağlık Merkezi'),exact:true}).click();
  await p.locator('#health-centre-links a[href="/mental"]').click();
  await act('Start a new conversation after completed result',p.getByRole('button',{name:tr('Görüşmeyi Başlat'),exact:true}),()=>p.locator('[data-conversation-phase=listening]').waitFor());
  await act('Pause restarted conversation',p.getByRole('button',{name:tr('Duraklat'),exact:true}),()=>p.locator('[data-conversation-phase=paused]').waitFor());
  await act('Resume restarted conversation',p.getByRole('button',{name:tr('Devam et'),exact:true}),()=>p.locator('[data-conversation-phase=listening]').waitFor());
  await act('Finish empty restarted conversation',p.getByRole('button',{name:tr('Görüşmeyi Bitir'),exact:true}),()=>p.locator('[data-conversation-phase=completed]').waitFor({state:'attached'}));
  await observe('Empty retry is not saved',p.getByRole('dialog'),400);
  assert.equal(await p.evaluate(()=>JSON.parse(localStorage.getItem('togg_health_mental_history')||'[]').length),r.before+1);
  await p.getByRole('button',{name:tr('Tamam'),exact:true}).click();

  // 4. Verify summary cancellation during ending phase does not save a partial record
  delayAnalyzeMs=3500;
  await act('Start session for summary cancellation boundary',p.getByRole('button',{name:tr('Görüşmeyi Başlat'),exact:true}),()=>p.locator('[data-conversation-phase=listening]').waitFor());
  await stateUntil(async phase=>(await p.locator('[data-chat-author=USER]').count())>=1,120);
  await stateUntil(async phase=>phase==='listening'&&(await p.locator('[data-chat-author=AI]').count())>=1,120);
  await p.getByRole('button',{name:tr('Görüşmeyi Bitir'),exact:true}).click();
  await p.locator('[data-conversation-phase=ending]').waitFor({state:'attached',timeout:10000});
  const cancelSumBtn=p.getByRole('button',{name:tr('Özet hazırlamayı iptal et'),exact:true});
  await cancelSumBtn.waitFor({timeout:5000});
  await cancelSumBtn.click();
  await p.locator('[data-conversation-phase=ready]').waitFor({state:'attached',timeout:10000});
  await p.waitForTimeout(4000);
  assert.equal(await p.evaluate(()=>JSON.parse(localStorage.getItem('togg_health_mental_history')||'[]').length),r.before+1,'Cancelled summarization must not save a record');
  r.cancelSummaryBoundaryVerified=true;
  delayAnalyzeMs=0;

  // 5. Verify failed summarization (HTTP 503) does not save a record and preserves existing history
  analyzeMode='fail503';
  await act('Start session for failed summarization boundary',p.getByRole('button',{name:tr('Görüşmeyi Başlat'),exact:true}),()=>p.locator('[data-conversation-phase=listening]').waitFor());
  await stateUntil(async phase=>(await p.locator('[data-chat-author=USER]').count())>=1,120);
  await stateUntil(async phase=>phase==='listening'&&(await p.locator('[data-chat-author=AI]').count())>=1,120);
  await p.getByRole('button',{name:tr('Görüşmeyi Bitir'),exact:true}).click();
  await p.locator('[data-conversation-phase=error]').waitFor({timeout:30000});
  assert.equal(await p.evaluate(()=>JSON.parse(localStorage.getItem('togg_health_mental_history')||'[]').length),r.before+1,'Failed summarization must not add a corrupt or partial history record');
  r.failedSummaryBoundaryVerified=true;
  analyzeMode='success';

  // 6. Verify Delete -> Reload -> Absence persists
  await deleteSynthetic(h,r.recordId,'mental');
  await h.seal();
  await p.reload();
  const afterReloadIds=await p.evaluate(()=>JSON.parse(localStorage.getItem('togg_health_mental_history')||'[]').map(x=>x.id));
  assert(!afterReloadIds.includes(r.recordId),'Deleted mental health summary must remain absent after page reload');
  r.deletedReloadVerified=true;

  await p.locator('nav a[href="/"]').click();
  await observe('Clean cockpit ending',p.locator('main'),400);
  r.fullResultCoverage=true;r.remaining=[];
  
 }catch(e){error=e;console.error(String(e));process.exitCode=1;}finally{await h.close(error);}
})().catch(e=>{console.error(String(e));process.exitCode=1;});
