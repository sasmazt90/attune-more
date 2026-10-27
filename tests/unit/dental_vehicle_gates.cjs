// In-car capture pose limits (vehicle-capture-v2): camera above/beside the
// eye line (pitch) and head tilt while turning (roll) must not block a pose,
// and there is no yaw dead zone between FRONT and the side poses.
const assert=require('node:assert/strict');
require(process.cwd()+'/tests/unit/ts_loader');
const D=require(process.cwd()+'/apps/vehicle-app/src/utils/dentalCapture.ts');
const rad=d=>d*Math.PI/180;
// Column-major rigid transform R=Ry(yaw)·Rx(pitch)·Rz(roll), the Euler order dentalPose() reads.
function transform(yawDeg,pitchDeg,rollDeg){
 const y=rad(yawDeg),p=rad(pitchDeg),r=rad(rollDeg);
 const Ry=[[Math.cos(y),0,Math.sin(y)],[0,1,0],[-Math.sin(y),0,Math.cos(y)]],Rx=[[1,0,0],[0,Math.cos(p),-Math.sin(p)],[0,Math.sin(p),Math.cos(p)]],Rz=[[Math.cos(r),-Math.sin(r),0],[Math.sin(r),Math.cos(r),0],[0,0,1]];
 const mul=(A,B)=>A.map((row,i)=>B[0].map((_,j)=>row.reduce((s,_,k)=>s+A[i][k]*B[k][j],0)));const R=mul(Ry,mul(Rx,Rz));
 const m=new Array(16).fill(0);for(let c=0;c<3;c++)for(let row=0;row<3;row++)m[c*4+row]=R[row][c];m[15]=1;return m;
}
const a=(y,p,r)=>({faceDetected:true,isMediaPipeActive:true,faceTransform:transform(y,p,r)});
const read=D.dentalPose(a(30,20,12));assert.ok(Math.abs(read.yawDeg-30)<2&&Math.abs(Math.abs(read.pitchDeg)-20)<3,JSON.stringify(read));
assert.equal(D.DENTAL_GATES.version,'vehicle-capture-v2');
// Previously rejected natural poses (pitch 12.6°/roll 8.6° limits).
assert.equal(D.matchesDentalAngle(a(0,20,0),'FRONT'),true,'camera above eye line');
assert.equal(D.matchesDentalAngle(a(35,-8,12),'LEFT'),true,'turned head with natural tilt');
assert.equal(D.matchesDentalAngle(a(-35,5,-12),'RIGHT'),true);
// No dead zone: 13° is a side pose, 10° is frontal.
assert.equal(D.matchesDentalAngle(a(13,0,0),'LEFT'),true);assert.equal(D.matchesDentalAngle(a(10,0,0),'FRONT'),true);
assert.equal(D.matchesDentalAngle(a(10,0,0),'LEFT'),false);
// Limits still exist.
assert.equal(D.matchesDentalAngle(a(0,32,0),'FRONT'),false,'pitch beyond 24°');
assert.equal(D.matchesDentalAngle(a(30,0,22),'LEFT'),false,'roll beyond 15°');
assert.equal(D.matchesDentalAngle(a(55,0,0),'LEFT'),false,'yaw beyond 45°');
assert.equal(D.matchesDentalAngle(a(30,0,0),'RIGHT'),false,'wrong side');
console.log('dental_vehicle_gates: PASS');
