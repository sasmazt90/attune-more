// Exercises real server fixtures and the browser converter; no image retention,
// trained-model quality or calibrated threshold acceptance is implied.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const native = require('node:module');
const root = path.resolve(__dirname, '../..');
let typescript;
try { typescript = require('typescript'); } catch {}
const strip = source => typescript ? typescript.transpileModule(source, {
  compilerOptions: { module: typescript.ModuleKind.ESNext, target: typescript.ScriptTarget.ES2022 }
}).outputText : native.stripTypeScriptTypes(source);
const fixtures = JSON.parse(fs.readFileSync(0, 'utf8'));
const source = { captureId: 'a'.repeat(64), pose: 'FRONT', sourceWidth: 1280, sourceHeight: 720, coordinateSpace: 'source-pixels' };
const clone = value => JSON.parse(JSON.stringify(value));
let checks = 0;
function check(fn) { fn(); checks++; }
function synthetic(values) {
  const keys = Object.keys(values);
  const module = new vm.SyntheticModule(keys, function () { for (const k of keys) this.setExport(k, values[k]); });
  return module;
}
const cache = new Map();
async function load(name) {
  if (cache.has(name)) return cache.get(name);
  if (name.endsWith('skinDemoFixture')) {
    const m = synthetic({ REGION_ORDER: ['forehead','rightCheek','leftCheek','nose','chin','periorbital'], SKIN_REGIONS: { forehead: {} }, buildSkinRegionViewModel: () => ({ index: 1 }) });
    cache.set(name,m); return m;
  }
  if (name.endsWith('skinIndicators')) {
    const m = synthetic({ SIGN_LABELS: {}, skinCriterionLabel: id => id }); cache.set(name,m); return m;
  }
  const filename = path.join(root, 'apps/vehicle-app/src/utils', path.basename(name) + '.ts');
  const m = new vm.SourceTextModule(strip(fs.readFileSync(filename, 'utf8')), { identifier: filename });
  cache.set(name,m); await m.link(load); return m;
}
(async () => {
  const module = await load('skinOverview'); await module.evaluate();
  const overview = module.namespace;
  const mapModule = [...cache.values()].find(m => m.identifier.endsWith('/regionalSkinMap.ts'));
  const R = mapModule.namespace;
  const u = R.bindRegionalSkinMap(fixtures.unknown, source), p = R.bindRegionalSkinMap(fixtures.combination, source);
  check(() => { assert(u); assert(p); assert(p.map.combinationMatched); });
  check(() => { assert.equal(u.map.complete,false); assert(Object.values(u.map.regions).every(r => r.state==='unknown' && r.fill==='lightgrey')); });
  check(() => { assert.equal(p.map.regions.leftCheek.fill,'blue'); assert.equal(p.map.regions.leftCheek.redness.colour,'red'); assert.equal(p.map.regions.rightCheek.fill,null); });
  check(() => { assert.equal(R.bindRegionalSkinMap(fixtures.partial,source).map.combinationMatched,false); });
  check(() => { const x=R.bindRegionalSkinMap(fixtures.conflict,source).map.regions.leftCheek; assert.equal(x.state,'unknown'); assert.equal(x.redness.colour,'red'); });
  for (const [key,value] of [['captureId','b'.repeat(64)],['pose','LEFT'],['sourceWidth',640],['sourceHeight',1280],['coordinateSpace','model-pixels']]) {
    check(() => assert.equal(R.validBoundRegionalSkinMap(p,{...source,[key]:value}),false));
  }
  for (const mutate of [
    x=>x.version='unknown-version', x=>x.geometry='predicted-pixel-mask', x=>x.sensitivityInferred=true,
    x=>x.complete=false, x=>x.combinationMatched=false, x=>x.tZone=['nose'],
    x=>x.regions.forehead.fill='blue', x=>x.regions.rightCheek.observations.dry.state='unknown',
    x=>x.regions.nose.observations.oil.coverage=0, x=>x.regions.nose.observations.oil.coverage=1.1,
    x=>x.regions.nose.observations.oil.coverage=NaN, x=>x.regions.nose.observations.oil.validationEvidence='',
    x=>x.regions.nose.observations.oil.methodVersion='', x=>delete x.regions.chin,
    x=>x.regions.leftCheek.redness.colour=null, x=>x.regions.leftCheek.redness.style='sensitivity-fill',
    x=>x.regions.rightCheek.reason='made-up-normal'
  ]) check(() => { const x=clone(fixtures.combination); mutate(x); assert.equal(R.parseRegionalSkinMap(x),undefined); });
  check(() => { const x=clone(fixtures.unknown); x.regions.forehead.state='normal'; x.regions.forehead.fill=null; assert.equal(R.parseRegionalSkinMap(x),undefined); });
  check(() => { const x=clone(fixtures.combination); x.photo='data:image/png;base64,secret'; x.regions.forehead.photo='secret'; assert(!JSON.stringify(R.parseRegionalSkinMap(x)).includes('secret')); });
  check(() => assert.deepEqual(Array.from(R.comparableRegionalObservations(u,u)),[]));
  check(() => assert.equal(R.comparableRegionalObservations(p,clone(p)).length,15));
  for (const mutate of [x=>x.photo='secret', x=>x.source.photo='secret', x=>x.map.photo='secret', x=>x.map.regions.forehead.observations.oil.photo='secret']) {
    check(() => { const x=clone(p); mutate(x); assert.equal(R.validBoundRegionalSkinMap(x,source),false); });
  }
  check(() => { const x=clone(p); x.map.regions.forehead.observations.oil.modelHash='other-model'; assert(!R.comparableRegionalObservations(p,x).includes('forehead:oil')); assert.equal(R.comparableRegionalObservations(p,x).length,14); });
  check(() => { const x=clone(p); x.map.regions.forehead.observations.oil.normalizationVersion='other-scale'; assert.equal(R.comparableRegionalObservations(p,x).length,14); });
  check(() => { const x=clone(p); x.map.regions.forehead.observations.oil.validationEvidence='different-evidence'; assert.equal(R.comparableRegionalObservations(p,x).length,14); });

  // Categorical history is anchored to one exact method identity and never
  // turns positive/negative observations into made-up numeric severity.
  const record=(id,date,map)=>({id,timestamp:date,general:{regionalSkinMap:map}});
  const pNegative=clone(p); pNegative.map.regions.forehead.observations.oil.state='negative';
  pNegative.map.regions.forehead.state='normal'; pNegative.map.regions.forehead.fill=null;
  pNegative.map.combinationMatched=false;
  const history=R.regionalObservationHistory([
    record('one','2026-10-20T10:00:00Z',p),record('two','2026-10-21T10:00:00Z',pNegative),record('three','2026-10-22T10:00:00Z',pNegative)
  ],'forehead','oil','three');
  check(() => { assert(history); assert.deepEqual(Array.from(history.points,v=>v.state),['positive','negative','negative']); });
  check(() => assert.deepEqual(Array.from(history.points,v=>v.changedFromPrevious),[null,true,false]));
  check(() => assert.equal(Object.values(history.points[0]).some(v=>typeof v==='number'&&v!==history.points[0].time),false));
  check(() => { const x=clone(p); x.map.regions.forehead.observations.oil.methodVersion='new-method'; const h=R.regionalObservationHistory([record('old','2026-10-20T10:00:00Z',p),record('new','2026-10-21T10:00:00Z',x)],'forehead','oil','new'); assert.equal(h.points.length,1); assert.equal(h.excludedIncompatible,1); });
  check(() => assert.equal(R.regionalObservationHistory([record('one','bad-date',p)],'forehead','oil'),undefined));
  check(() => assert.equal(R.regionalObservationHistory([record('one','2026-10-20T10:00:00Z',u)],'forehead','oil'),undefined));
  check(() => assert.equal(R.regionalObservationHistory([record('one','2026-10-20T10:00:00Z',p)],'periorbital','oil'),undefined));

  // Presentation plan remains source-bound and uses only anatomical summaries.
  const all = R.regionalSkinLayers(p,source,'overview',null);
  check(() => assert.equal(all.length,5));
  check(() => { const x=all.find(v=>v.region==='leftCheek'); assert.equal(x.fill,'blue'); assert.equal(x.redness,'positive'); assert.equal(x.geometry,'anatomical-region-summary-not-pixel-mask'); });
  check(() => { const x=all.find(v=>v.region==='rightCheek'); assert.equal(x.fill,null); assert.equal(x.state,'normal'); });
  const oil = R.regionalSkinLayers(p,source,'overview','oil');
  check(() => { assert.equal(oil.find(v=>v.region==='forehead').fill,'green'); assert.equal(oil.find(v=>v.region==='leftCheek').fill,null); assert(oil.every(v=>v.redness==='negative')); });
  const dry = R.regionalSkinLayers(p,source,'leftCheek','dry');
  check(() => { assert.equal(dry.length,1); assert.equal(dry[0].fill,'blue'); assert.equal(dry[0].redness,'negative'); });
  const red = R.regionalSkinLayers(p,source,'leftCheek','redness');
  check(() => { assert.equal(red[0].fill,null); assert.equal(red[0].redness,'positive'); });
  check(() => { const x=R.regionalSkinLayers(u,source,'forehead','redness')[0]; assert.equal(x.fill,'lightgrey'); assert.equal(x.redness,'unknown'); });
  check(() => assert.deepEqual(Array.from(R.regionalSkinLayers(p,{...source,captureId:'b'.repeat(64)},'overview',null)),[]));
  check(() => assert.deepEqual(Array.from(R.regionalSkinLayers(p,source,'periorbital',null)),[]));
  check(() => assert.deepEqual(Array.from(R.regionalSkinLayers(p,source,'overview','acne')),[]));

  // Retained-photo replay keeps the raster, crop and anatomical layer meshes
  // in the same source-pixel coordinate system at multiple source ratios.
  const replayCases=[
    {width:720,height:1280,crop:{x:.1,y:.05,width:.8,height:.9}},
    {width:1280,height:720,crop:{x:.08,y:.1,width:.84,height:.8}},
    {width:900,height:900,crop:{x:.05,y:.05,width:.9,height:.9}}
  ];
  const replaySnapshots=replayCases.map(({width,height,crop})=>{
    const bound=R.bindRegionalSkinMap(fixtures.combination,{captureId:'c'.repeat(64),pose:'FRONT',sourceWidth:width,sourceHeight:height,coordinateSpace:'source-pixels'});
    const x=crop.x*width,y=crop.y*height,w=crop.width*width,h=crop.height*height;
    const meshes=Object.fromEntries(['forehead','nose','chin','leftCheek','rightCheek'].map((id,index)=>[id,{points:[
      {x:x+w*(.18+index*.11),y:y+h*.25},{x:x+w*(.24+index*.11),y:y+h*.25},
      {x:x+w*(.24+index*.11),y:y+h*.42},{x:x+w*(.18+index*.11),y:y+h*.42}
    ],edges:[[0,1],[1,2],[2,3],[3,0]],major:[],boundary:[],excluded:[]}]))
    return {angle:'FRONT',photoId:'c'.repeat(64),dataUrl:'data:image/png;base64,AA==',width,height,
      crop:{x:0,y:0,width,height},previewCrop:crop,meshes,general:{regionalSkinMap:bound}};
  });
  for(const [index,snapshot] of replaySnapshots.entries()){
    const replay=R.retainedRegionalSkinReplay(snapshot,'overview',null);
    check(() => { assert(replay); assert.equal(replay.layers.length,5); assert.equal(replay.source.sourceWidth,snapshot.width); assert.equal(replay.source.sourceHeight,snapshot.height); });
    check(() => assert.deepEqual(JSON.parse(JSON.stringify(replay.viewBox)),{x:snapshot.previewCrop.x*snapshot.width,y:snapshot.previewCrop.y*snapshot.height,width:snapshot.previewCrop.width*snapshot.width,height:snapshot.previewCrop.height*snapshot.height}));
    check(() => { const scale=320/replay.viewBox.width,point=snapshot.meshes.forehead.points[0]; const projected={x:(point.x-replay.viewBox.x)*scale,y:(point.y-replay.viewBox.y)*scale}; assert(projected.x>=0&&projected.x<=320); assert(projected.y>=0&&projected.y<=320/replay.viewBox.width*replay.viewBox.height); });
  }
  check(() => { const x=clone(replaySnapshots[0]);x.photoId='d'.repeat(64);assert.equal(R.retainedRegionalSkinReplay(x,'overview',null),undefined); });
  check(() => { const x=clone(replaySnapshots[0]);x.previewCrop.width=1;assert.equal(R.retainedRegionalSkinReplay(x,'overview',null),undefined); });
  check(() => { const x=clone(replaySnapshots[0]);x.meshes.forehead.points[0].x=x.width+1;assert.equal(R.retainedRegionalSkinReplay(x,'overview',null),undefined); });
  check(() => { const x=clone(replaySnapshots[0]);x.dataUrl='https://example.invalid/photo.png';assert.equal(R.retainedRegionalSkinReplay(x,'overview',null),undefined); });

  const ids=['tone','oil','redness','acne','sag','dry','lines','dark','bags'];
  const response = { photoId: source.captureId, sourceWidth: source.sourceWidth, sourceHeight: source.sourceHeight,
    general: { regionalSkinMap: fixtures.combination, normalizationVersion:'fixture-scale',
      skinType:{value:null,quality:'insufficient',confidence:null,methodVersion:'unavailable',modelHash:null},
      measurements:ids.map(id=>({id,value:null,quality:'insufficient',methodVersion:'fixture-only',unit:'appearance-score-0-100',evaluatedArea:{analysisPixels:0},limitationCode:'NO_ACCEPTED_METHOD'})) } };
  const before=JSON.stringify(response), converted=overview.overviewFromResponse(response);
  check(() => assert.equal(JSON.stringify(response),before));
  check(() => assert.deepEqual(JSON.parse(JSON.stringify(converted.regionalSkinMap)),JSON.parse(JSON.stringify(p))));
  converted.analysisId='analysis-fixture';
  check(() => assert(overview.validSkinOverview(JSON.parse(JSON.stringify(converted)),'analysis-fixture')));
  check(() => { const x=clone(converted); x.captureId='b'.repeat(64); assert.equal(overview.validSkinOverview(x,'analysis-fixture'),false); });
  check(() => { const x=clone(converted); x.sourceTransform.sourceWidth=720; assert.equal(overview.validSkinOverview(x,'analysis-fixture'),false); });
  check(() => { const x=clone(converted); delete x.regionalSkinMap; assert(overview.validSkinOverview(x,'analysis-fixture')); });
  check(() => { const x=clone(response); delete x.general.regionalSkinMap; assert.equal(overview.overviewFromResponse(x).regionalSkinMap,undefined); });
  check(() => { const x=clone(response); x.general.regionalSkinMap.regions.forehead.fill='blue'; assert.equal(overview.overviewFromResponse(x).regionalSkinMap,undefined); });
  check(() => { const x=clone(response); x.photoId='not-a-capture'; assert.equal(overview.overviewFromResponse(x).regionalSkinMap,undefined); });
  check(() => assert.equal(overview.overviewFromResponse({}),undefined));
  console.log(JSON.stringify({ checks, serverFixtures:4, replayAspectRatios:3, result:'pass', scope:'numeric-contract-converter-svg-layer-categorical-history-and-retained-photo-replay', modelAcceptance:false, cameraAcceptance:false }));
})().catch(error => { console.error(error); process.exitCode=1; });

