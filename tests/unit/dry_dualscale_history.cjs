// Current history/attachment consumers, frozen staging response; no UI/storage.
require('./ts_loader.js');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'../..'),out=path.resolve(root,'../cdc-progress/skin-dryness-dualscale-20261018');
const S=require('../../apps/vehicle-app/src/utils/skinIndicators.ts'),O=require('../../apps/vehicle-app/src/utils/skinOverview.ts'),A=require('../../apps/vehicle-app/src/utils/appearanceMeasurements.ts');
const index=JSON.parse(fs.readFileSync(path.join(out,'runtime-input-index.json'),'utf8')),input=index.inputs.find(r=>r.eligibleForThirdCheck);
const old=JSON.parse(fs.readFileSync(input.savedResultPath,'utf8')),candidate=JSON.parse(fs.readFileSync(path.join(out,input.photoId.slice(0,8)+'-staging-result.json'),'utf8')),oldFrozen=JSON.stringify(old);
const make=(r,scope)=>({id:'dry',score:r.value,method:r.methodVersion,unit:r.unit,appearance:r,measurement:{scope,region:r.region,methodVersion:r.methodVersion,modelHash:r.modelHash,unit:r.unit,validation:'appearance-proxy'}});
for(const region of Object.keys(old.measurements)){
 const x=make(old.measurements[region].find(r=>r.id==='dry'),'regional'),y=make(candidate.measurements[region].find(r=>r.id==='dry'),'regional');
 assert(S.canCompareIndicator(x,x));assert(!S.canCompareIndicator(x,y));assert(!S.supportedAppearanceMethod('dry',y.method));
 A.compareAppearance(y,x,true,'isolated-old-reference');assert.equal(y.referenceDelta,undefined);
}
const x=O.overviewFromResponse(old).indicators.find(r=>r.id==='dry'),y=O.overviewFromResponse(candidate).indicators.find(r=>r.id==='dry');
assert(S.canCompareIndicator(x,x));assert(!S.canCompareIndicator(x,y));assert.notEqual(S.samplingSupportVersion(x.appearance),S.samplingSupportVersion(y.appearance));
const target=Object.fromEntries(Object.keys(candidate.measurements).map(k=>[k,[{id:'dry'}]]));
assert.throws(()=>A.attachAppearance(target,candidate),/INVALID_MEASUREMENT/); // Deliberately NOT admitted to normal persistence.
assert.equal(JSON.stringify(old),oldFrozen);
console.log('PASS regional+overview history separation; staging attachment rejected by unchanged product allowlist; old data unchanged');
