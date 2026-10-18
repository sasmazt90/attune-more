"""Technical photometric/mask invariants, never clinical accuracy evidence."""
import json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def test_fixed_scale_mask_units_source_immutability_and_contract(tmp_path):
 script=r'''
require('./tests/unit/ts_loader.js');
const fs=require('fs'),ts=require('typescript'),assert=require('assert/strict');const {dir}=JSON.parse(fs.readFileSync(0,'utf8'));
function load(n){const p=dir+'/'+n+'.js';fs.writeFileSync(p,ts.transpileModule(fs.readFileSync('apps/vehicle-app/src/utils/'+n+'.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText);return require(p)}
load('skinResearchAdapter');const S=load('skinSurfaceAnalysis'),I=load('skinIndicators');
const width=80,height=80,pixels=new Uint8ClampedArray(width*height*4);
for(let i=0;i<pixels.length;i+=4)pixels.set([150,120,100,255],i);
const mesh={points:[{x:0,y:0},{x:79,y:0},{x:79,y:79},{x:0,y:79}],edges:[[0,1],[1,2],[2,3],[3,0],[0,2]],major:[],boundary:[],excluded:[]};
const input={width,height,pixels,mesh,region:'forehead',exclusions:[{x:20,y:20,w:10,h:10}],qualityValid:true};
const before=Buffer.from(pixels);let a=S.analyzeSurface(input,true);assert.equal(a.shineAreaPercent,0);assert.deepEqual(Buffer.from(pixels),before);
assert.equal(a.valid[25*a.width+25],0);assert.equal(a.valid[10*a.width+10],255);
assert(Math.abs(a.redness[10*a.width+10]-(300-120-100)/255*100)<1e-5);
for(let y=40;y<44;y++)for(let x=40;x<44;x++)pixels.set([245,235,225,255],(y*80+x)*4);
a=S.analyzeSurface(input,true);assert(a.shineSamples>0);assert.equal(a.shineAreaPercent,100*a.shineSamples/a.validSamples);
assert.equal(S.analyzeSurface({...input,region:'periorbital'},true).shineAreaPercent,null);
assert.equal(S.analyzeSurface({...input,qualityValid:false},true).shineAreaPercent,null);
const bright=new Uint8ClampedArray(pixels.length);for(let i=0;i<bright.length;i+=4)bright.set([255,255,255,255],i);
assert.equal(S.analyzeSurface({...input,pixels:bright},true).shineAreaPercent,null);
assert.deepEqual(S.surfaceColor(50,false),[0,0,0,0]);assert.deepEqual(S.surfaceColor(NaN,true),[0,0,0,0]);assert.deepEqual(S.surfaceColor(0,true),[0,0,0,0]);
assert(S.surfaceColor(90,true)[3]>S.surfaceColor(10,true)[3]);assert(S.surfaceColor(100,true)[3]<=82);assert.deepEqual(S.surfaceColor(50,true),S.surfaceColor(50,true));
const row={id:'redness',score:20,method:'m',unit:'u',measurement:{scope:'regional',region:'nose',methodVersion:'v1',modelHash:null,unit:'color-index-0-100',rawValue:20.123,confidence:null,quality:'valid',validation:'analytic-pixel-index',unavailableReason:null}};
assert(I.validMeasurement(row,'nose'));assert(!I.validMeasurement(row,'chin'));assert(!I.validMeasurement({...row,measurement:{...row.measurement,rawValue:NaN}},'nose'));
assert(!I.validMeasurement({...row,id:'oil',score:null,measurement:{...row.measurement,unit:'visible-highlight-area-percent',validation:'development-only'}},'nose'));
assert(I.canCompareIndicator(row,JSON.parse(JSON.stringify(row))));assert(!I.canCompareIndicator(row,{...row,measurement:{...row.measurement,methodVersion:'v2'}}));
'''
 r=subprocess.run(['node','-e',script],cwd=ROOT,input=json.dumps({'dir':str(tmp_path).replace('\\','/')}),text=True,capture_output=True,encoding='utf8');assert r.returncode==0,r.stdout+r.stderr
