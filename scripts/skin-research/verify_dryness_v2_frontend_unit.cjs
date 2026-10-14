// Actual API contract -> frontend attachment -> persistence/history validation.
// This focused contract check does not stand in for browser acceptance.
const fs=require('fs'),assert=require('assert');
global.window=global;global.addEventListener=()=>{};global.__auditMediaPipe={};
eval(fs.readFileSync('.runtime/periorbital-v5-browser-support/utilities.js','utf8'));
const E=__auditRequire('apps/vehicle-app/src/utils/skinExpression.ts'),I=__auditRequire('apps/vehicle-app/src/utils/skinIndicators.ts'),A=__auditRequire('apps/vehicle-app/src/utils/appearanceMeasurements.ts'),O=__auditRequire('apps/vehicle-app/src/utils/skinOverview.ts');
const categories=E.EXPRESSION_FIELDS.map(categoryName=>({categoryName,score:.01}));
assert(E.expressionScores(categories));assert.strictEqual(E.expressionScores(categories.slice(1)),undefined);assert.strictEqual(E.expressionObservation(undefined,'a'),undefined);
assert.strictEqual(E.expressionObservation(E.expressionScores(categories),undefined),undefined);
assert.strictEqual(E.expressionObservation(E.expressionScores(categories),'source-bound-photo').photoId,'source-bound-photo');
const result=JSON.parse(fs.readFileSync('audit-results/dryness-integration-v2-20261014/normal-shortcut-cold-result.json','utf8'));
const indicators=Object.fromEntries(Object.entries(result.measurements).map(([region,rows])=>[region,rows.map(row=>({id:row.id,label:I.skinCriterionLabel(row.id),score:null,reason:'not yet attached',method:'unavailable',unit:'%',sampleCount:0}))]));
A.attachAppearance(indicators,result);assert(I.validSkinIndicators(indicators));
const general=O.overviewFromResponse(result);general.analysisId='isolated-contract';assert(O.validSkinOverview(general,'isolated-contract'));
for(const rows of Object.values(indicators))for(const row of rows)assert.strictEqual(row.measurement.rawValue,row.appearance.value);
const dry=indicators.chin.find(r=>r.id==='dry');const old=structuredClone(dry);old.method='appearance-cv-6';old.appearance.methodVersion='appearance-cv-6';old.appearance.normalizationVersion='native-flake-reference-area-v3';assert(!I.canCompareIndicator(dry,old));
assert(!I.supportedAppearanceMethod('tone','appearance-native-dry-2'));
const bad=structuredClone(dry);bad.id='tone';assert(!I.validMeasurement(bad,'chin'));
const S=__auditRequire('apps/vehicle-app/src/utils/skinSurfaceAnalysis.ts');
const quad={points:[{x:0,y:0},{x:10,y:0},{x:10,y:10},{x:0,y:10}],edges:[[0,1],[1,2],[2,3],[3,0]],major:[]};
assert.strictEqual(S.meshTriangles(quad,false,false).length,0);
assert.strictEqual(S.meshTriangles(quad,false,S.closedSurfaceSupportEnabled('dry','native-calibrated-material-source-area-v8')).length,2);
for(const version of ['contour-fold-visible-region-unique-centers-v7-expression-v2','contour-fold-lower-chin-observed-runs-v9-expression-v2'])assert.strictEqual(S.meshTriangles(quad,false,S.closedSurfaceSupportEnabled('sag',version)).length,2);
assert(!S.closedSurfaceSupportEnabled('dry','unknown'));assert(!S.closedSurfaceSupportEnabled('lines','native-calibrated-material-source-area-v8'));
fs.writeFileSync('audit-results/dryness-integration-v2-20261014/frontend-contract-unit.json',JSON.stringify({passed:true,sourceBoundExpression:true,missingNotNeutral:true,rawPrecisionPreserved:true,onlyDryMethodAdmitted:true,normalPersistValidationPassed:true,overviewPersistValidationPassed:true,newClosedAnatomicalClipsRetainQuadSupport:true,oldNormalizationSeparate:true,actualBrowser:false},null,2));
console.log('Actual API attachment + regional/Overview persistence + history contracts passed.');
