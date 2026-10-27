// Client BITE gate must agree with dental_analysis.incisal_contact on the same
// synthetic geometry as tests/unit/test_dental_bite_contact.py, and partial
// backend results must stay visible per view instead of failing the whole scan.
const assert=require('node:assert/strict');
require(process.cwd()+'/tests/unit/ts_loader');
const {incisalContact,DENTAL_BITE_CONTACT}=require(process.cwd()+'/apps/vehicle-app/src/utils/dentalCapture.ts');
const R=require(process.cwd()+'/apps/vehicle-app/src/utils/dentalResult.ts');

function mouthCase(kind){
 const H=240,W=400,[top,bottom]={bite:[90,150],'wide-bite':[60,180],open:[70,170],'upper-only':[70,170]}[kind],mid=(top+bottom)/2,left=100,right=300,cx=200;
 const p=Array.from({length:468},()=>({x:0,y:0}));p[78]={x:left,y:mid};p[308]={x:right,y:mid};p[13]={x:cx,y:top};p[14]={x:cx,y:bottom};
 const valid=new Uint8Array(W*H),tooth=new Uint8Array(W*H),a=(right-left)/2,b=(bottom-top)/2;
 for(let y=0;y<H;y++)for(let x=0;x<W;x++)if(((x-cx)/a)**2+((y-mid)/b)**2<=1)valid[y*W+x]=1;
 const fill=(y0,y1,x0,x1,step=1,value=1)=>{for(let y=y0;y<y1;y++)for(let x=x0;x<x1;x+=step)if(valid[y*W+x])tooth[y*W+x]=value;};
 if(kind==='bite'||kind==='wide-bite'){fill(Math.trunc(mid)-22,Math.trunc(mid)+20,130,270);fill(Math.trunc(mid)-1,Math.trunc(mid)+1,130,270,14,0);}
 else if(kind==='open'){fill(top+4,Math.trunc(mid)-14,130,270);fill(Math.trunc(mid)+14,bottom-4,130,270);}
 else fill(top+4,Math.trunc(mid)-8,130,270);
 return {valid,tooth,W,H,p,width:right-left};
}
for(const [kind,expected] of [['bite',true],['wide-bite',true],['open',false],['upper-only',false]]){
 const c=mouthCase(kind),r=incisalContact(c.valid,c.tooth,c.W,c.H,0,0,c.p,c.width);
 assert.equal(r.confirmed,expected,kind+' '+JSON.stringify(r));
}
assert.equal(DENTAL_BITE_CONTACT.version,'incisal-contact-v1');

// Partial results: shapes as returned by analyze_dental for a quality failure.
const hash=c=>c.repeat(64);
const measured=pose=>({photoId:hash(pose[0].toLowerCase().replace(/[^a-f]/,'a')),pose,sourceWidth:1920,sourceHeight:1080,quality:{valid:true,reasons:[],roi:{x:800,y:600,width:200,height:60}},
 caries:{quality:'valid',unit:'candidate-count',value:1,candidates:[{bounds:{x:850,y:610,width:20,height:20},classCode:'D',confidence:.8}],decisionThreshold:.35,modelHash:hash('e'),candidatePolicyVersion:R.DENTAL_ADULT_POLICY},
 accumulation:{quality:'valid',value:12,evaluatedArea:500,candidates:[]},alignment:{quality:'insufficient',value:null,contours:[],rows:null}});
const insufficient=pose=>({...measured(pose),quality:{valid:false,reasons:['BLURRY'],roi:{x:800,y:600,width:200,height:60}},
 caries:{quality:'insufficient',unit:'candidate-count',value:null,candidates:[],candidatePolicyVersion:R.DENTAL_ADULT_POLICY},
 accumulation:{quality:'insufficient',value:null,candidates:[]},alignment:{quality:'insufficient',value:null,contours:[],rows:null}});
const views=[measured('FRONT'),{...measured('RIGHT'),photoId:hash('b')},{...measured('LEFT'),photoId:hash('c')},{...insufficient('BITE'),photoId:hash('d')}];
const sources=views.map(v=>({photoId:v.photoId,pose:v.pose,width:1920,height:1080}));
// Previously the single unmeasured BITE view rejected the whole scan.
assert.doesNotThrow(()=>R.validateDentalResult({views,missingViews:[]},sources,true));
assert.equal(views.filter(R.dentalViewMeasured).length,3);
assert.equal(R.dentalRecordMeasurements({views,candidatePolicyVersion:R.DENTAL_ADULT_POLICY}).length,4);
// Never synthesize a value or keep marks for an unmeasured view.
for(const bad of [v=>{v.caries.value=0;},v=>{v.caries.candidates=[{}];},v=>{v.accumulation.value=0;},v=>{v.quality.reasons=[];},v=>{v.alignment.contours=[{points:[[1,1]],centroid:[1,1]}];}]){
 const copy=structuredClone(views);bad(copy[3]);assert.throws(()=>R.validateDentalResult({views:copy},sources,true));
}
// Skipped BITE: three views and an explicit missing view, consistent with the views.
assert.doesNotThrow(()=>R.validateDentalResult({views:views.slice(0,3),missingViews:['BITE']},sources.slice(0,3),true));
assert.throws(()=>R.validateDentalResult({views,missingViews:['BITE']},sources,true));
// Crop ROI must lie inside the source photo.
const outside=structuredClone(views);outside[0].quality.roi={x:1900,y:0,width:100,height:10};
assert.throws(()=>R.validateDentalResult({views:outside},sources,true));
console.log('dental_bite_contact_parity: PASS');
