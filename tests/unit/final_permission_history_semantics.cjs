// Actual store/gate/readers plus extracted actual effect callbacks, synthetic adapters only.
// No browser/profile, HTTP, model, media capture or persistent user storage.
require('./ts_loader.js');
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),Module=require('node:module'),ts=require('typescript');
const root='apps/vehicle-app/src/',nativeLoad=Module._load;
const map=new Map(),events=[],checks=[];let failKey=null;
global.window=new EventTarget();
global.localStorage={getItem:k=>map.get(k)??null,setItem(k,v){if(k===failKey){failKey=null;throw Error('synthetic write failure')}map.set(k,String(v))},removeItem:k=>map.delete(k)};
Object.defineProperty(global,'navigator',{configurable:true,value:{locks:{request:async(_name,fn)=>fn()}}});
let states=[],cursor=0,effects=[],path='/skin',routed=null;
const React={Fragment:'fragment',createElement:(type,props,...children)=>({type,props:{...props,children:children.length===1?children[0]:children}}),
 useSyncExternalStore:(_subscribe,snapshot)=>snapshot(),useState(initial){const i=cursor++;if(!(i in states))states[i]=initial;return [states[i],v=>states[i]=typeof v==='function'?v(states[i]):v]},useEffect:fn=>effects.push(fn)};
global.React=React;
Module._load=function(name,parent,...rest){
 if(name==='react')return React;
 if(name==='next/navigation')return {usePathname:()=>path,useRouter:()=>({push:p=>routed=p})};
 if(name==='./AccessibleDialog'&&parent.filename.endsWith('HealthConsentGate.tsx'))return {AccessibleDialog:'dialog'};
 return nativeLoad.call(this,name,parent,...rest);
};
const C=require('../../apps/vehicle-app/src/utils/serviceConsent.ts'),M=require('../../apps/vehicle-app/src/utils/attuneMode.ts');
for(const name of ['attune-service-consent','attune-privacy'])window.addEventListener(name,()=>events.push(name));
const G=require('../../apps/vehicle-app/src/components/HealthConsentGate.tsx');
function gate(service){path='/'+service;cursor=0;effects=[];const e=G.HealthConsentGate({children:'actual-child'});const result=e.type(e.props);for(const effect of effects)effect();return result}
function nodes(e,out=[]){if(!e||typeof e!=='object')return out;out.push(e);for(const c of [e.props?.children].flat(Infinity))nodes(c,out);return out}
function check(name,fn){fn();checks.push(name)}
check('five-service grant/reentry/revoke isolates other services and resets modal checks',()=>{
 for(const id of Object.keys(C.SERVICE_REQUIREMENTS))C.setServiceConsent(id,C.SERVICE_REQUIREMENTS[id].map(([k])=>k));
 for(const id of Object.keys(C.SERVICE_REQUIREMENTS)){
  states=[];assert.equal(gate(id).props.children,'actual-child');assert.equal(gate(id).props.children,'actual-child');
  C.setServiceConsent(id,null);assert.equal(C.serviceAllowed(id),false);
  for(const other of Object.keys(C.SERVICE_REQUIREMENTS).filter(k=>k!==id))assert(C.serviceAllowed(other));
  assert.equal(gate(id).type,'dialog');let controls=nodes(gate(id));assert(controls.filter(n=>n.type==='input').every(n=>!n.props.checked));
  assert(controls.find(n=>n.type==='button'&&n.props.children==='İzin ver ve devam et').props.disabled);
  controls.find(n=>n.type==='button'&&n.props.children==='Şimdi değil').props.onClick();assert.equal(routed,'/');
  C.setServiceConsent(id,C.SERVICE_REQUIREMENTS[id].map(([k])=>k));assert.equal(gate(id).props.children,'actual-child');
 }
});
check('malformed/partial consent and failed writes stay closed without success events',()=>{
 const good=map.get(C.SERVICE_CONSENT_KEY);map.set(C.SERVICE_CONSENT_KEY,'{bad');assert(!C.serviceAllowed('skin'));
 map.set(C.SERVICE_CONSENT_KEY,good);assert.throws(()=>C.setServiceConsent('mental',['recognition']));
 const before=events.length;failKey=C.SERVICE_CONSENT_KEY;assert.throws(()=>C.setServiceConsent('skin',null));assert.equal(events.length,before);assert(C.serviceAllowed('skin'));
});
// Extract a named callback AST from actual source instead of restating its condition.
function callback(file,name,needle){const text=fs.readFileSync(root+file,'utf8'),source=ts.createSourceFile(file,text,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX),found=[];
 function visit(n){if(ts.isVariableDeclaration(n)&&n.name.getText(source)===name&&n.initializer?.getText(source).includes(needle))found.push(n.initializer.getText(source));ts.forEachChild(n,visit)}visit(source);assert.equal(found.length,1,file+': unique callback');return ts.transpile('('+found[0]+')',{target:ts.ScriptTarget.ES2022});}
