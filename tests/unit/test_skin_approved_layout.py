"""Verify result-screen vs scan-screen layout and overlay contracts."""
import subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def test_existing_layout_styles_and_visible_content_are_preserved():
 script=r'''
const fs=require('fs'),ts=require('typescript'),Module=require('module'),assert=require('assert/strict'),React=require('react'),{renderToStaticMarkup}=require('react-dom/server');
function load(path,source,stubs={}){const m=new Module(path,module);m.paths=module.paths;m.require=id=>id in stubs?stubs[id]:require(id);m._compile(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.React,esModuleInterop:true}}).outputText,path);return m.exports;}
const prefix='apps/vehicle-app/src/',surface=load('surface',fs.readFileSync(prefix+'utils/skinSurfaceAnalysis.ts','utf8'));
const region={id:'forehead',nameTr:'Alin',metrics:{},indicators:[{id:'redness',label:'Bölgesel kızarıklık farkı',score:25.4,reason:'Pixel index'},{id:'oil',label:'Oil',score:null,reason:'No independently accepted measurement'},{id:'sag',label:'Sarkma',score:null,reason:'Not applicable to forehead'}]};
const snapshot={width:640,height:480,angle:'FRONT',crop:{x:200,y:100,width:200,height:300},dataUrl:'data:image/png;base64,unchanged',meshes:{forehead:{points:[{x:250,y:150},{x:300,y:150},{x:280,y:200}],edges:[[0,1],[1,2],[0,2]],major:[0],boundary:[],excluded:[]}},exclusions:[],photoId:'photo',localAnalysis:{loadMs:1,analysisMs:2,allocatedBytes:3}};
const stubs={'../InformationButton':{InformationButton:()=>null},'next/image':{default:()=>null},'./SkinRegionNavigator':{SkinRegionNavigator:()=>React.createElement('nav',null,'Existing navigation')},'../CameraPreparation':{cameraCrop:()=>({})},'../../utils/cameraStability':{StablePreviewCrop:class{}},'../../utils/skinSurfaceAnalysis':surface};
const Summary=load(prefix+'components/skin/SkinRegionSummary.tsx',fs.readFileSync(prefix+'components/skin/SkinRegionSummary.tsx','utf8'),stubs).SkinRegionSummary;
const FacePanel=load(prefix+'components/skin/SkinFacePanel.tsx',fs.readFileSync(prefix+'components/skin/SkinFacePanel.tsx','utf8'),stubs).SkinFacePanel;

// 1. Forehead summary filters out inapplicable 'sag' indicator and keeps applicable ones:
const sumHtml=renderToStaticMarkup(React.createElement(Summary,{currentRegion:region,onOpenModal:()=>{},onNavigateToCare:()=>{},onSelectCriterion:()=>{},selectedCriterion:null}));
assert.equal((sumHtml.match(/data-skin-indicator=/g)||[]).length,2);
assert(!sumHtml.includes('data-skin-indicator="sag"'));
assert(sumHtml.includes('grid grid-cols-1 sm:grid-cols-2 gap-3'));

// 2. Result mode never renders cyan wireframe mesh (data-skin-mesh), while scan mode does:
const resultHtml=renderToStaticMarkup(React.createElement(FacePanel,{currentRegion:region,snapshot,mode:'result',onPrev:()=>{},onNext:()=>{},selectedCriterion:null}));
assert(!resultHtml.includes('data-skin-mesh'));
const scanHtml=renderToStaticMarkup(React.createElement(FacePanel,{currentRegion:region,snapshot,mode:'scan',onPrev:()=>{},onNext:()=>{},selectedCriterion:null}));
assert(scanHtml.includes('data-skin-mesh="forehead"'));

// 3. Regional skin-type overlay uses decisionTrace.regions[regionId].state, leaving 'normal' colorless:
const regionWithTrace={...region,id:'overview',skinType:{value:'dry',quality:'valid',decisionTrace:{regions:{forehead:{state:'normal'}}}}};
const traceNormalHtml=renderToStaticMarkup(React.createElement(FacePanel,{currentRegion:regionWithTrace,snapshot,mode:'result',onPrev:()=>{},onNext:()=>{},selectedCriterion:null}));
assert(!traceNormalHtml.includes('data-skin-type-region="forehead"'));

const regionWithOilyTrace={...region,id:'overview',skinType:{value:'combination',quality:'valid',decisionTrace:{regions:{forehead:{state:'oily'}}}}};
const traceOilyHtml=renderToStaticMarkup(React.createElement(FacePanel,{currentRegion:regionWithOilyTrace,snapshot,mode:'result',onPrev:()=>{},onNext:()=>{},selectedCriterion:null}));
assert(traceOilyHtml.includes('data-skin-type-region="forehead"'));
assert(traceOilyHtml.includes('fill="#22c55e"'));
'''
 r=subprocess.run(['node','-e',"require('./tests/unit/ts_loader.js');\n"+script],cwd=ROOT,text=True,capture_output=True,encoding='utf8');assert r.returncode==0,r.stdout+r.stderr
