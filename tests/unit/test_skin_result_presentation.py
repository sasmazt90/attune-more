"""Display-only framing and rounding. Not physical or clinical acceptance."""
import json, subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

def test_face_framing_and_score_rounding():
 script=r'''
const fs=require('fs'),ts=require('typescript'),assert=require('assert/strict'),Module=require('module');
const React=require('react'),{renderToStaticMarkup}=require('react-dom/server');
function load(path,stubs={}) {
 const m=new Module(path,module);m.paths=module.paths;
 m.require=(id)=>id in stubs?stubs[id]:require(id);
 m._compile(ts.transpileModule(fs.readFileSync(path,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.React,target:ts.ScriptTarget.ES2022,esModuleInterop:true}}).outputText,path);
 return m.exports;
}
const {cameraCrop}=load('apps/vehicle-app/src/utils/cameraStability.ts');
const points=Array.from({length:478},(_,i)=>({x:i<468?.4+(i%2)*.2:1,y:i<468?.3+(i%3)*.15:1}));
const before=JSON.stringify(points),crop=cameraCrop(points);
assert.equal(JSON.stringify(points),before);
assert(Math.abs(crop.x-.336)<1e-10);assert(Math.abs(crop.y-.195)<1e-10);
assert(Math.abs(crop.width-.328)<1e-10);assert(Math.abs(crop.height-.453)<1e-10);
assert.deepEqual(cameraCrop(points.slice(0,10)),{x:0,y:0,width:1,height:1});
const edge=cameraCrop(points.map(p=>({x:p.x-.39,y:p.y-.29})));
assert.equal(edge.x,0);assert.equal(edge.y,0);assert(edge.x+edge.width<=1&&edge.y+edge.height<=1);
const {SkinRegionSummary}=load('apps/vehicle-app/src/components/skin/SkinRegionSummary.tsx',{'../InformationButton':{InformationButton:()=>null}});
for(const [value,expected] of [[.4,0],[.5,1],[32.4,32],[32.5,33],[99.5,100]]) {
 const indicators=[{id:'redness',label:'Redness',score:value,reason:'Color index',unit:'Renk indeksi / 100',appearance:{unit:'relative-color-index-0-100',type:'appearance_proxy'}},{id:'oil',label:'Oil',score:12.5,reason:'Supported area',unit:'%',appearance:{unit:'percent-visible-area',type:'appearance_proxy'}}];
 const html=renderToStaticMarkup(React.createElement(SkinRegionSummary,{currentRegion:{nameTr:'Region',metrics:{},indicators},onOpenModal:()=>{},onNavigateToCare:()=>{}}));
 const scores=[...html.matchAll(/data-skin-score="[^"]*"[^>]*>([^<]+)<\/span>/g)].map(match=>match[1]);
 assert(scores.includes(String(expected)));assert(!scores.includes(expected+'%'));
 assert(scores.includes('13%'));assert(html.includes('aria-valuenow="12.5"'));
 assert(!html.includes('aria-valuenow="'+value+'"'));
 assert.equal((html.match(/role="meter"/g)||[]).length,1);
 assert.equal(indicators[0].score,value);
}
'''
 result=subprocess.run(['node','-e',"require('./tests/unit/ts_loader.js');\n"+script],cwd=ROOT,capture_output=True,text=True,encoding='utf8')
 assert result.returncode==0,result.stdout+result.stderr
