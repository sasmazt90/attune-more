// Regression: "Kapanışı atla" pressed while the BITE frame is still inside a
// delayed captureDental() must start exactly one analysis, with the three
// sealed sources, and the late BITE capture must not be appended.
const assert=require('node:assert/strict');
require(process.cwd()+'/tests/unit/ts_loader');
const {DentalCaptureSession}=require(process.cwd()+'/apps/vehicle-app/src/utils/dentalCaptureSession.ts');
const capture=(pose,id)=>({photo:'data:image/png;base64,AA==',photoId:id.repeat(64),width:1920,height:1080,pose,landmarks:[],conditions:{}});
const delayedCaptureDental=(pose,id,gate)=>gate.then(()=>capture(pose,id)); // stands in for the SHA-256/PNG encoding await

(async()=>{
 // 1) Race: skip during the pending BITE encoding.
 const analyses=[];const session=new DentalCaptureSession((sources,missing)=>analyses.push({sources,missing}));
 for(const [pose,id] of [['FRONT','a'],['RIGHT','b'],['LEFT','c']])assert.equal(session.accept(capture(pose,id)),'added');
 let release;const gate=new Promise(r=>{release=r;});
 const pending=delayedCaptureDental('BITE','d',gate);           // loop awaits captureDental(...)
 assert.equal(session.skipBite(),true);                          // user presses "skip" meanwhile
 release();const late=await pending;                             // encoding finishes afterwards
 assert.equal(session.accept(late),'closed');                    // continuation is a no-op
 assert.equal(analyses.length,1,'exactly one analysis');
 assert.deepEqual(analyses[0].sources.map(s=>s.pose),['FRONT','RIGHT','LEFT']);
 assert.deepEqual(analyses[0].missing,['BITE']);
 assert.ok(Object.isFrozen(analyses[0].sources),'analysis sources are immutable');
 assert.throws(()=>analyses[0].sources.push(late));
 assert.equal(session.skipBite(),false,'second skip cannot start another analysis');

 // 2) Normal completion seals once; nothing after it is accepted.
 const done=[];const full=new DentalCaptureSession(s=>done.push(s));
 assert.equal(full.skipBite(),false,'skip only at the BITE step');
 for(const [pose,id] of [['FRONT','a'],['RIGHT','b'],['LEFT','c']])full.accept(capture(pose,id));
 assert.equal(full.accept(capture('BITE','d')),'complete');
 assert.equal(full.skipBite(),false);assert.equal(full.accept(capture('BITE','e')),'closed');
 assert.equal(done.length,1);assert.deepEqual(done[0].map(s=>s.pose),['FRONT','RIGHT','LEFT','BITE']);

 // 3) Same photo for two poses and out-of-order poses are refused.
 const dup=new DentalCaptureSession(()=>assert.fail('must not seal'));
 dup.accept(capture('FRONT','a'));
 assert.equal(dup.accept(capture('RIGHT','a')),'duplicate');
 assert.equal(dup.accept(capture('LEFT','b')),'wrong-pose');

 // 4) Cancel/stop closes the session: a late capture cannot start an analysis.
 const cancelled=new DentalCaptureSession(()=>assert.fail('cancelled scan must not analyse'));
 for(const [pose,id] of [['FRONT','a'],['RIGHT','b'],['LEFT','c']])cancelled.accept(capture(pose,id));
 cancelled.close();assert.equal(cancelled.accept(capture('BITE','d')),'closed');assert.equal(cancelled.skipBite(),false);
 // 5) Any pose can be skipped (no endless loop); skipped poses are reported missing.
 const sk=[];const any=new DentalCaptureSession((sources,missing)=>sk.push({sources,missing}));
 any.accept(capture('FRONT','a'));
 let releaseRight;const rightGate=new Promise(r=>{releaseRight=r;});const pendingRight=delayedCaptureDental('RIGHT','b',rightGate);
 assert.equal(any.skipCurrent(),true);assert.equal(any.nextPose,'LEFT');           // RIGHT skipped while encoding
 releaseRight();assert.equal(any.accept(await pendingRight),'wrong-pose');         // late RIGHT frame dropped
 any.accept(capture('LEFT','c'));assert.equal(any.skipCurrent(),true);             // BITE skipped
 assert.equal(sk.length,1);assert.deepEqual(sk[0].sources.map(s=>s.pose),['FRONT','LEFT']);assert.deepEqual(sk[0].missing,['RIGHT','BITE']);
 // 6) Everything skipped: sealed with no sources (page shows an error, no analysis).
 const none=[];const empty=new DentalCaptureSession((sources,missing)=>none.push({sources,missing}));
 for(let i=0;i<4;i++)assert.equal(empty.skipCurrent(),true);
 assert.equal(empty.skipCurrent(),false);assert.equal(none.length,1);assert.equal(none[0].sources.length,0);assert.deepEqual(none[0].missing,['FRONT','RIGHT','LEFT','BITE']);
 console.log('dental_capture_session: PASS');
})().catch(error=>{console.error(error);process.exit(1);});
