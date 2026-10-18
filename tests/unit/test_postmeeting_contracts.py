from pathlib import Path
import json,subprocess

def test_source_motion_preview_jitter_and_regional_color_contracts(tmp_path):
 root=Path(__file__).resolve().parents[2]
 script=r'''
const fs=require('fs'),ts=require('typescript'),assert=require('assert');
const dir=JSON.parse(fs.readFileSync(0,'utf8')).dir;
const load=require('./tests/unit/ts_source_loader.cjs')(dir);
const {StablePreviewCrop,SourceMotion}=load('cameraStability');
const smooth=new StablePreviewCrop(),start={x:.2,y:.15,width:.5,height:.7};smooth.update(start,0);
for(let t=16;t<1000;t+=16)assert.deepEqual(smooth.update({...start,x:start.x+.003*Math.sin(t),width:start.width+.004*Math.cos(t)},t),start);
assert.equal(smooth.update({...start,x:.35},1001).x,.35);
const motion=new SourceMotion();for(let t=0;t<=600;t+=100)assert.equal(motion.update(.5+.0005*Math.sin(t),.5,.4,t),false);
assert(motion.update(.7,.5,.4,700));
const {measureSkinIndicators,indicatorIds,validSkinIndicators}=load('skinIndicators');assert.equal(indicatorIds('nose').length,5);assert.equal(indicatorIds('periorbital').length,4);
const w=40,h=40,pixels=new Uint8ClampedArray(w*h*4);for(let i=0;i<pixels.length;i+=4){pixels[i]=160;pixels[i+1]=120;pixels[i+2]=100;pixels[i+3]=255;}
const mesh={points:[{x:1,y:1},{x:38,y:1},{x:1,y:38}],edges:[[0,1],[1,2],[2,0]],major:[],boundary:[],excluded:[]};
const snapshot={width:w,height:h,meshes:{forehead:mesh}};
const ctx={getImageData:()=>({data:pixels})},quality={isValid:true};
const rows=measureSkinIndicators(ctx,snapshot,quality).forehead;
assert.equal(rows.find(i=>i.id==='tone').score,0);assert.equal(rows.find(i=>i.id==='redness').score,39.2);
for(const id of ['dry','sag','acne','oil'])assert.equal(rows.find(i=>i.id===id).score,null);
assert(measureSkinIndicators(ctx,snapshot,{isValid:false}).forehead.every(i=>i.score===null));
const full={};for(const region of ['forehead','rightCheek','leftCheek','nose','chin','periorbital'])full[region]=indicatorIds(region).map(id=>({id,score:null,method:'unavailable',reason:'No validated measurement'}));assert(validSkinIndicators(full));full.forehead[0].score=NaN;assert(!validSkinIndicators(full));full.forehead[0].score=null;full.forehead[1].score=0;assert(!validSkinIndicators(full));
'''
 subprocess.run(['node','-e',"require('./tests/unit/ts_loader.js');\n"+script],cwd=root,input=json.dumps({'dir':str(tmp_path).replace('\\','/')}),text=True,check=True)

def test_snapshot_source_and_no_segmentation_preload():
 root=Path(__file__).resolve().parents[2]
 page=(root/'apps/vehicle-app/src/app/skin/page.tsx').read_text('utf8')
 assert '.segmentHead(' not in page
 inference=(root/'apps/vehicle-app/src/utils/skinInference.ts').read_text('utf8')
 initialize=inference.split('async initialize()')[1].split('private prepareSegmentation')[0]
 assert 'this.prepareSegmentation()' not in initialize
 snapshot=(root/'apps/vehicle-app/src/utils/skinSnapshot.ts').read_text('utf8')
 assert 'snapshotRawSkinFrame as snapshotSkinFrame' in page
 raw=snapshot.split('export function snapshotRawSkinFrame')[1].split('export function snapshotAngleForRegion')[0]
 assert "dataUrl:canvas.toDataURL('image/png'),crop:{x:0,y:0,width:canvas.width,height:canvas.height}" in raw
 assert 'headAlpha(' not in raw and 'segmentHead(' not in raw

def test_v3_reference_deletion_preserves_legacy_and_journal_recovers(tmp_path):
 root=Path(__file__).resolve().parents[2]
 script=r'''
const fs=require('fs'),ts=require('typescript'),assert=require('assert');const {dir}=JSON.parse(fs.readFileSync(0,'utf8'));
for(const n of ['attuneMode','healthRecords'])fs.writeFileSync(dir+'/'+n+'.js',ts.transpileModule(fs.readFileSync('apps/vehicle-app/src/utils/'+n+'.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText);
const map=new Map();global.localStorage={getItem:k=>map.get(k)??null,setItem:(k,v)=>map.set(k,String(v)),removeItem:k=>map.delete(k)};global.window={dispatchEvent:()=>{},location:{search:''}};Object.defineProperty(global,'navigator',{value:{locks:{request:async(n,f)=>f()}}});global.crypto=require('crypto').webcrypto;
const H=require(dir+'/healthRecords.js'),K=require(dir+'/attuneMode.js').STORAGE_KEYS;
(async()=>{map.set(K.SKIN_BASELINE,'legacy-metrics-unchanged');map.set(K.SKIN_SINGLE_SIGNS_BASELINE,JSON.stringify({id:'v3'}));map.set(K.SKIN_HISTORY,JSON.stringify([{id:'v3',schemaVersion:3,isBaseline:true,comparisonScope:'single-front-v1'},{id:'comparison',schemaVersion:3,baselineId:'v3',indicators:{forehead:[{id:'tone',score:2,referenceDelta:1}]}}]));await H.deleteHealthRecord('skin','v3');assert.equal(map.get(K.SKIN_BASELINE),'legacy-metrics-unchanged');assert(!map.has(K.SKIN_SINGLE_SIGNS_BASELINE));const remaining=H.readHealthRecords('skin')[0];assert.equal(remaining.indicators.forehead[0].score,2);assert(!('referenceDelta' in remaining.indicators.forehead[0]));assert(remaining.comparisonUnavailable);map.set(H.RECORD_JOURNAL,JSON.stringify({[K.SKIN_SINGLE_SIGNS_BASELINE]:'restored-v3-reference'}));await H.prepareHealthRecords('skin');assert.equal(map.get(K.SKIN_SINGLE_SIGNS_BASELINE),'restored-v3-reference');assert(!map.has(H.RECORD_JOURNAL));})().catch(e=>{console.error(e);process.exitCode=1});
'''
 subprocess.run(['node','-e',"require('./tests/unit/ts_loader.js');require('./tests/unit/skin_photo_numeric_stub.cjs');\n"+script],cwd=root,input=json.dumps({'dir':str(tmp_path)}),text=True,check=True)
