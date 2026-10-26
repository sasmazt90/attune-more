// Three-pose skin photo storage: the actual photo store (skinPhotoHistory.ts) on an in-memory IndexedDB adapter,
// plus the actual finishMultiScan frame/overview loop and the actual /skin record loader effect, both extracted
// from app/skin/page.tsx with the TypeScript AST (not restated). Synthetic pixels only; no browser, HTTP or model.
// Real-browser IndexedDB coverage: tests/unit/test_skin_photo_history.py and tests/e2e/skin_photo_storage.py.
require('./ts_loader.js');
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),ts=require('typescript'),crypto=require('node:crypto');

// ---- adapters: localStorage + a minimal IndexedDB (copy-on-write transactions, async requests, abort = rollback)
const map=new Map();
global.localStorage={getItem:k=>map.has(k)?map.get(k):null,setItem:(k,v)=>map.set(k,String(v)),removeItem:k=>map.delete(k)};
const databases=new Map();
const later=fn=>setTimeout(fn,0);
function request(){return {onsuccess:null,onerror:null,result:undefined,error:null};}
function makeTransaction(db,name,mode){
 const base=db.stores.get(name);if(!base)throw new DOMException('NotFoundError');
 const work=new Map([...base.data].map(([k,v])=>[k,structuredClone(v)]));let pending=0,done=false;
 const tx={oncomplete:null,onabort:null,onerror:null,error:null,
  abort(){if(done)return;done=true;later(()=>tx.onabort&&tx.onabort());},objectStore:()=>store};
 const op=(write,fn)=>{if(done)throw new DOMException('TransactionInactiveError');if(write&&mode!=='readwrite')throw new DOMException('ReadOnlyError');
  pending++;const r=request();later(()=>{pending--;if(done)return;r.result=fn();try{r.onsuccess&&r.onsuccess({target:r});}catch(e){tx.error=e;tx.abort();return;}finish();});return r;};
 const store={transaction:tx,
  get:k=>op(false,()=>structuredClone(work.get(k))),getAll:()=>op(false,()=>[...work.values()].map(v=>structuredClone(v))),
  put(v){const copy=structuredClone(v);return op(true,()=>{work.set(copy[base.keyPath],copy);return copy[base.keyPath];});},
  delete:k=>op(true,()=>{work.delete(k);}),clear:()=>op(true,()=>{work.clear();})};
 function finish(){if(pending||done)return;done=true;if(mode==='readwrite')base.data=work;later(()=>tx.oncomplete&&tx.oncomplete());}
 later(finish);return tx;
}
global.indexedDB={open(name){const r=request();later(()=>{let db=databases.get(name);const created=!db;if(created){db={stores:new Map()};databases.set(name,db);}
 r.result={createObjectStore:(s,{keyPath})=>db.stores.set(s,{keyPath,data:new Map()}),transaction:(s,mode='readonly')=>makeTransaction(db,s,mode),close(){},onversionchange:null};
 if(created&&r.onupgradeneeded)r.onupgradeneeded();r.onsuccess&&r.onsuccess();});return r;}};
const rows=()=>[...(databases.get('attune-skin-photos')?.stores.get('records')?.data.values()||[])];
const settle=()=>new Promise(r=>setTimeout(r,20));

const P=require('../../apps/vehicle-app/src/utils/skinPhotoHistory.ts');
const HISTORY='togg_health_skin_history',LATEST='togg_health_latest_skin';

