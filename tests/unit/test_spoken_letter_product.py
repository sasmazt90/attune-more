"""Production TS and exact-provider safety contracts; no simulated STT claim."""
import json,subprocess,sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'services/core-api'))
import main
from fastapi.testclient import TestClient

def run(tmp_path,script):
 bootstrap=r"""
const fs=require('fs'),ts=require('typescript'),assert=require('assert/strict');
const dir=JSON.parse(fs.readFileSync(0,'utf8')).dir;
const Module=require('module'),original=Module._resolveFilename;
Module._resolveFilename=function(request,parent,...rest){if(request==='@mediapipe/tasks-vision')return original.call(this,request,{paths:module.paths},...rest);return original.call(this,request,parent,...rest)};
const load=require('./tests/unit/ts_source_loader.cjs')(dir);
const V=load('spokenVision');
// Explicit unit geometry input, not a claim of browser measurement.
const originalRespond=V.SpokenLetterSession.prototype.respond;
V.SpokenLetterSession.prototype.respond=function(a,c,n,id,g){return originalRespond.call(this,a,c,n,id,g||{viewportWidthCssPx:this.sizePx,viewportHeightCssPx:this.sizePx,pathWidthCssPx:this.sizePx*.8,pathHeightCssPx:this.sizePx*.8,strokeWidthCssPx:this.sizePx*.1,measuredAt:n-1,method:'dom-svg-css-pixels'})};
const open={state:'open',ear:.3,darkFraction:.1,contrast:20,method:'lid-geometry-and-current-pixels'},closed={...open,state:'closed',ear:.1};
const c={observedAt:1000,cameraLive:true,modelActive:true,faceCount:1,qualityValid:true,positionValid:true,relativeScaleChange:0,right:open,left:closed};
"""+script
 result=subprocess.run(['node','-e',bootstrap],cwd=ROOT,input=json.dumps({'dir':str(tmp_path).replace('\\','/')}),capture_output=True,text=True,encoding='utf-8')
 assert result.returncode==0,result.stdout+result.stderr

@pytest.mark.parametrize('text,expected',[
 ('ters E',{'letter':'E','clarify':'reverse'}),('düz P',{'letter':'P','rotation':0}),
 ('sağa yatmış A',{'letter':'A','rotation':90}),('sola yatmış B',{'letter':'B','rotation':270}),
 ('Rize baş aşağı',{'letter':'R','rotation':180}),('Edirne aynalı',{'letter':'E','mirrored':True}),
 ('göremiyorum',{'command':'not-visible'}),('tekrar',{'command':'repeat'}),('duraklat',{'command':'pause'}),('devam et',{'command':'resume'}),('bitir',{'command':'finish'}),
 ('düz E veya F',{'rotation':0,'ambiguous':'letter','clarify':'letter'}),('E',{'letter':'E','clarify':'orientation'})])
def test_target_independent_turkish_parser(tmp_path,text,expected):
 run(tmp_path,'assert.deepEqual(JSON.parse(JSON.stringify(V.parseLetterAnswer('+json.dumps(text)+'))),'+json.dumps(expected)+');')

def test_symmetry_real_errors_and_not_visible_adaptation(tmp_path):
 run(tmp_path,"""
assert(V.equivalentOrientation('A','upright','mirror'));assert(!V.equivalentOrientation('A','left','right'));assert(!V.equivalentOrientation('E','upright','mirror'));
const s=new V.SpokenLetterSession();s.present();let size=s.sizePx;const answer=()=>({letter:s.letter,rotation:s.transform.rotation,mirrored:s.transform.mirrored});
assert(s.respond(answer(),c,1100,s.presentationId));assert.equal(s.sizePx,size);s.present();assert(s.respond(answer(),c,1100,s.presentationId));assert(s.sizePx<size);
size=s.sizePx;s.present();assert(s.respond({letter:s.letter==='E'?'P':'E',orientation:s.orientation},c,1100,s.presentationId));assert.equal(s.sizePx,size);
size=s.sizePx;s.present();assert(s.respond({command:'not-visible'},c,1100,s.presentationId));assert(s.sizePx>size);assert(!s.trials.at(-1).correct&&s.trials.at(-1).notVisible);
for(let i=s.trials.length;i<24;i++){s.present();const cc={...c,...(s.eye==='LEFT'?{right:closed,left:open}:{})};assert(s.respond(answer(),cc,1100,s.presentationId));assert(!s.respond(answer(),cc,1100,s.presentationId));}
assert(s.completed);assert.equal(s.trials.filter(t=>t.eye==='RIGHT').length,12);assert.equal(s.trials.filter(t=>t.eye==='LEFT').length,12);assert(!('logMAR' in s));
""")

