// Actual current product pose helper: a valid side view is not a front view.
require('./ts_loader.js');
const assert=require('assert/strict');
const {matchesSkinAngle}=require('../../apps/vehicle-app/src/utils/skinMultiAngle.ts');
const base={faceDetected:true,isMediaPipeActive:true,yaw:0,pitch:0,roll:0,scaleRatio:.5,sourceFramed:true,isAligned:false};
assert.equal(matchesSkinAngle({...base,yaw:.40},'LEFT'),true);
assert.equal(matchesSkinAngle({...base,yaw:-.40},'RIGHT'),true);
assert.equal(matchesSkinAngle({...base,yaw:.40},'FRONT'),false);
assert.equal(matchesSkinAngle({...base,yaw:-.40},'LEFT'),false);
assert.equal(matchesSkinAngle({...base,yaw:.40,pitch:.23},'LEFT'),false);
assert.equal(matchesSkinAngle({...base,yaw:.40,roll:.16},'LEFT'),false);
assert.equal(matchesSkinAngle({...base,yaw:.40,sourceFramed:false},'LEFT'),false);
assert.equal(matchesSkinAngle({...base,yaw:.70},'LEFT'),false);
console.log(JSON.stringify({actualProductPoseHelper:true,sideFrontGateRegression:true,checks:8}));
