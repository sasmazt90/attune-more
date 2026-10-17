"""Generated geometry/pixel-field test, explicitly not a natural face/hand detector test."""
from test_vision_technical_closeout import node

def test_actual_tracker_baseline_mouth_distance_loss_and_new_session():
    node(r"""
const w=640,h=480,ctx={canvas:{width:w,height:h},blank:false,getImageData(x,y,width,height){width=Math.ceil(width);height=Math.ceil(height);const data=new Uint8ClampedArray(width*height*4);for(let j=0;j<height;j++)for(let i=0;i<width;i++){const k=(j*width+i)*4,v=this.blank?0:90+((Math.floor(x)+i)*17+(Math.floor(y)+j)*31)%100;data[k]=data[k+1]=data[k+2]=v;data[k+3]=255;}return {width,height,data};}};
const points=Array.from({length:478},()=>({x:.5,y:.5,z:0}));
for(const [id,x,y] of [[10,.5,.2],[152,.5,.8],[168,.5,.35],[1,.5,.5],[4,.5,.52],[2,.5,.56],[234,.2,.5],[454,.8,.5],[127,.23,.42],[356,.77,.42],[93,.26,.55],[323,.74,.55],[33,.3,.4],[133,.43,.4],[160,.33,.38],[158,.4,.38],[153,.4,.42],[144,.33,.42],[362,.57,.4],[263,.7,.4],[385,.60,.38],[387,.67,.38],[373,.67,.42],[380,.60,.42],[70,.34,.34],[300,.66,.34]])points[id]={x,y,z:0};
const model=(p,t)=>({landmarks:[p],hands:[],blinkRight:.02,blinkLeft:.02,inferenceMs:1,frameTime:t});const tracker=new T.VisionTracker();let evidence;
for(let t=100;t<=1300;t+=200)evidence=tracker.assess(ctx,w,h,model(points,t),t,null);
assert.equal(evidence.conditions.distanceState,'stable');assert(evidence.conditions.positionValid);assert.equal(evidence.conditions.right.state,'open');assert.equal(evidence.conditions.left.state,'open');
const mouth=structuredClone(points);mouth[152].y=.9;evidence=tracker.assess(ctx,w,h,model(mouth,1400),1400,null);assert(Math.abs(evidence.conditions.relativeScaleChange)<1e-12);assert.equal(evidence.conditions.distanceState,'stable');
const scaled=points.map(p=>({...p,x:.5+(p.x-.5)*1.22,y:.5+(p.y-.5)*1.22}));
for(let t=1500;t<=2100;t+=200)evidence=tracker.assess(ctx,w,h,model(scaled,t),t,null);
assert.equal(evidence.conditions.distanceState,'near');assert.equal(evidence.conditions.positionValid,false);assert(Math.abs(evidence.conditions.relativeScaleChange-.22)<1e-9);
for(const t of [2200,2400,2550])evidence=tracker.assess(ctx,w,h,model(points,t),t,null);
assert.equal(evidence.conditions.distanceState,'stable');assert(evidence.conditions.positionValid);
ctx.blank=true;evidence=tracker.assess(ctx,w,h,{...model(points,2700),landmarks:[]},2700,null);assert.equal(evidence.conditions.faceCount,0);assert.equal(evidence.conditions.right.state,'uncertain');assert.equal(evidence.conditions.left.state,'uncertain');assert.equal(evidence.conditions.positionValid,false);
ctx.blank=false;const fresh=new T.VisionTracker();evidence=fresh.assess(ctx,w,h,model(points,3000),3000,null);assert.equal(evidence.conditions.distanceState,'learning');assert.equal(evidence.conditions.blocker,'preparing');assert.equal(evidence.conditions.right.state,'uncertain');
""")
