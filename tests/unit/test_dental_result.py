import subprocess,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def test_response_identity_geometry_count_and_probability(tmp_path):
 code=r'''
const fs=require('fs'),assert=require('assert/strict'),load=require('./tests/unit/ts_source_loader.cjs')(JSON.parse(fs.readFileSync(0,'utf8')).dir),{validateDentalView,validateDentalResult}=load('dentalResult');
const source={photoId:'a'.repeat(64),pose:'FRONT',width:100,height:80};
const base={...source,sourceWidth:100,sourceHeight:80,quality:{valid:true},caries:{quality:'valid',unit:'candidate-count',value:1,decisionThreshold:.35,modelHash:'b'.repeat(64),candidates:[{classCode:'d',confidence:.8,bounds:{x:90,y:70,width:10,height:10}}]},accumulation:{value:null,candidates:[]},alignment:{value:null,contours:[],rows:null}};
assert.strictEqual(validateDentalView(base,source),base);assert.strictEqual(validateDentalResult({views:[base]},[source]).views[0],base);
for(const mutate of [v=>v.photoId='c'.repeat(64),v=>v.pose='RIGHT',v=>v.sourceWidth=99,v=>v.caries.value=2,v=>v.caries.candidates[0].confidence=Infinity,v=>v.caries.candidates[0].confidence=1.1,v=>v.caries.candidates[0].bounds.x=NaN,v=>v.caries.candidates[0].bounds.width=0,v=>v.caries.candidates[0].bounds.width=11,v=>v.caries.candidates[0].classCode='other',v=>v.alignment.contours=[{points:[[3,Infinity]],centroid:[1,1]}]]){const v=structuredClone(base);mutate(v);assert.throws(()=>validateDentalView(v,source));}
assert.throws(()=>validateDentalResult({views:[]},[source]));
'''
 r=subprocess.run(['node','-e',code],cwd=ROOT,input=json.dumps({'dir':str(tmp_path)}),text=True,capture_output=True)
 assert r.returncode==0,r.stdout+r.stderr

def test_dental_history_partitions_geometry_model_threshold_and_units_without_rewrite():
 code=r'''
require('./tests/unit/ts_loader.js');
const assert=require('assert/strict'),{buildHistorySeries}=require('./apps/vehicle-app/src/utils/healthHistorySeries.ts');
const base={id:'base',timestamp:'2026-10-17T08:00:00Z',sourceType:'upload',methodVersion:'dental-visible-upload-v3',measurements:[{pose:'FRONT',caries:{quality:'valid',value:2,unit:'candidate-count',methodVersion:'upload-local-v2',modelVersion:'model-v1',modelHash:'a'.repeat(64),decisionThreshold:.35},accumulation:{value:null,quality:'insufficient',unit:'percent-visible-border-area',methodVersion:'border-v2'}}]};
const rows=[base];
for(const [id,change] of [['model',r=>r.measurements[0].caries.modelHash='b'.repeat(64)],['threshold',r=>r.measurements[0].caries.decisionThreshold=.4],['method',r=>r.measurements[0].caries.methodVersion='other-geometry'],['unit',r=>r.measurements[0].caries.unit='percent'],['source',r=>r.sourceType='camera']]){const r=structuredClone(base);r.id=id;change(r);rows.push(r)}
const before=JSON.stringify(rows),series=buildHistorySeries('dental',rows),caries=series.filter(s=>s.criterion==='caries');assert.equal(caries.length,6);for(const s of caries)assert.equal(s.points.filter(p=>p.value!==null).length,1);assert(series.filter(s=>s.criterion==='accumulation').every(s=>s.points.every(p=>p.value===null)));assert.equal(JSON.stringify(rows),before);
'''
 r=subprocess.run(['node','-e',code],cwd=ROOT,text=True,capture_output=True)
 assert r.returncode==0,r.stdout+r.stderr