// ---- actual page code, extracted by AST
// SKIN_PAGE_SOURCE: run the same checks against another copy of the page (e.g. the pre-fix revision).
const pageFile=process.env.SKIN_PAGE_SOURCE||'apps/vehicle-app/src/app/skin/page.tsx',pageText=fs.readFileSync(pageFile,'utf8');
const page=ts.createSourceFile(pageFile,pageText,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX);
const find=(test)=>{const out=[];(function visit(n){if(test(n))out.push(n);ts.forEachChild(n,visit);})(page);return out;};
const finishMulti=find(n=>ts.isVariableDeclaration(n)&&n.name.getText(page)==='finishMultiScan');assert.equal(finishMulti.length,1);
const loops=[];(function visit(n){if(ts.isForOfStatement(n)&&n.getText(page).includes('frame.general'))loops.push(n);ts.forEachChild(n,visit);})(finishMulti[0]);
assert.equal(loops.length,1,'finishMultiScan: exactly one frame/overview loop');
const overviewLoop=ts.transpile(loops[0].getText(page),{target:ts.ScriptTarget.ES2022});
const loaderCalls=find(n=>ts.isCallExpression(n)&&n.expression.getText(page)==='useEffect'&&n.arguments[0]?.getText(page).includes('__attuneInitialSnapshots'));
assert.equal(loaderCalls.length,1,'one view=latest/view=record loader effect');
const loaderSource=ts.transpile('('+loaderCalls[0].arguments[0].getText(page)+')',{target:ts.ScriptTarget.ES2022});
// The loop as it was at d6474d9 (the reviewed bug), kept only to prove the store rejects its output.
const buggyLoop='for (const frame of Object.values(snapshotFrames.current)) { if (frame && finalResult.general) frame.general = finalResult.general; }';

// ---- synthetic three-pose capture: photoId = sha256 of each frame's own RGBA pixels (as in addLocalMaps)
const sizes={FRONT:[48,64],LEFT:[40,64],RIGHT:[44,64]};
function pixels(seed,w,h){const a=new Uint8Array(w*h*4);for(let i=0;i<a.length;i++)a[i]=i%4===3?255:(i*seed+seed*31)&255;return a;}
function capture(seed){
 const frames={};
 for(const pose of ['FRONT','LEFT','RIGHT']){
  const [w,h]=sizes[pose],photoId=crypto.createHash('sha256').update(pixels(seed+pose.length,w,h)).digest('hex');
  frames[pose]={angle:pose,photoId,dataUrl:'data:image/png;base64,'+Buffer.from(seed+pose).toString('base64'),width:w,height:h,meshes:{},rois:[],exclusions:[],faceContour:[],contours:{},crop:{x:0,y:0,width:1,height:1},
   regionalSkinMap:{pose,regions:{}},
   localMaps:{['forehead:redness']:{photoId,pose,sourceWidth:w,sourceHeight:h,values:new Float32Array([.25,.5]),valid:new Uint8Array([1,0])}},
   // what overviewFromResponse builds from each photo's own /skin response (pose is always 'FRONT' there)
   general:{schemaVersion:1,captureId:photoId,pose:'FRONT',sourceTransform:{sourceWidth:w,sourceHeight:h,coordinateSpace:'source-pixels'},indicators:[]}};
 }
 return frames;
}
function finish(frames,id,loop=overviewLoop){
 const front=frames.FRONT.general;
 const finalResult={id,general:{...front,regionalSkinMap:{fused:true},findings:{status:'measured',findings:[]},analysisId:id}};
 vm.runInNewContext(loop,{snapshotFrames:{current:frames},finalResult,Object});
 return finalResult;
}
const ids=frames=>Object.fromEntries(Object.entries(frames).map(([p,f])=>[p,[f.photoId,f.angle,f.width,f.height]]));
const checks=[];
async function check(name,fn){await fn();checks.push(name);}
const reset=()=>{map.clear();databases.clear();};
const records=(...list)=>{map.set(HISTORY,JSON.stringify(list.map(id=>({id,regions:{forehead:{}},timestamp:id}))));map.set(LATEST,JSON.stringify({id:list[0],regions:{forehead:{}},timestamp:list[0]}));};

