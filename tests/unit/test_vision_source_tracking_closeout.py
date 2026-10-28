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


def test_small_eye_closure_keeps_source_pixels_and_independent_open_eye():
    # Generated source pixels/model geometry reproduce the ROI-collapse defect.
    # This is not physical camera/eyelid detection accuracy evidence.
    node(r"""
const w=640,h=480,ctx={canvas:{width:w,height:h},blank:false,getImageData(x,y,width,height){width=Math.ceil(width);height=Math.ceil(height);const data=new Uint8ClampedArray(width*height*4);for(let j=0;j<height;j++)for(let i=0;i<width;i++){const k=(j*width+i)*4,v=this.blank?0:90+((Math.floor(x)+i)*17+(Math.floor(y)+j)*31)%100;data[k]=data[k+1]=data[k+2]=v;data[k+3]=255;}return {width,height,data};}};
const points=Array.from({length:478},()=>({x:.5,y:.5,z:0}));
for(const [id,x,y] of [[10,.5,.2],[152,.5,.8],[168,.5,.35],[1,.5,.5],[4,.5,.52],[2,.5,.56],[234,.2,.5],[454,.8,.5],[127,.23,.42],[356,.77,.42],[93,.26,.55],[323,.74,.55],[33,.3,.4],[133,.43,.4],[160,.33,.38],[158,.4,.38],[153,.4,.42],[144,.33,.42],[362,.57,.4],[263,.7,.4],[385,.60,.38],[387,.67,.38],[373,.67,.42],[380,.60,.42],[70,.34,.34],[300,.66,.34]])points[id]={x,y,z:0};

for(const side of ['RIGHT','LEFT']){
 const p=structuredClone(points),ids=side==='RIGHT'?[33,160,158,133,153,144]:[362,385,387,263,373,380],x=side==='RIGHT'?.3:.57;
 p[ids[0]]={x,y:.4,z:0};p[ids[3]]={x:x+18/640,y:.4,z:0};
 for(const i of [1,2,4,5])p[ids[i]]={x:x+(i%2?.005:.02),y:.4+(i<3?-.005625:.005625),z:0};
 const frame=(p,t,closed=false)=>({landmarks:[p],hands:[],blinkRight:side==='RIGHT'&&closed?.9:.02,blinkLeft:side==='LEFT'&&closed?.9:.02,inferenceMs:1,frameTime:t});
 const tracker=new T.VisionTracker();let e;
 for(let t=100;t<=1300;t+=200)e=tracker.assess(ctx,w,h,frame(p,t),t,null);
 assert(e.conditions.positionValid);assert.equal(e.conditions[side==='RIGHT'?'right':'left'].state,'open');
 const shut=structuredClone(p);for(const i of [1,2,4,5])shut[ids[i]].y=.4;
 for(let t=1400;t<=2200;t+=200)e=tracker.assess(ctx,w,h,frame(shut,t,true),t,side==='RIGHT'?'LEFT':'RIGHT');
 assert.equal(e.conditions[side==='RIGHT'?'right':'left'].state,'closed');
 assert.equal(e.conditions[side==='RIGHT'?'left':'right'].state,'open');
 assert.equal(V.letterConditionFailure(e.conditions,side==='RIGHT'?'LEFT':'RIGHT',2200),null);
 assert(V.letterConditionFailure(e.conditions,side,2200));
}
""")


