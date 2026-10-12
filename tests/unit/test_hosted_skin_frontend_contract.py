"""Actual client modules: consent, source generation and hosted record identity."""
from pathlib import Path
import json,subprocess
ROOT=Path(__file__).resolve().parents[2]

def test_permission_capture_and_revocation_aborts_real_client_module():
 script=r'''
require('./tests/unit/ts_loader.js');const assert=require('assert/strict');
global.window={};const data=new Map();global.localStorage={getItem:k=>data.get(k)||null};
const A=require('./apps/vehicle-app/src/utils/appearanceMeasurements.ts'),P=require('./apps/vehicle-app/src/utils/attuneMode.ts');
const snapshot={dataUrl:'local-test-pixels',photoId:'a'.repeat(64),angle:'FRONT',width:640,height:480,meshes:{},exclusions:[],landmarks:[]};
let bodies=[],current=true;
global.fetch=async(url,options)=>{bodies.push(JSON.parse(options.body));return {ok:true,json:async()=>({photoId:snapshot.photoId,sourceWidth:640,sourceHeight:480})};};
(async()=>{
 assert(!P.isSkinHostedProcessingAllowed());await A.analyzeAppearance(snapshot,true,{},[],()=>current);assert.equal(bodies[0].hostedProcessingConsent,false);
 data.set(P.SKIN_HOSTED_PROCESSING_PERMISSION,'true');await A.analyzeAppearance(snapshot,true,{},[],()=>current);assert.equal(bodies[1].hostedProcessingConsent,true);
 let aborted=false;global.fetch=(url,options)=>new Promise((resolve,reject)=>{options.signal.addEventListener('abort',()=>{aborted=true;reject(Error('aborted'));});setTimeout(()=>data.set(P.SKIN_HOSTED_PROCESSING_PERMISSION,'false'),20);});
 await assert.rejects(A.analyzeAppearance(snapshot,true,{},[],()=>current));assert(aborted);
 global.fetch=async()=>({ok:true,json:async()=>{current=false;return {photoId:snapshot.photoId,sourceWidth:640,sourceHeight:480};}});
 await assert.rejects(A.analyzeAppearance(snapshot,true,{},[],()=>current),/STALE_SOURCE/);
})().catch(e=>{console.error(e);process.exitCode=1;});
'''
 r=subprocess.run(['node','-e',script],cwd=ROOT,text=True,capture_output=True);assert r.returncode==0,r.stdout+r.stderr

def test_hosted_identity_four_labels_and_unknown_weights_are_valid_records():
 script=r'''
require('./tests/unit/ts_loader.js');const assert=require('assert/strict'),V=require('./apps/vehicle-app/src/utils/skinOverview.ts');
const value={schemaVersion:1,analysisId:'one',captureId:'a'.repeat(64),pose:'FRONT',normalizationVersion:'fixed',sourceTransform:{coordinateSpace:'source-pixels',sourceWidth:640,sourceHeight:640},indicators:['tone','oil','redness','acne','sag','dry','lines','dark','bags'].map(id=>({id,score:null,measurement:{scope:'whole-face',region:'overview',methodVersion:'preserved',quality:'insufficient',unavailableReason:'NO_SUPPORT'}}))};
for(const [id,label] of Object.entries({normal:'Normal',dry:'Kuru',oily:'Yağlı',combination:'Karma'})){
 value.skinType={value:id,quality:'valid',confidence:.9,methodVersion:'hosted-roboflow-skin-type-axavj/1',modelHash:null,provider:'roboflow',providerModelId:'skin-type-axavj/1',inferenceKind:'hosted'};assert(V.validSkinOverview(value,'one'));assert.equal(V.SKIN_TYPE_LABELS[id],label);
 value.skinType.providerModelId='unverified/1';assert(!V.validSkinOverview(value,'one'));
}
value.skinType={value:'normal',quality:'insufficient',confidence:null,methodVersion:'hosted-roboflow-skin-type-axavj/1',modelHash:null};assert(!V.validSkinOverview(value,'one'));
'''
 r=subprocess.run(['node','-e',script],cwd=ROOT,text=True,capture_output=True);assert r.returncode==0,r.stdout+r.stderr