@pytest.mark.parametrize('change',[{'observedAt':0},{'cameraLive':False},{'modelActive':False},{'faceCount':2},{'qualityValid':False},{'positionValid':False},{'relativeScaleChange':.081},{'relativeScaleChange':None},{'left':{'state':'open'}},{'right':{'state':'closed'}},{'left':{'state':'uncertain'}}])
def test_conditions_block_scoring_and_preserve_presentation(tmp_path,change):
 run(tmp_path,"const s=new V.SpokenLetterSession();s.present();const id=s.presentationId,size=s.sizePx;const cc={...c,..."+json.dumps(change)+"};assert(V.letterConditionFailure(cc,'RIGHT',1100));assert(!s.respond({letter:s.letter,orientation:s.orientation},cc,1100,id));assert(!s.respond({command:'not-visible'},cc,1100,id));assert.equal(s.trials.length,0);assert.equal(s.presentationId,id);assert.equal(s.sizePx,size);")

def test_clarification_does_not_advance_or_guess_target(tmp_path):
 run(tmp_path,"const s=new V.SpokenLetterSession();s.present();const id=s.presentationId;assert(!s.respond(V.parseLetterAnswer('ters E'),c,1100,id));assert.equal(s.presentationId,id);assert.equal(s.trials.length,0);")

def test_unavailable_exact_mental_voice_never_exports_text(monkeypatch):
 import vision_speech,time
 monkeypatch.setattr(vision_speech,'_catalogue',(time.monotonic(),frozenset(['some-other-voice'])))
 monkeypatch.setitem(main.vehicle_state,'vehicleMoving',False)
 monkeypatch.setattr(main,'get_openai_client',lambda *args:pytest.fail('TTS must not call OpenAI'))
 response=TestClient(main.app).post('/api/mental/speech',json={'text':'Sentetik metin','cloudConsent':True})
 assert response.status_code==503 and 'tr-TR-EmelNeural' in response.json()['detail']

def test_fixed_vision_route_consent_origin_and_targets(monkeypatch):
 monkeypatch.setitem(main.vehicle_state,'vehicleMoving',False);client=TestClient(main.app)
 assert client.post('/api/vision/speech',json={'text':'right'}).status_code==403
 assert client.post('/api/vision/speech',json={'text':'E sağa','cloudConsent':True}).status_code==422
 assert client.post('/api/vision/speech',headers={'Origin':'https://untrusted.invalid'},json={'text':'right','cloudConsent':True}).status_code==403
 monkeypatch.setitem(main.vehicle_state,'vehicleMoving',True)
 assert client.post('/api/vision/speech',json={'text':'right','cloudConsent':True}).status_code==409

def test_all_six_local_contours_crop_and_numeric_pipeline(tmp_path):
 run(tmp_path,"""
load('skinAnalyzer');load('skinMultiAngle');load('skinMesh');const S=load('skinSnapshot');
assert.equal(Object.keys(S.SKIN_CONTOURS).length,6);for(const indices of Object.values(S.SKIN_CONTOURS)){assert(indices.length>=10);assert(indices.every(i=>i>=0&&i<468));}
const A=require(dir+'/skinAnalyzer.js').SkinAnalyzer;const originalGeometry=A.regionGeometry;A.regionGeometry=()=>({roiDefinitions:[{id:'forehead',nameTr:'Alın',x:20,y:30,w:100,h:60}],exclusionBoxes:[]});
const landmarks=Array.from({length:478},(_,i)=>({x:.25+(i%20)/40,y:.2+Math.floor(i/20)/50,z:0}));let captures=0;
const snapshot=S.snapshotSkinFrame({width:640,height:480,toDataURL:()=>{captures++;return 'data:image/png;base64,fixture'}},{landmarks,isMediaPipeActive:true},'FRONT');
// Without semantic segmentation no oval/raw-photo fallback is permitted.
assert.equal(captures,0);assert(snapshot.visualError);assert.equal(snapshot.dataUrl,'');assert.equal(snapshot.rois[0].x,20);assert.equal(snapshot.rois[0].w,100);assert.equal(snapshot.contours.forehead[0].x,landmarks[109].x*640);assert.equal(snapshot.faceContour.length,S.FACE_OUTLINE.length);A.regionGeometry=originalGeometry;
""")


