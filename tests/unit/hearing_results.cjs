const assert=require('node:assert/strict');
require(process.cwd()+'/tests/unit/ts_loader');
const R=require(process.env.HEARING_RESULTS_MODULE||process.cwd()+'/apps/vehicle-app/src/utils/hearingResults.ts');
const {HEARING_CONFIG:C}=require(process.cwd()+'/apps/vehicle-app/src/utils/hearingProtocol.ts');
const thresholds=['left','right'].flatMap(ear=>C.frequencies.map((frequency,i)=>({ear,frequency,value:-60,status:'threshold',unit:'dBFS-peak',trials:6,repeat:i===6})));
function fixture(id='current',timestamp='2026-10-27T12:00:00Z'){
 const presentations=[1,2,3].map((id,i)=>({id,ear:i<2?'left':'right',frequency:1000,level:-60,silent:false,scheduledAt:0,startedAt:100,deadline:2300,completedAt:2400,answered:true,duration:1,audioStartedAt:1,audioExpectedEnd:2,audioEndedAt:2,outputEndedAt:1100}));
 return {id,timestamp,unit:'dBFS-peak',methodVersion:C.version,presentationVersion:'source-complete-token-v1',thresholds:structuredClone(thresholds),presentations,presses:[{trialId:1,at:500,kind:'valid'},{trialId:2,at:900,kind:'valid'},{trialId:3,at:700,kind:'valid'}]};
}
const original=fixture(),snapshot=JSON.stringify(original);
assert.equal(R.meanHearingResponse(original,'left').count,2);assert.ok(Math.abs(R.meanHearingResponse(original,'left').seconds-.6)<1e-12);
assert.deepEqual(R.meanHearingResponse(original,'right'),{seconds:.6,count:1});
assert.equal(JSON.stringify(original),snapshot,'must never mutate stored records');
for(const alter of [
 r=>r.presses[0].kind='early',r=>r.presses[0].kind='late',r=>r.presses[0].kind='silent',r=>r.presses[0].kind='duplicate',
 r=>r.presses[0].at=99,r=>r.presses[0].at=2301,r=>r.presses[0].at=NaN,r=>r.presses[0].trialId=999,
 r=>r.presentations[0].silent=true,r=>r.presentations[0].answered=false,r=>r.presentations[0].invalidReason='interrupted',
 r=>r.presentations[0].id=-1,r=>r.presentations[0].duration=.1,r=>r.presentations[0].audioExpectedEnd=1.5,
 r=>r.presentations[0].completedAt=2298.99,r=>r.presentations[0].completedAt=null,r=>r.presentations[0].completedAt=2200,r=>r.presentations[0].startedAt=null,
 r=>r.presentations[0].outputEndedAt=2500,r=>r.presentations[0].audioEndedAt=1.5,r=>r.presentations[0].audioExpectedEnd=Infinity,
 r=>r.presentations.push({...r.presentations[0]}),r=>r.presses.push({...r.presses[0],at:600}),
 ]){const r=fixture();alter(r);assert.equal(R.validHearingResponses(r,'left').length,1,alter.toString());}
const rounded=fixture();rounded.presentations[0].completedAt=2299.2;assert.equal(R.validHearingResponses(rounded,'left').length,2,'submillisecond timer rounding retains an otherwise completed valid response');
const duplicates=fixture();duplicates.presses.push({trialId:1,at:600,kind:'duplicate'});assert.equal(R.validHearingResponses(duplicates,'left').length,2,'duplicate events do not replace/count as the first valid press');
const old=fixture();delete old.presentations;delete old.presses;assert.equal(R.meanHearingResponse(old,'left'),null);
const partial=fixture();partial.thresholds.pop();assert.equal(R.meanHearingResponse(partial,'left'),null);
const nulls=fixture();nulls.thresholds.find(t=>t.ear==='left'&&t.frequency===500).value=null;
assert.deepEqual(R.thresholdRows(nulls,'left'),[-60,null,-60,-60,-60,-60]);
assert.deepEqual(R.thresholdPaths([-60,null,-65,-70],i=>i,v=>v),['M0 -60','M2 -65 L3 -70']);
assert.ok(R.hearingLevelY(-30)<R.hearingLevelY(-90),'higher digital levels at top');
assert.equal(R.hearingLevelY(-30),12);assert.equal(R.hearingLevelY(-90),192);
const older=fixture('older','2026-10-25T12:00:00Z'),nearest=fixture('nearest','2026-10-26T12:00:00Z');delete nearest.presentations;delete nearest.presses;delete nearest.presentationVersion;
const incompatible=fixture('other','2026-10-26T13:00:00Z');incompatible.deviceSession='different-output';
assert.equal(R.previousHearingRecord(original,[original,older,nearest,incompatible]).id,'nearest');
assert.equal(R.meanHearingResponse(R.previousHearingRecord(original,[older,nearest]),'left'),null,'missing nearest timing stays missing');
console.log('PASS: selected-record means, event exclusions, missing data, chart gaps/direction, prior-record scope');
module.exports={fixture};
