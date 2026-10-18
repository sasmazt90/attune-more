// Actual frontend attachment/persistence validators; no camera/storage/API call.
require('./ts_loader.js');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'../..'),out=path.resolve(root,'../cdc-progress/skin-dryness-dualscale-20261018');
const S=require('../../apps/vehicle-app/src/utils/skinIndicators.ts'),O=require('../../apps/vehicle-app/src/utils/skinOverview.ts'),A=require('../../apps/vehicle-app/src/utils/appearanceMeasurements.ts');
const fixture=JSON.parse(fs.readFileSync(path.join(out,'promoted-contract-replay.json'),'utf8')),candidate=fixture.result;
assert.equal(fixture.modelInferenceCalls,0);assert(S.supportedAppearanceMethod('dry','appearance-native-dry-2'));assert(S.supportedAppearanceMethod('dry','appearance-native-dry-3'));assert(!S.supportedAppearanceMethod('acne','appearance-native-dry-3'));
const indicators=Object.fromEntries(Object.keys(candidate.measurements).map(region=>[region,candidate.measurements[region].map(r=>({id:r.id,label:S.skinCriterionLabel(r.id),score:null,reason:'isolated contract fixture',method:'placeholder',unit:'%'}))]));
A.attachAppearance(indicators,candidate);assert(S.validSkinIndicators(indicators));
const overview=O.overviewFromResponse(candidate);overview.analysisId='isolated-dualscale-contract';assert(O.validSkinOverview(overview,overview.analysisId));
const saved=JSON.parse(JSON.stringify({indicators,general:overview}));assert(S.validSkinIndicators(saved.indicators));assert(O.validSkinOverview(saved.general,overview.analysisId));
const input=JSON.parse(fs.readFileSync(path.join(out,'runtime-input-index.json'),'utf8')).inputs.find(r=>r.eligibleForThirdCheck),old=JSON.parse(fs.readFileSync(input.savedResultPath,'utf8')),oldCopy=JSON.stringify(old);
const prior=Object.fromEntries(Object.keys(old.measurements).map(region=>[region,old.measurements[region].map(r=>({id:r.id,label:S.skinCriterionLabel(r.id),score:null,reason:'old isolated fixture',method:'placeholder',unit:'%'}))]));A.attachAppearance(prior,old);
for(const region of Object.keys(indicators)){
 const x=prior[region].find(r=>r.id==='dry'),y=indicators[region].find(r=>r.id==='dry');assert(S.canCompareIndicator(x,x));assert(S.canCompareIndicator(y,y));assert(!S.canCompareIndicator(x,y));
}
const priorOverview=O.overviewFromResponse(old).indicators.find(r=>r.id==='dry'),newOverview=overview.indicators.find(r=>r.id==='dry');assert(!S.canCompareIndicator(priorOverview,newOverview));assert.equal(JSON.stringify(old),oldCopy);
const p=fs.readFileSync('services/core-api/product_dryness.py','utf8');assert(p.includes('analyze_product_candidate(value,base_analyzer,check,promoted=True)'));
const receipt={newRegionalRoundtrip:true,newOverviewRoundtrip:true,oldNative2StillReadable:true,crossMethodComparisonRejected:true,oldRecordUnchanged:true,modelCalls:0,apiCalls:0,historyWrites:0};
fs.writeFileSync(path.join(out,'product-contract-checks.json'),JSON.stringify(receipt,null,2));console.log('PASS normal dry3 attachment + regional/overview roundtrip + native2 history separation; default caller uses shared admitted kernel');
