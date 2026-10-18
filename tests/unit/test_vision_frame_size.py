"""Focused bounds, recorded geometry and preserved display crop contracts."""
import json, subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
def test_step50_min15_and_frame_crop(tmp_path):
    script=r"""
const fs=require('fs'),assert=require('assert/strict'),load=require('./tests/unit/ts_source_loader.cjs')(JSON.parse(fs.readFileSync(0,'utf8')).dir),V=load('spokenVision'),C=load('cameraStability');
assert.equal(V.LETTER_RULES.shrinkRatio,.5);assert.equal(V.LETTER_RULES.startPx,120);assert.equal(V.LETTER_RULES.minPx,15);assert.equal(V.LETTER_RULES.maxPx,180);assert(V.LETTER_METHOD.includes('step50-min15-v4'));
const close=(a,b)=>assert(Math.abs(a-b)<1e-9);const s=new V.SpokenLetterSession(),open={state:'open'},closed={state:'closed'};
const cond=()=>({observedAt:1000,cameraLive:true,modelActive:true,faceCount:1,qualityValid:true,positionValid:true,relativeScaleChange:0,distancePolicy:'head-anchors-hysteresis-v1',distanceState:'stable',right:s.eye==='RIGHT'?open:closed,left:s.eye==='RIGHT'?closed:open});
const geom=()=>({viewportWidthCssPx:s.sizePx,viewportHeightCssPx:s.sizePx,pathWidthCssPx:s.sizePx*.6,pathHeightCssPx:s.sizePx*.7,strokeWidthCssPx:s.sizePx/11.6,measuredAt:1099,method:'dom-svg-css-pixels'});
const reply=correct=>{s.present(1000);const before=s.sizePx,g=geom();assert(s.respond({letter:correct?s.letter:s.letter==='F'?'P':'F',rotation:s.transform.rotation,mirrored:s.transform.mirrored},cond(),1100,s.presentationId,g));assert.equal(s.trials.at(-1).sizePx,before);assert.deepEqual(s.trials.at(-1).renderedGeometry,g);return s.sizePx;};
close(reply(true),120);s.present(1000);const id=s.presentationId;s.unscored('technical',cond(),1100,geom());assert(!s.respond({letter:s.letter},cond(),1100,id,geom()));s.invalidate('paused',cond(),1100,geom());s.present(1000);assert.equal(s.sizePx,120);close(reply(true),60);
close(reply(false),60);close(reply(false),120);close(reply(true),120);close(reply(false),120);close(reply(true),120);close(reply(true),60);
const nearMax=new V.SpokenLetterSession();nearMax.sizePx=175;for(let i=0;i<2;i++){nearMax.present(1000);assert(nearMax.respond({command:'not-visible'},cond(),1100,nearMax.presentationId,{...geom(),viewportWidthCssPx:175}));}assert.equal(nearMax.sizePx,180);
const nearMin=new V.SpokenLetterSession();nearMin.sizePx=20;for(let i=0;i<2;i++){nearMin.present(1000);assert(nearMin.respond({letter:nearMin.letter,rotation:nearMin.transform.rotation,mirrored:nearMin.transform.mirrored},cond(),1100,nearMin.presentationId,{...geom(),viewportWidthCssPx:20}));}assert.equal(nearMin.sizePx,15);
const points=Array.from({length:478},()=>({x:.5,y:.5}));points[234]={x:.3,y:.5};points[454]={x:.7,y:.5};points[10]={x:.5,y:.2};points[1]={x:.5,y:.5};
const old=C.visionCameraCrop(points,4/3),wide=C.visionCameraCrop(points,4/3,5/3);assert.equal(wide.height,old.height);assert(Math.abs(wide.width/wide.height*(4/3)-5/3)<1e-10);assert(wide.width>old.width);
for(const i of [17,152,172,397])points[i].y=.95;assert.deepEqual(C.visionCameraCrop(points,4/3,5/3),wide);
const full=C.visionCameraCrop(undefined,4/3,5/3);close(full.height,1);assert(full.width>1&&full.x<0);close(full.width/full.height*(4/3),5/3);
"""
    result=subprocess.run(['node','-e',script],input=json.dumps({'dir':str(tmp_path)}),text=True,capture_output=True,cwd=ROOT)
    assert result.returncode==0,result.stdout+result.stderr
