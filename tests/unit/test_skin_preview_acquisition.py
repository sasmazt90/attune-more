"""Source framing and display crop checks, not physical camera acceptance."""
from test_spoken_letter_product import run

def test_cabin_framing_preserves_pose_quality_and_source_scale(tmp_path):
 run(tmp_path,"""
const A=load('skinAnalyzer'),M=load('skinMultiAngle');
const pts=Array.from({length:468},(_,i)=>({x:.4+(i%2)*.18,y:.2+(i%3)*.14,z:0}));
assert(A.skinSourceFramed(pts,640,480));
assert(!A.skinSourceFramed(pts.map(p=>({...p,x:p.x-.45})),640,480));
assert(!A.skinSourceFramed(pts.slice(0,100),640,480));
const a={faceDetected:true,isMediaPipeActive:true,sourceFramed:true,landmarks:pts,yaw:0,pitch:0,roll:0,scaleRatio:.18};
assert(M.matchesSkinAngle(a,'FRONT'));assert(!M.matchesSkinAngle({...a,yaw:.4},'FRONT'));
assert(M.matchesSkinAngle({...a,yaw:-.4},'RIGHT'));assert(!M.matchesSkinAngle({...a,yaw:-.4},'LEFT'));
assert(!M.matchesSkinAngle({...a,sourceFramed:false},'FRONT'));assert(!M.matchesSkinAngle({...a,pitch:.4},'FRONT'));
assert(!M.matchesSkinAngle({...a,roll:.4},'FRONT'));assert(!M.matchesSkinAngle({...a,isMediaPipeActive:false},'FRONT'));
assert.equal(a.scaleRatio,.18);assert(!M.angleGuidance(a,'FRONT').includes('yaklaşın'));
""")

def test_covered_lid_transition_does_not_restart_valid_occlusion(tmp_path):
 run(tmp_path,"""
load('skinAnalyzer');load('visionFrameQuality');const T=load('visionTracking');
const hold=new T.SustainedEyeState();
for(let at=0;at<600;at+=100)assert.equal(hold.update(at%200?'closed':'covered',at).state,'uncertain');
assert.equal(hold.update('covered',600).state,'covered');assert.equal(hold.update('closed',700).state,'closed');
hold.update('open',800);assert.equal(hold.update('closed',900).state,'uncertain');
hold.update('covered',1000);assert.equal(hold.update('covered',1500).state,'uncertain');
""")

def test_real_covered_head_outlier_does_not_remove_distance_gate(tmp_path):
 run(tmp_path,"""
load('skinAnalyzer');load('visionFrameQuality');const T=load('visionTracking');
// Actual after9 covered-eye source ratios: one model pair jumped to .426.
const observed=[.038973386,-.051414392,.182829693,.174342548,.425833266,.078403772,.062328884];
const relative=T.headScaleConsensus(observed);assert(relative!==null&&Math.abs(relative)<.15);
assert.equal(T.headScaleConsensus([.2,.21,.19,.9]),.2);assert.equal(T.headScaleConsensus([-.2,-.21,-.19,-.9]),-.2);
assert.equal(T.headScaleConsensus([0,.01,.7,.8]),null);assert.equal(T.headScaleConsensus([0,.01,.7]),null);
assert.equal(T.headScaleConsensus([0,NaN,0,0]),null);assert.equal(T.headScaleConsensus([0,0]),null);
const d=new T.HeadDistanceHysteresis();for(let t=0;t<=700;t+=100)d.update(T.headScaleConsensus([.2,.21,.19,.9]),t);assert.equal(d.update(.2,800),'near');
""")