const skinRevoke=callback('app/skin/page.tsx','revoke','hostedConsentRef');
check('actual skin revoke callback ignores mic-only changes; camera/driving invalidate acquisition',()=>{
 let cancelled=0,stopped=0;const ctx={isCameraAllowed:M.isCameraAllowed,isSkinHostedProcessingAllowed:M.isSkinHostedProcessingAllowed,hostedConsentRef:{current:false},activeScanRef:{current:true},parkedRef:{current:true},voice:{cancel:()=>cancelled++},setLowerFaceIssue:()=>{},acquisitionRef:{current:0},snapshotFrames:{current:{}},snapshotRecord:{current:{}},setSnapshots:()=>{},demoTimerRef:{current:null},clearInterval:()=>{},setScanState:()=>{},setMediaStream:v=>{assert.equal(v,null);stopped++},setIsLiveVideo:()=>{}};
 const fn=vm.runInNewContext(skinRevoke,ctx);map.set(M.STORAGE_KEYS.PRIVACY_MIC_ALLOWED,'false');fn();assert.equal(stopped,0);
 map.set(M.STORAGE_KEYS.PRIVACY_CAMERA_ALLOWED,'false');fn();assert.equal(stopped,1);assert.equal(ctx.acquisitionRef.current,1);
 map.set(M.STORAGE_KEYS.PRIVACY_CAMERA_ALLOWED,'true');ctx.parkedRef.current=false;fn();assert.equal(stopped,2);assert.equal(cancelled,2);
});
const mentalRevoke=callback('utils/useMentalConversation.ts','revoke','isMicrophoneAllowed');
check('actual mental revoke ignores camera; microphone stops voice but does not erase storage',()=>{
 let cancelled=0;const ctx={r:{active:true,mounted:false},phase:'active',serviceAllowed:C.serviceAllowed,isMicrophoneAllowed:M.isMicrophoneAllowed,actions:{current:{cancel:()=>cancelled++}},settings:{current:{textMode:false}},prepareHealthRecords:()=>Promise.resolve(),readMentalHistory:()=>[],setHistory:()=>{},setSummary:()=>{},setNotice:()=>{}};
 const fn=vm.runInNewContext(mentalRevoke,ctx);map.set(M.STORAGE_KEYS.PRIVACY_MIC_ALLOWED,'true');map.set(M.STORAGE_KEYS.PRIVACY_CAMERA_ALLOWED,'false');const before=JSON.stringify([...map]);fn();assert.equal(cancelled,0);assert.equal(JSON.stringify([...map]),before);
 map.set(M.STORAGE_KEYS.PRIVACY_MIC_ALLOWED,'false');fn();assert.equal(cancelled,1);
 ctx.settings.current.textMode=true;fn();assert.equal(cancelled,1);
});
// Execute the actual stream cleanup, using owned synthetic tracks; no device API.
check('actual skin scan cleanup cancels analysis/RAF and stops only owned tracks',()=>{
 const file='app/skin/page.tsx',text=fs.readFileSync(root+file,'utf8'),source=ts.createSourceFile(file,text,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX);let cleanup;
 function visit(n){if(ts.isReturnStatement(n)&&n.expression&&ts.isArrowFunction(n.expression)&&n.expression.getText(source).includes('mediaStream.getTracks().forEach'))cleanup=n.expression.getText(source);ts.forEachChild(n,visit)}visit(source);assert(cleanup);
 let stops=0,otherStops=0,cancels=0,rafs=0;const foreignTrack={stop:()=>otherStops++};
 const ctx={eyewearCheck:{cancel:()=>{}},eyewearGate:{reset:()=>{}},cancelled:false,localAnalysis:{current:{cancel:()=>cancels++}},frameId:7,cancelAnimationFrame:id=>{assert.equal(id,7);rafs++},video:{srcObject:'owned'},mediaStream:{getTracks:()=>[{stop:()=>stops++}]}};
 vm.runInNewContext(ts.transpile('('+cleanup+')',{target:ts.ScriptTarget.ES2022}),ctx)();assert.equal(stops,1);assert.equal(otherStops,0);assert.equal(cancels,1);assert.equal(rafs,1);assert.equal(ctx.video.srcObject,null);assert(ctx.cancelled);void foreignTrack;
});
(async()=>{
 const H=require('../../apps/vehicle-app/src/utils/healthRecords.ts'),V=require('../../apps/vehicle-app/src/utils/skinVolatileHistory.ts');
 const old={id:'synthetic-old',timestamp:'2026-01-01T00:00:00Z',methodVersion:'frozen-old',indicators:{leftCheek:[{id:'dry',score:3,methodVersion:'frozen-old'}]}};
 const fresh={id:'synthetic-new',timestamp:'2026-10-18T00:00:00Z',methodVersion:'synthetic-new',photoId:'a'.repeat(64),regions:{leftCheek:{score:7}},indicators:{leftCheek:[{id:'dry',score:7,methodVersion:'synthetic-new'}]},acneCandidates:[{x:10,y:11,width:2,height:2}],candidateCount:1};
 map.set(M.STORAGE_KEYS.SKIN_HISTORY,JSON.stringify([old]));map.set(M.STORAGE_KEYS.LATEST_SKIN,JSON.stringify(old));const oldJSON=JSON.stringify(old);
 await H.appendHealthRecord('skin',fresh);let rows=await H.prepareHealthRecords('skin');assert.deepEqual(rows,[fresh,old]);assert.equal(JSON.stringify(rows[1]),oldJSON);assert.deepEqual(H.readHealthRecords('skin')[0],fresh);
 const before=JSON.stringify([...map]);C.setServiceConsent('skin',null);const revoked=JSON.stringify([...map]);await assert.rejects(()=>H.appendHealthRecord('skin',{id:'forbidden'}));assert.equal(JSON.stringify([...map]),revoked);C.setServiceConsent('skin',['local']);
 await assert.rejects(()=>H.appendHealthRecord('skin',{id:'late'}, {},()=>false));
 await assert.rejects(()=>H.appendHealthRecord('skin',{id:'raw',image:'data:image/png;base64,AA=='}));
 const stable=JSON.stringify([...map]);failKey=M.STORAGE_KEYS.LATEST_SKIN;await assert.rejects(()=>H.appendHealthRecord('skin',{id:'failed'}));assert.equal(JSON.stringify([...map]),stable);
 checks.push('actual numeric writer/reader reopens exact region/bar/point/photo identity; old unchanged; revoked/late/media/write-failure blocked');
 map.set('attune_privacy_skin_save_allowed','true');const frame={FRONT:{angle:'FRONT',photoId:fresh.photoId,width:32,height:32,localMaps:{dry:{photoId:fresh.photoId,pose:'FRONT',values:new Float32Array([.3]),valid:new Uint8Array([1])}}}};
 V.rememberSkinSnapshots(fresh.id,frame);assert.equal(V.readSkinSnapshots(fresh.id).FRONT.photoId,fresh.photoId);assert.equal(V.readSkinSnapshots(old.id),undefined);
 map.set('attune_privacy_skin_save_allowed','false');window.dispatchEvent(new Event('attune-privacy'));assert.equal(V.readSkinSnapshots(fresh.id),undefined);assert.deepEqual(H.readHealthRecords('skin'),[fresh,old]);
 checks.push('actual volatile photo identity/revocation clears media while numeric history survives');
 const B=require('../../apps/vehicle-app/src/utils/skinOverview.ts');
 assert.equal(B.skinViewOrder(old).length,6);assert(!B.skinViewOrder(old).includes('overview'));
 const legacyLabel={...old,indicators:{leftCheek:[{id:'dry',label:'Cilt kuruluÄŸu',score:3,method:'frozen-old',unit:'%'}]}};
 const labelBefore=JSON.stringify(legacyLabel),view=B.buildSkinViewModel('leftCheek',legacyLabel);
 assert.equal(view.indicators[0].score,3);assert.notEqual(view.indicators[0].label,'Cilt kuruluÄŸu');assert.equal(JSON.stringify(legacyLabel),labelBefore);
 assert.equal(B.skinViewOrder({...fresh,general:{indicators:[]}}).length,7);
 checks.push('actual view builder preserves legacy six regions and scores, centralizes labels without rewriting records');
 const P=require('../../apps/vehicle-app/src/utils/skinPhotoHistory.ts');map.set(P.SKIN_PHOTO_PERMISSION,'true');
 const bad={FRONT:{angle:'FRONT',photoId:'b'.repeat(64),dataUrl:'data:image/png;base64,AA==',width:32,height:32,localMaps:{dry:{photoId:'a'.repeat(64),pose:'FRONT',sourceWidth:32,sourceHeight:32}}}};
 await assert.rejects(()=>P.saveSkinPhotos(fresh.id,bad),/INVALID_PHOTO_MAP/);
 assert.equal(await P.saveSkinPhotos(fresh.id,{},()=>false),false);
 checks.push('actual photo writer rejects map/source identity mismatch and stale acquisition before opening IndexedDB');
 assert(before);Module._load=nativeLoad;
 console.log(JSON.stringify({scope:'actual modules and actual callback AST with synthetic adapters; not browser rendering',checks,passed:checks.length,modelCalls:0,httpCalls:0,userStorageWrites:0,physicalMediaCalls:0},null,2));
})().catch(e=>{Module._load=nativeLoad;console.error(e);process.exitCode=1});
