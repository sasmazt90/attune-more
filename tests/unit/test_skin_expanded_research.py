"""Adapter/data-isolation/math regressions, never fabricated clinical truth."""
import json,subprocess,importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def test_unreviewed_or_foreign_source_artifact_cannot_enter_user_result(tmp_path):
 script=r'''
require('./tests/unit/ts_loader.js');
const fs=require('fs'),ts=require('typescript'),a=require('assert/strict'),dir=JSON.parse(fs.readFileSync(0,'utf8')).dir;
for(const n of ['skinResearchAdapter','skinIndicators','skinSurfaceAnalysis'])fs.writeFileSync(dir+'/'+n+'.js',ts.transpileModule(fs.readFileSync('apps/vehicle-app/src/utils/'+n+'.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText);
const A=require(dir+'/skinResearchAdapter.js'),I=require(dir+'/skinIndicators.js');
const ctx={photoId:'source',pose:'FRONT',region:'chin',width:640,height:480};
const base={id:'dry',label:'Cilt kuruluğu',score:null,reason:'missing',method:'unavailable',unit:'',sampleCount:0};
const artifact={target:'visible-flaking-grade',methodVersion:'grade-v1',modelHash:'a'.repeat(64),datasetHash:'b'.repeat(64),evidenceHash:'c'.repeat(64),region:'chin',rawValue:2,confidence:.9,unit:'ordinal-grade',gradeMaximum:3,photoId:'source',pose:'FRONT',sourceWidth:640,sourceHeight:480,quality:'valid',rights:{code:true,weights:true,data:true},independentCases:1000,validation:'independently-validated'};
let row=A.adaptResearchResult(artifact,ctx,base);a.equal(row.score,null);a.equal(row.measurement.rawValue,null);a.equal(row.measurement.unavailableReason,'no-reviewed-independent-skin-acceptance');a(I.validMeasurement(row,'chin'));
row=A.adaptResearchResult({...artifact,photoId:'foreign'},ctx,base);a.equal(row.measurement.unavailableReason,'source-coordinate-mismatch');
row=A.adaptResearchResult({...artifact,rawValue:NaN},ctx,base);a.equal(row.measurement.unavailableReason,'invalid-target-value');
row=A.adaptResearchResult({...artifact,unit:'class-probability'},ctx,base);a.equal(row.measurement.unavailableReason,'target-unit-mismatch');
row=A.adaptResearchResult({...artifact,rights:{code:true,weights:true,data:false}},ctx,base);a.equal(row.measurement.unavailableReason,'unresolved-usage-rights');
a(!I.canCompareIndicator(row,{...row,measurement:{...row.measurement,datasetHash:'d'.repeat(64)}}));
const S=require(dir+'/skinSurfaceAnalysis.js'),width=80,height=80,pixels=new Uint8ClampedArray(width*height*4);
for(let i=0;i<pixels.length;i+=4)pixels.set([150,120,100,255],i);
for(let y=40;y<44;y++)for(let x=40;x<44;x++)pixels.set([210,200,190,255],(y*width+x)*4);
const mesh={points:[{x:0,y:0},{x:79,y:0},{x:79,y:79},{x:0,y:79}],edges:[[0,1],[1,2],[2,3],[3,0],[0,2]]};
const input={width,height,pixels,mesh,region:'forehead',exclusions:[{x:0,y:0,w:10,h:10}],qualityValid:true};const before=Buffer.from(pixels);const g=S.analyzeRelativeShine(input);
a(g.shineSamples>0);a.equal(g.shineAreaPercent,100*g.shineSamples/g.validSamples);a.deepEqual(before,Buffer.from(pixels));a.equal(g.shine[5*g.width+5],0);
a.equal(S.analyzeRelativeShine({...input,region:'periorbital'}).shineAreaPercent,null);
const gain=pixels.map((v,i)=>i%4===3?v:Math.floor(v*.8));const h=S.analyzeRelativeShine({...input,pixels:gain});a.equal(g.validSamples,h.validSamples);a.equal(g.shineSamples,h.shineSamples);
'''
 r=subprocess.run(['node','-e',script],cwd=ROOT,input=json.dumps({'dir':str(tmp_path).replace('\\','/')}),text=True,capture_output=True,encoding='utf8');assert r.returncode==0,r.stdout+r.stderr

def test_ordinal_errors_are_case_weighted_not_frame_weighted():
 spec=importlib.util.spec_from_file_location('ordinal_evaluation',ROOT/'scripts/skin-research/ordinal_evaluation.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 result=module.evaluate([0,0,0,3],[0,0,0,0],['a','a','a','b'])
 assert result['MAE']==1.5 and result['bias']==-1.5 and result['exactAgreement']==.5
 assert result['independentCases']==2 and result['images']==4 and 'MAE' in result['caseBootstrap95']
