import json
from pathlib import Path
import subprocess


def test_production_face_quality_region_notes_and_reminder_contracts(tmp_path):
    root=Path(__file__).resolve().parents[2]
    script=r"""
require('./tests/unit/ts_loader.js');
const fs=require('fs'),ts=require('typescript'),assert=require('assert');
const dir=JSON.parse(fs.readFileSync(0,'utf8')).dir;
function load(name){const source='apps/vehicle-app/src/'+name+'.ts',target=dir+'/'+name.split('/').pop()+'.cjs';fs.writeFileSync(target,ts.transpileModule(fs.readFileSync(source,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText);return require(target);}
// Move temp compiled files into the test directory only; import external MediaPipe from the project.
const Module=require('module'); const original=Module._resolveFilename;
Module._resolveFilename=function(request,parent,...rest){if(request==='@mediapipe/tasks-vision')return original.call(this,request,{paths:module.paths},...rest);return original.call(this,request,parent,...rest);};
const analyzer=load('utils/skinAnalyzer'),A=analyzer.SkinAnalyzer;
const width=80,height=80,raw=new Uint8ClampedArray(width*height*4);
const face={x:20,y:20,width:40,height:40};
function ctx(faceLevel,detail){for(let y=0;y<height;y++)for(let x=0;x<width;x++){const inside=x>=20&&x<60&&y>=20&&y<60,v=inside ? faceLevel+(detail?(x%4<2?10:-10):0) : (x%4<2?250:180),i=(y*width+x)*4;raw[i]=raw[i+1]=raw[i+2]=v;raw[i+3]=255;}return {getImageData:(x,y,w,h)=>{const data=new Uint8ClampedArray(w*h*4);for(let j=0;j<h;j++)for(let i=0;i<w;i++)for(let k=0;k<4;k++)data[(j*w+i)*4+k]=raw[((j+y)*width+i+x)*4+k];return {data,width:w,height:h};}};}
assert.equal(A.checkQuality(ctx(20,true),width,height,true,face).status,'TOO_DARK');
assert.equal(A.checkQuality(ctx(120,false),width,height,true,face).status,'BLURRY');
assert.equal(A.checkQuality(ctx(240,false),width,height,true,face).status,'TOO_BRIGHT');
assert.equal(A.checkQuality(ctx(120,true),width,height,true,face).status,'OPTIMAL');
assert.equal(A.checkQuality(ctx(120,true),width,height,false,face).status,'NO_FACE');
assert.equal(A.checkQuality(ctx(120,true),width,height,true,{...face,x:NaN}).status,'NO_FACE');
const invalidLandmarks=Array.from({length:478},()=>({x:2,y:2,z:0}));
assert.throws(()=>A.analyzeRegions(ctx(120,true),width,height,{isMediaPipeActive:true,landmarks:invalidLandmarks,box:face}),/INVALID_ROI/);
const quality=A.checkQuality(ctx(120,true),width,height,true,face);
const pose={yaw:0,pitch:0,roll:0,scaleRatio:.5};
const metadata={id:'reference',timestamp:new Date().toISOString(),schemaVersion:1,scope:'single-front-v1',quality,pose};
assert(analyzer.canCompareSkinReference(metadata,quality,pose));
assert(!analyzer.canCompareSkinReference(null,quality,pose));
assert(!analyzer.canCompareSkinReference({...metadata,pose:undefined},quality,pose));
assert(!analyzer.canCompareSkinReference(metadata,{...quality,avgLuminance:quality.avgLuminance+16},pose));
assert(!analyzer.canCompareSkinReference(metadata,quality,{...pose,yaw:.13}));
assert(!analyzer.canCompareSkinReference(metadata,quality,{...pose,scaleRatio:.59}));
assert(!analyzer.canCompareSkinReference(metadata,quality,{...pose,pitch:NaN}));
const build=load('data/skinDemoFixture').buildSkinRegionViewModel;
const result={isBaseline:true,clinicalNoteTr:'Sol Yanak generic',regions:{periorbital:{rednessScore:50,luminanceScore:50,textureVariance:80}}};
const region=build('periorbital',result,false);
assert(!JSON.stringify(region.observation).includes('Sol Yanak'));assert(!region.badgeText.includes('%'));assert(!region.metrics.texture.displayValue.includes('Artış'));
result.isBaseline=false;result.regions.periorbital.changeFromBaselinePct=-12;
assert(build('periorbital',result,false).observation.details.includes('-12%'));
"""
    subprocess.run(['node','-e',script],cwd=root,check=True,input=json.dumps({'dir':str(tmp_path).replace('\\','/')}),text=True,encoding='utf-8')
