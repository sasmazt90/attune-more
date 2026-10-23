"""Real comparison/reference lifecycle, with no fabricated clinical values."""
import json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def test_first_valid_region_reference_and_individual_deletion(tmp_path):
 script=r'''
const fs=require('fs'),ts=require('typescript'),a=require('assert/strict'),dir=JSON.parse(fs.readFileSync(0,'utf8')).dir;
for(const n of ['appearanceMeasurements','healthRecords','attuneMode'])fs.writeFileSync(dir+'/'+n+'.js',ts.transpileModule(fs.readFileSync('apps/vehicle-app/src/utils/'+n+'.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText);
const A=require(dir+'/appearanceMeasurements.js'),H=require(dir+'/healthRecords.js'),map=new Map();
a(A.isSagAppearanceOnly({components:{appearanceSemantics:A.SAG_APPEARANCE_SEMANTICS,clinicalSeverity:false,elasticity:false,comparisonMode:'same-person-compatible-capture-only'}}));
a(!A.isSagAppearanceOnly({components:{appearanceSemantics:A.SAG_APPEARANCE_SEMANTICS,clinicalSeverity:false,elasticity:true,comparisonMode:'same-person-compatible-capture-only'}}));
global.localStorage={getItem:k=>map.get(k)??null,setItem:(k,v)=>map.set(k,String(v)),removeItem:k=>map.delete(k)};
global.window={dispatchEvent:()=>{},location:{search:''}};Object.defineProperty(global,'navigator',{value:{locks:{request:async(n,fn)=>fn()}}});global.crypto=require('crypto').webcrypto;
// Explicit isolated consent fixture; never waive the production append guard.
require('./apps/vehicle-app/src/utils/serviceConsent.ts').setServiceConsent('skin',['local']);
const make=(value)=>({id:'sag',score:value,appearance:{type:'longitudinal_measurement',value,quality:value===null?'insufficient':'valid',methodVersion:'appearance-cv-1',unit:'normalized-contour-ratio',referenceId:null,limitationCode:value===null?'DETAIL_MISSING':'REFERENCE_CREATED',components:{features:[value,value]}},measurement:{rawValue:value,quality:value===null?'insufficient':'valid'}});
let base=make(.4),row=make(.6);A.compareAppearance(row,base,true,'baseline');a(Math.abs(row.referenceDelta-.2)<1e-9);a.equal(row.appearance.referenceId,'baseline');
row=make(.6);A.compareAppearance(row,base,false,'baseline');a.equal(row.appearance.limitationCode,'CAPTURE_CONDITIONS_INCOMPATIBLE');a.equal(row.referenceDelta,undefined);
row=make(null);A.compareAppearance(row,base,false,'baseline');a.equal(row.appearance.limitationCode,'DETAIL_MISSING');
const prior={id:'baseline',indicators:{chin:[make(null)],forehead:[base]}};const current={chin:[make(.6)],forehead:[make(.8)]};
a.equal(A.initializeMissingContourReferences(prior,current,[],'later'),null);
const added=A.initializeMissingContourReferences(prior,current,['chin','forehead'],'later');a.equal(prior.indicators.chin[0].score,null);a.equal(added.indicators.chin[0].appearance.referenceId,'later');a.equal(added.indicators.forehead[0].score,.4);a.equal(current.chin[0].appearance.limitationCode,'REFERENCE_CREATED');
row=make(.65);A.compareAppearance(row,added.indicators.chin[0],true,'baseline');a.equal(row.appearance.referenceId,'later');a(Math.abs(row.referenceDelta-.05)<1e-9);
(async()=>{
 const key='attune_skin_appearance_reference_v1';map.set(key,JSON.stringify(added));
 await H.appendHealthRecord('skin',{id:'baseline',schemaVersion:3,indicators:prior.indicators});
 await H.appendHealthRecord('skin',{id:'later',schemaVersion:3,indicators:current});
 await H.appendHealthRecord('skin',{id:'dependent',schemaVersion:3,baselineId:'baseline',indicators:{chin:[row]}});
 await H.deleteHealthRecord('skin','later');
 const remaining=JSON.parse(map.get(key));a.equal(remaining.indicators.chin[0].appearance.value,null);a.equal(remaining.indicators.forehead[0].score,.4);
 const dependent=H.readHealthRecords('skin').find(r=>r.id==='dependent').indicators.chin[0];a.equal(dependent.referenceDelta,undefined);a.equal(dependent.appearance.referenceId,null);a.equal(dependent.appearance.limitationCode,'REFERENCE_DELETED');
})().catch(e=>{console.error(e);process.exitCode=1;});
'''
 r=subprocess.run(['node','-e',"require('./tests/unit/ts_loader.js');require('./tests/unit/skin_photo_numeric_stub.cjs');\n"+script],cwd=ROOT,input=json.dumps({'dir':str(tmp_path).replace('\\','/')}),text=True,capture_output=True,encoding='utf8');assert r.returncode==0,r.stdout+r.stderr
