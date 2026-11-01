const fs=require('fs'),path=require('path'),cp=require('child_process'),assert=require('assert/strict');
const {chromium,_android}=require(process.env.ATTUNE_PLAYWRIGHT_PATH||'playwright');
if(!process.env.ATTUNE_OEM_WORKSPACE)throw Error('Set ATTUNE_OEM_WORKSPACE to the protected fixture/runtime directory');
const root=path.resolve(process.env.ATTUNE_OEM_WORKSPACE),repository=path.resolve(__dirname,'../../..');
const adb=process.env.ATTUNE_ADB||'adb';
const android=(...a)=>cp.execFileSync(adb,['-s','127.0.0.1:15555',...a],{encoding:'utf8',windowsHide:true,timeout:30000});
async function open(module,{camera,controlledAudio=false,language='tr'}={}){
 const out=path.join(root,'runtime',module+'-'+Date.now());fs.mkdirSync(out,{recursive:true});
 const r={module,started:new Date().toISOString(),boundary:'Real AAOS 15, simulated PARK. Controlled approved media traverses official Anbox SDK / WebRTC / Android media capture. No product score, landmark or recognition result injection.',actions:[],inventory:[],responses:[],errors:[]};
 const save=()=>fs.writeFileSync(path.join(out,'evidence.json'),JSON.stringify(r,null,2));
 const args=['--autoplay-policy=no-user-gesture-required'];
 if(camera)args.push('--use-fake-device-for-media-stream','--use-file-for-fake-video-capture='+camera);
 const b=await chromium.launch({headless:true,executablePath:process.env.ATTUNE_CHROME_EXECUTABLE,ignoreDefaultArgs:['--mute-audio'],args});
 let d;
 try{
 const c=await b.newContext({viewport:{width:1320,height:790},permissions:['camera','microphone'],acceptDownloads:true});
 const q=await c.newPage();await q.goto('https://localhost:18443'+(controlledAudio?'#controlled-audio':''));await q.locator('#connect').click();await q.waitForFunction(()=>document.querySelector('#stream video')?.videoWidth>0,null,{timeout:30000});
 android('shell','input','keyevent','KEYCODE_HOME');await q.waitForTimeout(1200);await q.locator('#record').click();r.recordStart=Date.now();await q.waitForTimeout(1200);
 r.launch=android('shell','am','start','-W','-n','more.attune.automotive.prototype.debug/more.attune.automotive.MainActivity');
 d=(await _android.devices({omitDriverInstall:true})).find(x=>x.serial()==='127.0.0.1:15555');assert(d);
 const p=await(await d.webView({pkg:'more.attune.automotive.prototype.debug',timeout:30000})).page();p.setDefaultTimeout(25000);
 // Presentation-only touch feedback, driven exclusively by actual input events.
 // No application values, scoring, consent, media or gate state are modified.
 await p.evaluate(()=>document.addEventListener('pointerdown',e=>{
  const dot=document.createElement('span');dot.dataset.oemTouchFeedback='actual-pointer';
  Object.assign(dot.style,{position:'fixed',left:(e.clientX-13)+'px',top:(e.clientY-13)+'px',width:'26px',height:'26px',border:'3px solid #00e7ff',borderRadius:'50%',background:'#00e7ff33',pointerEvents:'none',zIndex:'2147483647',boxSizing:'border-box'});
  document.body.append(dot);setTimeout(()=>dot.remove(),550);
 },true));
 r.touchFeedback='Transient ring on genuine pointerdown events; presentation overlay only';
 if(new URL(p.url()).pathname!=='/')await p.locator('nav a[href="/"]').click();
 await p.locator('#attune-language').selectOption(language);
 const catalog=JSON.parse(fs.readFileSync(path.join(repository,'shared/localization/messages.json'),'utf8'));
 const tr=text=>language==='tr'?text:Object.values(catalog).find(x=>x.tr===text)?.[language]||text;
 // Revoke only this synthetic test's service grant via the real UI, so every
 // complete run includes the actual consent dialog rather than inherited consent.
 await p.getByRole('link',{name:tr('Gizlilik & İzinler'),exact:true}).click();
 const serviceName=JSON.parse(fs.readFileSync(path.join(repository,'shared/healthModules.json'),'utf8'))[module].name;
 const consentRow=p.locator('[data-service-settings] > div').filter({has:p.getByRole('heading',{name:tr(serviceName),exact:true})});
 const revoke=consentRow.getByRole('button',{name:tr('İzni kaldır'),exact:true});if(await revoke.count())await revoke.click();
 await p.locator('nav a[href="/"]').click();
 const stamp=()=>r.recordStart?Math.round((Date.now()-r.recordStart)/100)/10:null;
 const pending=[];
 p.on('pageerror',e=>r.errors.push(String(e)));
 p.on('response',res=>{const url=new URL(res.url());if(/^\/api\/(local-health|speech\/transcribe|mental\/)/.test(url.pathname))pending.push(res.json().then(body=>{r.responses.push({path:url.pathname,status:res.status(),body,seconds:stamp()});save();}).catch(()=>{}));});
 p.on('response',res=>{const url=new URL(res.url());if(url.pathname==='/api/mental-neural-speech'){const row={path:url.pathname,status:res.status(),contentType:res.headers()['content-type'],seconds:stamp()};r.responses.push(row);save();pending.push(res.body().then(body=>{Object.assign(row,{bytes:body.length,sha256:require('crypto').createHash('sha256').update(body).digest('hex')});save();}).catch(e=>{row.bodyReadError=String(e);save();}));}});
 async function observe(label,loc,ms=1200){await loc.scrollIntoViewIfNeeded();await p.waitForTimeout(ms);r.actions.push({label,action:'observe',text:await loc.innerText(),seconds:stamp()});save();}
 async function act(label,loc,verify){await loc.scrollIntoViewIfNeeded();const control=await loc.evaluate(e=>e.innerText||e.getAttribute('aria-label')||e.textContent||'');await loc.click();if(verify)await verify();await p.waitForTimeout(650);r.actions.push({label,action:'click',control,seconds:stamp(),status:verify?'PASS':'ACTIVATED'});save();}
 async function inventory(label,loc){r.inventory.push({label,seconds:stamp(),elements:await loc.locator('button,[role=button],a[href],summary,input,select').evaluateAll(es=>es.map(e=>({tag:e.tagName,text:(e.innerText||e.textContent||'').trim(),label:e.getAttribute('aria-label'),href:e.getAttribute('href'),disabled:e.disabled||false,visible:!!(e.offsetWidth||e.offsetHeight||e.getClientRects().length)})))});save();}
 let recording=true;
 async function record(){await p.getByRole('button',{name:tr('Sağlık Merkezi'),exact:true}).waitFor();}
 async function enter(){await p.getByRole('button',{name:tr('Sağlık Merkezi'),exact:true}).click();await p.locator('#health-centre-links a[href="/'+module+'"]').click();const consent=p.getByRole('dialog');if(await consent.count()){await observe('Explicit service permissions',consent);for(const checkbox of await consent.getByRole('checkbox').all())await checkbox.check();await consent.getByRole('button',{name:tr('İzin ver ve devam et'),exact:true}).click();}}
 async function close(error){
  if(error){r.error=String(error);r.body=await p.locator('body').innerText().catch(()=>null);await q.screenshot({path:path.join(out,'failure.png')}).catch(()=>{});}
  await Promise.allSettled(pending);r.stream=await q.evaluate(()=>window.streamEvidence).catch(()=>null);
  if(recording){try{const download=q.waitForEvent('download',{timeout:45000});await q.locator('#stop').click();await(await download).saveAs(path.join(out,'continuous-raw.webm'));r.rawRecording='continuous-raw.webm';}catch(e){r.recordingError=String(e);}}
  r.finished=new Date().toISOString();save();await d.close();await b.close();console.log(JSON.stringify({out,result:r.result,error:r.error}));
 }
 return {p,q,r,out,save,stamp,tr,record,enter,close,act,observe,inventory,android};
 }catch(error){if(d)await d.close().catch(()=>{});await b.close().catch(()=>{});throw error;}
}
module.exports={open,root,android};
