"""Finite capture/expression engineering controls, not natural accuracy."""
import copy,json,subprocess,sys
from pathlib import Path
import numpy as np,pytest
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'services/core-api'))
import skin_expression as E,instant_appearance as I
def observation():return dict(photoId='a'*64,version=E.VERSION,scores={k:.01 for k in E.REQUIRED})

def test_missing_observation_is_not_neutral_and_static_lips_are_not_smile():
 assert E.reason(None,'a'*64,.01,0,.4)=='EXPRESSION_SUPPORT_UNAVAILABLE'
 assert E.reason(observation(),'a'*64,.01,-.12,.4) is None
@pytest.mark.parametrize('change',[dict(photoId='b'*64),dict(version='old'),dict(scores={})])
def test_stale_or_mismatched_source_rejected(change):
 with pytest.raises(ValueError):E.reason({**observation(),**change},'a'*64,.01,0,.4)
@pytest.mark.parametrize('name,expected',[('jawOpen','OPEN_MOUTH'),('mouthSmileLeft','SMILE'),('mouthFrownRight','FROWN'),('cheekPuff','CHEEK_PUFF'),('mouthPressRight','MOUTH_PRESS'),('mouthPucker','PUCKER')])
def test_existing_expression_thresholds(name,expected):
 obs=observation();obs['scores'][name]=.8
 assert E.reason(obs,'a'*64,.01,0,.3)=='EXPRESSION_'+expected
@pytest.mark.parametrize('pose,yaw,expected',[('FRONT',0,None),('FRONT',.3,'HEAD_ANGLE_UNSUPPORTED'),('RIGHT',-.4,None),('LEFT',.4,None),('RIGHT',.4,'HEAD_ANGLE_UNSUPPORTED'),('LEFT',-.4,'HEAD_ANGLE_UNSUPPORTED')])
def test_existing_three_pose_limits_not_front_only(pose,yaw,expected):
 assert E.pose_reason(pose,dict(yaw=yaw,pitch=0,roll=0))==expected

def test_unsupported_lower_face_stays_null_and_eye_method_unchanged():
 from test_local_appearance_health import landmarks
 p=landmarks();gray=np.full((320,320),.5,np.float32);mask=np.ones(gray.shape,bool)
 for region in ['chin','leftCheek','rightCheek']:
  v,c,field,lines,reason=I.instant_proxy(gray,mask,p,region,dict(yaw=0,pitch=0,roll=0),1,(0,0),gray.shape,photo_id='a'*64,capture_pose='FRONT')
  assert v is None and reason=='EXPRESSION_SUPPORT_UNAVAILABLE' and not field.any() and not lines
  assert c['formulaVersion'].endswith('expression-v3-observed-pose')
 row=dict(id='sag',value=None,quality='insufficient',limitationCode='EXPRESSION_SUPPORT_UNAVAILABLE',methodVersion='appearance-cv-6',normalizationVersion='new',modelHash=None,evaluatedArea={},localMap={'key':'chin:sag'})
 from skin_measurement_contract import attach_result_receipts
 r=attach_result_receipts(dict(measurements={'chin':[row]},maps={'chin:sag':dict(region='chin',criterion='sag')},general={'measurements':[]}))
 assert r['maps']=={} and row['localMap'] is None and r['activeCriterionMethods']['criteria']['sag']['chin']['status']=='unavailable'

def test_frontend_matches_backend_neutral_gate_and_snapshot_copy():
 code=r'''
require('./tests/unit/ts_loader.js');const fs=require('fs'),a=require('assert/strict'),E=require('./apps/vehicle-app/src/utils/skinExpression.ts'),S=require('./apps/vehicle-app/src/utils/skinSnapshot.ts'),A=require('./apps/vehicle-app/src/utils/skinAnalyzer.ts');
const path=require('path').resolve('../attune-live-test/audit-results/material-closeout-20261013/camera-native-payload.json');const payload=JSON.parse(fs.readFileSync(path,'utf8'));
const scores=Object.fromEntries(E.EXPRESSION_FIELDS.map(k=>[k,.01])),p=structuredClone(payload.landmarks);p[13]={x:.5,y:.6};p[14]={x:.5,y:.6001};
const align={landmarks:p,expressionScores:scores,faceCount:1};a.equal(E.lowerFaceExpressionReason(align,1280,960),undefined);
const M=require('./apps/vehicle-app/src/utils/skinMultiAngle.ts');for(const [pose,yaw,ok] of [['FRONT',0,true],['FRONT',.3,false],['RIGHT',-.4,true],['RIGHT',.4,false],['LEFT',.4,true],['LEFT',-.4,false]])a.equal(M.matchesSkinAngle({...align,faceDetected:true,isMediaPipeActive:true,sourceFramed:true,yaw,pitch:0,roll:0,scaleRatio:.5},pose),ok);
for(const [key,expected] of [['jawOpen','OPEN_MOUTH'],['mouthSmileLeft','SMILE'],['mouthFrownRight','FROWN'],['cheekPuff','CHEEK_PUFF'],['mouthPressRight','MOUTH_PRESS']]){a.equal(E.lowerFaceExpressionReason({...align,expressionScores:{...scores,[key]:.8}},1280,960),'EXPRESSION_'+expected)}
a.equal(E.lowerFaceExpressionReason({...align,expressionScores:undefined},1280,960),'EXPRESSION_SUPPORT_UNAVAILABLE');
const canvas={width:1280,height:960,toDataURL:()=> 'original-source-marker'};A.SkinAnalyzer.regionGeometry=()=>({roiDefinitions:[{id:'forehead',x:500,y:100,w:100,h:100}],exclusionBoxes:[]});
const snapshot=S.snapshotRawSkinFrame(canvas,align,'FRONT');scores.mouthSmileLeft=.9;p[13].y=.9;a.equal(snapshot.expressionScores.mouthSmileLeft,.01);a.notEqual(snapshot.landmarks[13].y,.9);a.equal(snapshot.dataUrl,'original-source-marker');
const bound=E.expressionObservation(snapshot.expressionScores,'a'.repeat(64));snapshot.expressionScores.jawOpen=.9;a.equal(bound.scores.jawOpen,.01);a.equal(bound.photoId,'a'.repeat(64));
'''
 p=subprocess.run(['node','-e',code],cwd=ROOT,text=True,capture_output=True)
 assert p.returncode==0,p.stdout+p.stderr

def test_existing_voice_issue_lifecycle_is_rate_limited_and_cooperative():
 p=subprocess.run(['node','tests/unit/skin_guidance_control.cjs'],cwd=ROOT,text=True,capture_output=True)
 assert p.returncode==0,p.stdout+p.stderr
