"""Focused normal-camera contract: unchanged area unit, methods and history identity."""
import copy,json,subprocess,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'services/core-api'))
import acne_v5_product as V

def test_same_area_unit_uses_unique_boxes_and_fixed_support(monkeypatch):
    support=np.ones((20,20),bool);context=dict(scale=1.,origin=(0,0),gray=np.zeros((20,20)),acne_envelopes={'forehead':support},acne_skin=support,face_support=support,exclusion=np.zeros((20,20),np.uint8),hair=np.zeros((20,20),bool),acne_clipping=np.zeros((20,20),bool))
    boxes=[dict(x=0,y=0,width=10,height=10,candidateId='a'),dict(x=5,y=0,width=10,height=10,candidateId='b')]
    row=dict(id='acne',value=None,region='forehead',unit='appearance-score-0-100',components={},evaluatedArea={'sourcePixels':400,'analysisPixels':400},captureConditions={},uncertainty=[])
    other=dict(id='tone',value=17,region='forehead',quality='valid',normalizationVersion='fixed',components={},evaluatedArea={})
    result=dict(photoId='photo',sourceWidth=20,sourceHeight=20,measurements={'forehead':[row,other]},general=dict(skinType={'value':None},measurements=[dict(row,region='overview')]),maps={},contours={})
    from skin_measurement_contract import attach_result_receipts
    attach_result_receipts(result)
    runtime=dict(photoId='photo',sourceWidth=20,sourceHeight=20,model=dict(onnxSHA256=V.GRAPH_HASH,verifierSHA256=V.V5_HASH),acneCandidates={'forehead':boxes},timing=dict(modelLoadMs=0,inferenceMs=0),resources={},tileCount=1,detectorForwardCount=1)
    monkeypatch.setattr(V,'analyze',lambda *a,**kw:(runtime,context));before=V.non_acne_fingerprint(result);out=V.replace_acne(result,{'qualityValid':True})
    assert out['measurements']['forehead'][0]['value']==37.5
    assert out['general']['measurements'][0]['value']==37.5
    assert out['acneRuntime']['candidateCount']==2 and out['measurements']['forehead'][0]['evaluatedArea']['sourcePixels']==400
    assert V.non_acne_fingerprint(out)==before and out['measurements']['forehead'][1]==other
    assert out['maps']=={} and out['acneRuntime']['nonAcnePreservation']['equal']

def test_current_identity_and_old_history_never_become_equivalent():
    script=r"""
require('./tests/unit/ts_loader.js');
const assert=require('assert/strict'),fs=require('fs'),S=require('./apps/vehicle-app/src/utils/skinIndicators.ts'),C=require('./apps/vehicle-app/src/utils/acneV5Contract.ts');
const e=JSON.parse(fs.readFileSync('tests/fixtures/acne-v5-camera-response.json','utf8'));const original=JSON.stringify(e),row=e.indicator;
assert(S.supportedAppearanceMethod('acne',row.method));assert(!S.supportedAppearanceMethod('dry',row.method));assert(S.validMeasurement(row,'rightCheek'));
assert(S.canCompareIndicator(row,structuredClone(row)));
const old=structuredClone(row);old.method='appearance-cv-6';old.appearance.methodVersion='appearance-cv-6';old.measurement.methodVersion='appearance-cv-6';old.measurement.modelHash=null;old.appearance.modelHash=null;
assert(!S.canCompareIndicator(row,old));
assert.equal(JSON.stringify(e),original);
// The saved v1 fixture remains readable, but cannot masquerade as a new response.
assert.throws(()=>C.validateAcneV5Response(e.response));
const current=structuredClone(e.response);current.acneRuntime.methodVersion=C.ACNE_V5_METHOD;
for(const r of Object.values(current.measurements).flat()){r.methodVersion=C.ACNE_V5_METHOD;r.components.samplingSupportVersion=C.ACNE_V5_SAMPLING;}
C.validateAcneV5Response(current);
const newRow=structuredClone(row);newRow.method=C.ACNE_V5_METHOD;newRow.appearance.methodVersion=C.ACNE_V5_METHOD;newRow.measurement.methodVersion=C.ACNE_V5_METHOD;newRow.appearance.components.samplingSupportVersion=C.ACNE_V5_SAMPLING;
assert(!S.canCompareIndicator(newRow,row));assert(S.validMeasurement(newRow,'rightCheek'));
const bad=structuredClone(current);bad.acneRuntime.onnxSHA256='0'.repeat(64);assert.throws(()=>C.validateAcneV5Response(bad));
const t=structuredClone(current);t.acneRuntime.threshold=.1;assert.throws(()=>C.validateAcneV5Response(t));
"""
    p=subprocess.run(['node','-e',script],cwd=ROOT,text=True,capture_output=True,encoding='utf8');assert p.returncode==0,p.stdout+p.stderr


def test_wrong_model_identity_cannot_leave_a_partially_assigned_score(monkeypatch):
    from skin_measurement_contract import attach_result_receipts
    row=dict(id='acne',value=None,region='forehead',unit='appearance-score-0-100',components={},evaluatedArea={'sourcePixels':400},quality='insufficient',limitationCode='MODEL_NOT_ACCEPTED',normalizationVersion=V.NORMALIZATION)
    other=dict(id='tone',value=17,region='forehead',quality='valid',normalizationVersion='fixed',components={},evaluatedArea={})
    result=attach_result_receipts(dict(photoId='photo',sourceWidth=20,sourceHeight=20,measurements={'forehead':[row,other]},maps={},contours={}))
    wrong=dict(photoId='photo',sourceWidth=20,sourceHeight=20,model=dict(onnxSHA256='0'*64,verifierSHA256=V.V5_HASH))
    monkeypatch.setattr(V,'analyze',lambda *args,**kw:(wrong,{'mustNotBeUsed':True}))
    out=V.replace_acne(result,{'qualityValid':True})
    assert out['acneRuntime']['status']=='unavailable' and out['acneRuntime']['reason']=='ACNE_V5_SOURCE_OR_MODEL_MISMATCH'
    assert out['acneRuntime']['modelHash'] is None and out['measurements']['forehead'][0]['value'] is None
    assert out['measurements']['forehead'][1]['value']==17 and out['acneRuntime']['nonAcnePreservation']['equal']