def test_component_metrics_log_steps_and_recomputation(tmp_path):
 run(tmp_path,"""
const s=new V.SpokenLetterSession();s.present(1000);s.beginResponse(1000);s.letter='P';s.orientation='right';s.transform=V.legacyTransform('right');const size=s.sizePx;
assert(s.respond({letter:'P',orientation:'left'},c,1100,s.presentationId));assert.equal(s.sizePx,size);assert.deepEqual(V.scoreLetterTrial(s.trials[0]),{letterCorrect:true,orientationCorrect:false,combinedCorrect:false});
s.present(1100);s.letter='P';s.orientation='right';s.transform=V.legacyTransform('right');assert(s.respond({letter:'P',orientation:'down'},c,1150,s.presentationId));assert.equal(s.sizePx,Math.min(V.LETTER_RULES.maxPx,size/V.LETTER_RULES.shrinkRatio));
s.present(1200);s.letter='P';s.orientation='right';s.transform=V.legacyTransform('right');assert(s.respond({letter:'F',orientation:'right'},c,1300,s.presentationId));assert.deepEqual(V.scoreLetterTrial(s.trials[2]),{letterCorrect:false,orientationCorrect:true,combinedCorrect:false});
s.present(1300);assert(s.respond({command:'not-visible'},c,1400,s.presentationId));
const rows=V.performanceBySize(s.ledger,'RIGHT');assert.equal(rows.reduce((n,r)=>n+r.letter.total,0),4);assert.equal(rows.reduce((n,r)=>n+r.orientation.correct,0),1);assert.equal(rows.reduce((n,r)=>n+r.combined.correct,0),0);
s.trials[0].letterCorrect=false;s.trials[0].correct=true;assert.equal(V.performanceForEye(s.ledger,'RIGHT').letter.correct,2);
assert.equal(V.performanceBySize([], 'LEFT').length,0);assert(!('threshold' in s));assert(!('acuity' in s));assert.equal(s.trials[0].responseTimeMs,100);
assert(s.trials.every(t=>t.protocolVersion===V.LETTER_PROTOCOL&&t.id&&t.presentationId&&t.distanceEvidence.absoluteDistanceCm===null));
""")

def test_invalid_resubmits_same_trial_drops_old_presentation(tmp_path):
 run(tmp_path,"""
const s=new V.SpokenLetterSession();s.present(1000);const letter=s.letter,rotation=s.orientation,id=s.trialId,presentation=s.presentationId,size=s.sizePx;
assert(s.invalidate('position',{...c,positionValid:false},1150,null));assert(!s.invalidate('position',c,1160,null));
s.present(1200);assert.equal(s.letter,letter);assert.equal(s.orientation,rotation);assert.equal(s.trialId,id);assert.notEqual(s.presentationId,presentation);assert.equal(s.sizePx,size);
assert(!s.respond({letter,orientation:rotation},c,1300,presentation));assert(s.respond({letter,orientation:rotation},c,1300,s.presentationId));assert.equal(s.invalidTrials.length,1);assert.equal(s.trials.length,1);
assert.equal(s.ledger[0].letterCorrect,null);assert.equal(V.performanceBySize(s.ledger,'RIGHT')[0].letter.total,1);assert.equal(s.ledger[0].invalidReason,'position');
""")

def test_actual_geometry_required_and_unknown_asr_not_error(tmp_path):
 run(tmp_path,"""
const s=new V.SpokenLetterSession();s.present(1000);const id=s.presentationId;const a=V.parseLetterAnswer('anlaşılmayan kelimeler');assert(a.clarify);
assert(!s.respond(a,c,1100,id));s.unscored('ASR_UNCLEAR',c,1100,null);assert.equal(s.trials.length,0);assert.equal(s.presentationId,id);
assert(!originalRespond.call(s,{letter:s.letter,orientation:s.orientation},c,1100,id,null));
assert(!originalRespond.call(s,{letter:s.letter,orientation:s.orientation},c,1100,id,{viewportWidthCssPx:0,viewportHeightCssPx:1,pathWidthCssPx:1,pathHeightCssPx:1,measuredAt:1100}));
assert.equal(V.performanceBySize(s.ledger,'RIGHT').length,0);assert(s.respond({letter:s.letter,orientation:s.orientation},c,1100,id));assert.equal(V.performanceBySize(s.ledger,'RIGHT')[0].letter.total,1);assert(!('threshold' in s.trials[0]));
""")

def test_eye_pixels_are_required_and_anatomical(tmp_path):
 run(tmp_path,"""
const E=load('visionEyePixels');const landmarks=Array.from({length:478},()=>({x:.5,y:.5}));
function points(indices,center,ear){const p=[[center-30,50],[center-10,50-ear*30],[center+10,50-ear*30],[center+30,50],[center+10,50+ear*30],[center-10,50+ear*30]];indices.forEach((i,n)=>landmarks[i]={x:p[n][0]/200,y:p[n][1]/100});}
points([33,160,158,133,153,144],60,.3);points([362,385,387,263,373,380],140,.1);
const alignment={landmarks,isMediaPipeActive:true,faceCount:1};let calls=0;
const ctx={getImageData(x,y,w,h){calls++;const data=new Uint8ClampedArray(w*h*4);for(let i=0;i<w*h;i++){const shade=x<100&&i%10===0?20:i%2===0?120:160;data.set([shade,shade,shade,255],i*4);}return {data};}};
let eyes=E.assessEyePixels(ctx,200,100,alignment);assert.equal(eyes.right.state,'open');assert.equal(eyes.left.state,'closed');assert.equal(calls,2);
const dark={getImageData(x,y,w,h){return {data:new Uint8ClampedArray(w*h*4)}}};eyes=E.assessEyePixels(dark,200,100,alignment);assert.equal(eyes.right.state,'uncertain');assert.equal(eyes.left.state,'uncertain');
eyes=E.assessEyePixels(ctx,200,100,{...alignment,isMediaPipeActive:false});assert.equal(eyes.right.state,'uncertain');
""")