(async()=>{
 await check('reviewed bug: the d6474d9 loop gives LEFT/RIGHT the FRONT overview and the store rejects the three-pose record',async()=>{
  reset();records('A');map.set(P.SKIN_PHOTO_PERMISSION,'true');
  const frames=capture(3);finish(frames,'A',buggyLoop);
  assert.equal(frames.LEFT.general.captureId,frames.FRONT.photoId);
  await assert.rejects(()=>P.saveSkinPhotos('A',frames),/INVALID_OVERVIEW_SOURCE/);assert.equal(rows().length,0);
 });
 await check('fixed loop: FRONT carries the fused overview (its own captureId/pose/size), LEFT/RIGHT carry none',async()=>{
  const frames=capture(5),result=finish(frames,'A');
  assert.equal(frames.FRONT.general,result.general);assert.equal(frames.FRONT.general.captureId,frames.FRONT.photoId);
  assert.equal(frames.FRONT.general.pose,'FRONT');assert.equal(frames.FRONT.general.sourceTransform.sourceWidth,frames.FRONT.width);
  assert(!('general' in frames.LEFT)&&!('general' in frames.RIGHT));
  // per-photo data the side photos own is kept
  assert.equal(frames.LEFT.regionalSkinMap.pose,'LEFT');assert.equal(frames.RIGHT.localMaps['forehead:redness'].photoId,frames.RIGHT.photoId);
 });
 await check('(a) consent on: one row holds FRONT, LEFT and RIGHT with each photo\'s own photoId/pose/size and checksum',async()=>{
  reset();records('A');map.set(P.SKIN_PHOTO_PERMISSION,'true');
  const frames=capture(7);finish(frames,'A');const expected=ids(frames);
  assert.equal(await P.saveSkinPhotos('A',frames),true);
  const stored=rows();assert.equal(stored.length,1);assert.equal(stored[0].id,'A');
  assert.equal(crypto.createHash('sha256').update(stored[0].payload).digest('hex'),stored[0].sha256);
  const payload=JSON.parse(stored[0].payload);assert.deepEqual(Object.keys(payload).sort(),['FRONT','LEFT','RIGHT']);
  assert.deepEqual(ids(payload),expected);assert.equal(payload.FRONT.general.captureId,expected.FRONT[0]);
  assert(!payload.LEFT.general&&!payload.RIGHT.general);
  const loaded=await P.loadSkinPhotos('A');assert.deepEqual(ids(loaded),expected);
  assert(loaded.LEFT.localMaps['forehead:redness'].values instanceof Float32Array);
 });
 await check('validation is not loosened: side photo with any overview, wrong pose key, wrong size, foreign map are all rejected',async()=>{
  const base=()=>{const f=capture(9);finish(f,'A');return f;};
  let f=base();f.LEFT.general=f.FRONT.general;await assert.rejects(()=>P.saveSkinPhotos('A',f),/INVALID_OVERVIEW_SOURCE/);
  f=base();f.RIGHT.general={...f.FRONT.general,captureId:f.RIGHT.photoId,sourceTransform:{sourceWidth:f.RIGHT.width,sourceHeight:f.RIGHT.height}};await assert.rejects(()=>P.saveSkinPhotos('A',f),/INVALID_OVERVIEW_SOURCE/);
  f=base();f.FRONT.general={...f.FRONT.general,captureId:f.LEFT.photoId};await assert.rejects(()=>P.saveSkinPhotos('A',f),/INVALID_OVERVIEW_SOURCE/);
  f=base();f.FRONT.width+=1;await assert.rejects(()=>P.saveSkinPhotos('A',f),/INVALID_OVERVIEW_SOURCE|INVALID_PHOTO_MAP/);
  f=base();f.LEFT.angle='RIGHT';await assert.rejects(()=>P.saveSkinPhotos('A',f),/INVALID_PHOTO_SOURCE/);
  f=base();f.LEFT.photoId='nothex';await assert.rejects(()=>P.saveSkinPhotos('A',f),/INVALID_PHOTO_SOURCE/);
  f=base();f.LEFT.localMaps['forehead:redness'].photoId=f.FRONT.photoId;await assert.rejects(()=>P.saveSkinPhotos('A',f),/INVALID_PHOTO_MAP/);
  f=base();f.RIGHT.localMaps['forehead:redness'].pose='LEFT';await assert.rejects(()=>P.saveSkinPhotos('A',f),/INVALID_PHOTO_MAP/);
  assert.equal(rows().length,1,'rejected writes leave the stored row untouched');
 });

 // two real-shaped records: B older, A newest
 const A=capture(11),B=capture(13);finish(A,'A');finish(B,'B');
 async function seed(){reset();records('A','B');map.set(P.SKIN_PHOTO_PERMISSION,'true');assert(await P.saveSkinPhotos('B',B));assert(await P.saveSkinPhotos('A',A));}
 async function openPage(search,inMemory){
  const state={snapshots:undefined,analysis:null,scan:null,region:null};
  const ctx={window:{location:{search},__attuneInitialSnapshots:inMemory},URLSearchParams,localStorage,JSON,
   STORAGE_KEYS:{LATEST_SKIN:LATEST,SKIN_HISTORY:HISTORY},isParked:true,loadSkinPhotos:P.loadSkinPhotos,
   snapshotFrames:{current:{}},snapshotRecord:{current:null},
   setSnapshots:v=>state.snapshots=v,setSelectedRegionId:v=>state.region=v,setAnalysisResult:v=>state.analysis=v,setScanState:v=>state.scan=v};
  vm.runInNewContext(loaderSource,ctx)();await settle();
  return {...state,record:ctx.snapshotRecord.current};
 }
 await check('(b) after reload (no in-memory frames) view=latest and view=record&id show that record\'s own three photos',async()=>{
  await seed();
  let v=await openPage('?view=latest');assert.equal(v.analysis.id,'A');assert.equal(v.record,'A');assert.deepEqual(ids(v.snapshots),ids(A));
  v=await openPage('?view=record&id=A');assert.equal(v.analysis.id,'A');assert.deepEqual(ids(v.snapshots),ids(A));
 });
 await check('(c) opening the OLDER record shows its own photos, never the newest record\'s (stored or in memory)',async()=>{
  await seed();
  let v=await openPage('?view=record&id=B');assert.equal(v.analysis.id,'B');assert.equal(v.record,'B');assert.deepEqual(ids(v.snapshots),ids(B));
  for(const pose of ['FRONT','LEFT','RIGHT'])assert.notEqual(v.snapshots[pose].photoId,A[pose].photoId);
  v=await openPage('?view=record&id=B',A);assert.deepEqual(ids(v.snapshots),ids(B));
  // a record without stored photos shows none (not the newest record's)
  await P.deleteSkinPhotos('B');v=await openPage('?view=record&id=B',A);assert.equal(v.analysis.id,'B');assert.equal(v.snapshots,undefined);
  // the newest record opened while its frames are still in memory uses them
  v=await openPage('?view=record&id=A',A);assert.deepEqual(ids(v.snapshots),ids(A));
 });
 await check('(d) consent off: nothing is stored or loaded',async()=>{
  reset();records('A','B');map.set(P.SKIN_PHOTO_PERMISSION,'false');
  assert.equal(await P.saveSkinPhotos('A',A),false);assert.equal(rows().length,0);
  map.delete(P.SKIN_PHOTO_PERMISSION);assert.equal(await P.saveSkinPhotos('A',A),false);assert.equal(rows().length,0);
  await seed();map.set(P.SKIN_PHOTO_PERMISSION,'false');
  assert.equal(await P.loadSkinPhotos('A'),undefined);assert.equal((await openPage('?view=latest')).snapshots,undefined);
  // a record that is not in the numeric history never gets or shows photos
  map.set(P.SKIN_PHOTO_PERMISSION,'true');assert.equal(await P.saveSkinPhotos('ghost',A),false);
 });
 await check('(d) withdrawing consent (privacy toggle: permission false + clearSkinPhotos) removes all stored photos',async()=>{
  await seed();assert.equal(rows().length,2);
  map.set(P.SKIN_PHOTO_PERMISSION,'false');await P.clearSkinPhotos();assert.equal(rows().length,0);
  map.set(P.SKIN_PHOTO_PERMISSION,'true');assert.equal(await P.loadSkinPhotos('A'),undefined);
  assert.equal(JSON.parse(map.get(HISTORY)).length,2,'numeric records are kept');
 });
 await check('(d) deleting a record removes its three-pose photos (and the undo backup), other records keep theirs',async()=>{
  await seed();let finalized=0;
  await P.deleteSkinPhotosWithRecords('A',()=>{map.set(HISTORY,JSON.stringify(JSON.parse(map.get(HISTORY)).filter(r=>r.id!=='A')));},()=>{throw Error('no rollback expected');},()=>finalized++);
  assert.equal(finalized,1);assert.deepEqual(rows().map(r=>r.id),['B']);assert.equal(map.get(P.SKIN_PHOTO_DELETE_PENDING),undefined);
  assert.deepEqual(ids(await P.loadSkinPhotos('B')),ids(B));assert.equal(await P.loadSkinPhotos('A'),undefined);
 });
 console.log(JSON.stringify({scope:'actual skinPhotoHistory.ts + AST-extracted finishMultiScan loop and /skin loader effect; in-memory IndexedDB adapter, synthetic pixels',checks,passed:checks.length},null,2));
})().catch(e=>{console.error(e);process.exitCode=1;});
