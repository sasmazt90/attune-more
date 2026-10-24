// Actual current product pose helper: a valid side view is not a front view.
require('./ts_loader.js');
const assert=require('assert/strict');
const {matchesSkinAngle,skinPoseRotation,angleGuidance}=require('../../apps/vehicle-app/src/utils/skinMultiAngle.ts');
const base={faceDetected:true,isMediaPipeActive:true,yaw:0,pitch:0,roll:0,scaleRatio:.5,sourceFramed:true,isAligned:false};
assert.equal(matchesSkinAngle({...base,yaw:.40},'LEFT'),true);
assert.equal(matchesSkinAngle({...base,yaw:-.40},'RIGHT'),true);
assert.equal(matchesSkinAngle({...base,yaw:.40},'FRONT'),false);
assert.equal(matchesSkinAngle({...base,yaw:-.40},'LEFT'),false);
assert.equal(matchesSkinAngle({...base,yaw:.40,pitch:.23},'LEFT'),false);
assert.equal(matchesSkinAngle({...base,yaw:.40,roll:.16},'LEFT'),false);
assert.equal(matchesSkinAngle({...base,yaw:.40,sourceFramed:false},'LEFT'),false);
assert.equal(matchesSkinAngle({...base,yaw:.70},'LEFT'),false);

// Helper to construct a column-major 4x4 rotation matrix around Y by yawDeg:
function makeTransform(yawDeg){
  const rad=yawDeg*Math.PI/180;
  const c=Math.cos(rad),s=Math.sin(rad);
  return [c,0,-s,0, 0,1,0,0, s,0,c,0, 0,0,-40,1];
}
// Real gate-check-1. England-side-2-a0e0f8857bdd frame: yaw=0.79, faceTransform yawDeg=+24.21°
const realEnglandSide2={...base,yaw:.79,faceTransform:makeTransform(24.21)};
assert.equal(skinPoseRotation(realEnglandSide2).yawDeg,24.21);
assert.equal(matchesSkinAngle(realEnglandSide2,'LEFT'),true);
assert.equal(matchesSkinAngle(realEnglandSide2,'RIGHT'),false);
assert.equal(matchesSkinAngle(realEnglandSide2,'FRONT'),false);

// Boundary checks with 3D faceTransform:
assert.equal(matchesSkinAngle({...base,yaw:-.70,faceTransform:makeTransform(-21.6)},'RIGHT'),true);
assert.equal(matchesSkinAngle({...base,yaw:.10,faceTransform:makeTransform(6.0)},'LEFT'),false);
assert.equal(matchesSkinAngle({...base,yaw:.95,faceTransform:makeTransform(42.0)},'LEFT'),false);
assert(angleGuidance({...base,yaw:.95,faceTransform:makeTransform(42.0)},'LEFT').includes('15°–35°'));
console.log(JSON.stringify({actualProductPoseHelper:true,sideFrontGateRegression:true,rigid3DYawVerified:true,checks:15}));