def test_hand_and_object_pixels_are_automatic_and_side_specific():
    node(r"""
const w=640,h=480,ctx={canvas:{width:w,height:h},blank:false,getImageData(x,y,width,height){width=Math.ceil(width);height=Math.ceil(height);const data=new Uint8ClampedArray(width*height*4);for(let j=0;j<height;j++)for(let i=0;i<width;i++){const k=(j*width+i)*4,v=this.blank?0:90+((Math.floor(x)+i)*17+(Math.floor(y)+j)*31)%100;data[k]=data[k+1]=data[k+2]=v;data[k+3]=255;}return {width,height,data};}};
const points=Array.from({length:478},()=>({x:.5,y:.5,z:0}));
for(const [id,x,y] of [[10,.5,.2],[152,.5,.8],[168,.5,.35],[1,.5,.5],[4,.5,.52],[2,.5,.56],[234,.2,.5],[454,.8,.5],[127,.23,.42],[356,.77,.42],[93,.26,.55],[323,.74,.55],[33,.3,.4],[133,.43,.4],[160,.33,.38],[158,.4,.38],[153,.4,.42],[144,.33,.42],[362,.57,.4],[263,.7,.4],[385,.60,.38],[387,.67,.38],[373,.67,.42],[380,.60,.42],[70,.34,.34],[300,.66,.34]])points[id]={x,y,z:0};

const basePixels=ctx.getImageData.bind(ctx);ctx.cover=null;
ctx.getImageData=function(x,y,width,height){const image=basePixels(x,y,width,height);if(this.cover){for(let j=0;j<image.height;j++)for(let i=0;i<image.width;i++)if(x+i>=this.cover.x&&x+i<=this.cover.x+this.cover.width&&y+j>=this.cover.y&&y+j<=this.cover.y+this.cover.height){const k=(j*image.width+i)*4;image.data[k]=image.data[k+1]=image.data[k+2]=250;}}return image;};
for(const side of ['RIGHT','LEFT'])for(const kind of ['hand','object']){
 ctx.cover=null;const tracker=new T.VisionTracker();let e;
 const frame=(t,hands=[])=>({landmarks:[points],hands,blinkRight:.02,blinkLeft:.02,inferenceMs:1,frameTime:t});
 for(let t=100;t<=1300;t+=200)e=tracker.assess(ctx,w,h,frame(t),t,null);
 const ids=side==='RIGHT'?[33,160,158,133,153,144]:[362,385,387,263,373,380];ctx.cover=T.visionEyeRegion(points,ids,w,h,.40);
 const box=ctx.cover,hand=Array.from({length:21},()=>({x:box.x/w,y:box.y/h}));
 for(const [id,x,y]of [[0,0,0],[1,.5,0],[5,1,0],[9,1,1],[13,.5,1],[17,0,1]])hand[id]={x:(box.x+x*box.width)/w,y:(box.y+y*box.height)/h};
 for(let t=1400;t<=2200;t+=200)e=tracker.assess(ctx,w,h,frame(t,kind==='hand'?[hand]:[]),t,side==='RIGHT'?'LEFT':'RIGHT');
 const observed=e.conditions[side==='RIGHT'?'right':'left'];assert.equal(observed.state,'covered');assert.equal(observed.occlusionKind,kind);
 assert.equal(e.conditions[side==='RIGHT'?'left':'right'].state,'open');
 assert.equal(V.letterConditionFailure(e.conditions,side==='RIGHT'?'LEFT':'RIGHT',2200),null);
 assert(V.letterConditionFailure(e.conditions,side,2200));
}
""")


def test_slow_fresh_frames_can_establish_and_revoke_eye_conditions():
    node(r"""
const e=new T.SustainedEyeState();assert.equal(e.update('closed',100).state,'uncertain');
assert.equal(e.update('closed',500).state,'uncertain');assert.equal(e.update('closed',900).state,'closed');
assert.equal(e.update('open',950).state,'open');assert.equal(e.update('closed',1000).state,'uncertain');
// Missing more than the camera freshness deadline breaks the hold.
assert.equal(e.update('closed',1800).state,'uncertain');assert.equal(e.update('closed',2200).state,'uncertain');assert.equal(e.update('closed',2600).state,'closed');
const d=new T.HeadDistanceHysteresis();d.update(.2,100);d.update(.2,500);assert.equal(d.update(.2,900),'near');
assert.equal(d.update(.0,1300),'near');assert.equal(d.update(.0,1700),'stable');
""")


def test_slow_fresh_model_frames_can_finish_open_eye_baseline():
    node(r"""
const w=640,h=480,ctx={canvas:{width:w,height:h},blank:false,getImageData(x,y,width,height){width=Math.ceil(width);height=Math.ceil(height);const data=new Uint8ClampedArray(width*height*4);for(let j=0;j<height;j++)for(let i=0;i<width;i++){const k=(j*width+i)*4,v=this.blank?0:90+((Math.floor(x)+i)*17+(Math.floor(y)+j)*31)%100;data[k]=data[k+1]=data[k+2]=v;data[k+3]=255;}return {width,height,data};}};
const points=Array.from({length:478},()=>({x:.5,y:.5,z:0}));
for(const [id,x,y] of [[10,.5,.2],[152,.5,.8],[168,.5,.35],[1,.5,.5],[4,.5,.52],[2,.5,.56],[234,.2,.5],[454,.8,.5],[127,.23,.42],[356,.77,.42],[93,.26,.55],[323,.74,.55],[33,.3,.4],[133,.43,.4],[160,.33,.38],[158,.4,.38],[153,.4,.42],[144,.33,.42],[362,.57,.4],[263,.7,.4],[385,.60,.38],[387,.67,.38],[373,.67,.42],[380,.60,.42],[70,.34,.34],[300,.66,.34]])points[id]={x,y,z:0};

const tracker=new T.VisionTracker();let e;
for(let t=100;t<=2500;t+=400)e=tracker.assess(ctx,w,h,{landmarks:[points],hands:[],blinkRight:.02,blinkLeft:.02,inferenceMs:1,frameTime:t},t,null);
assert.equal(e.conditions.distanceState,'stable');assert(e.conditions.positionValid);
assert.equal(e.conditions.right.state,'open');assert.equal(e.conditions.left.state,'open');
""")
