"""Current controller safety, not camera/voice detection or physical acceptance."""
import subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def node(script):
    prefix="require('./tests/unit/ts_loader.js');const assert=require('assert/strict'),V=require('./apps/vehicle-app/src/utils/spokenVision.ts'),T=require('./apps/vehicle-app/src/utils/visionTracking.ts');"
    p=subprocess.run(['node','-e',prefix+script],cwd=ROOT,text=True,capture_output=True,encoding='utf8')
    assert p.returncode==0,p.stdout+p.stderr

def test_nonfinite_conditions_cannot_admit_a_valid_trial():
    node("""
const open={state:'open'},covered={state:'covered'},c={observedAt:1000,cameraLive:true,modelActive:true,faceCount:1,qualityValid:true,positionValid:true,relativeScaleChange:0,distancePolicy:'head-anchors-hysteresis-v1',distanceState:'stable',right:open,left:covered};
assert.equal(V.letterConditionFailure({...c,observedAt:NaN},'RIGHT',1100),'camera');
assert.equal(V.letterConditionFailure({...c,observedAt:Infinity},'RIGHT',1100),'camera');
assert.equal(V.letterConditionFailure({...c,relativeScaleChange:NaN},'RIGHT',1100),'position');
assert.equal(V.letterConditionFailure({...c,relativeScaleChange:Infinity},'RIGHT',1100),'position');
assert.equal(V.letterConditionFailure(c,'RIGHT',NaN),'camera');
""")

def test_nonfinite_distance_cannot_be_committed_as_stable():
    node("""
const d=new T.HeadDistanceHysteresis();assert.equal(d.update(NaN,1000),'unknown');assert.equal(d.update(Infinity,1100),'unknown');assert.equal(d.update(0,1200),'stable');
""")

def test_nonfinite_rendered_geometry_is_unscored():
    node("""
const s=new V.SpokenLetterSession();s.present(1000);const c={observedAt:1000,cameraLive:true,modelActive:true,faceCount:1,qualityValid:true,positionValid:true,relativeScaleChange:0,right:{state:'open'},left:{state:'covered'}};
const geometry={viewportWidthCssPx:NaN,viewportHeightCssPx:120,pathWidthCssPx:80,pathHeightCssPx:90,strokeWidthCssPx:10,measuredAt:1099,method:'dom-svg-css-pixels'};
assert.equal(s.respond({letter:s.letter,rotation:s.transform.rotation,mirrored:s.transform.mirrored},c,1100,s.presentationId,geometry),false);assert.equal(s.trials.length,0);
""")
