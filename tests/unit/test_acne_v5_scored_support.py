"""Regression: points, box-area score and history use exactly the same scoped list."""
import sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'services/core-api'))
from acne_v5_product import scored_candidates
from acne_box_support import box_area

def box(x,y,w=2,h=2,**kw):
    return dict(x=x,y=y,width=w,height=h,candidateId=f'{x}:{y}',region='leftCheek',coordinateSpace='source-pixels',**kw)

def select(boxes,support,scale=1,origin=(0,0)):
    return scored_candidates(boxes,support,scale,origin,(100,100),'leftCheek','photo')

def test_outside_and_partial_boundary_candidates_are_not_moved_or_scored():
    support=np.zeros((20,20),bool);support[5:15,5:15]=True
    outside=box(0,0);partial=box(3,7,w=3);inside=box(5,5)
    kept,receipt=select([outside,partial,inside],support)
    assert [b['candidateId'] for b in kept]==[inside['candidateId']]
    assert kept[0]['x']==inside['x'] and kept[0]['y']==inside['y']
    assert receipt['inputCount']==3 and receipt['acceptedCount']==1 and receipt['rejectedCount']==2
    assert receipt['rejected'][0]['scoredPixels']==0 and receipt['rejected'][1]['scoredPixels']>0
    assert all(r['reason']=='CENTER_OUTSIDE_SCORED_SUPPORT' for r in receipt['rejected'])
    assert int((box_area(kept,support.shape,1,(0,0))&support).sum())==4
    assert receipt['denominatorAnalysisPixels']==100

def test_native_origin_scale_and_no_edge_clamping():
    support=np.ones((10,10),bool)
    valid=box(20,30,w=4,h=4);outside=box(18,30,w=1,h=1)
    kept,receipt=select([valid,outside],support,.5,(20,30))
    assert kept[0]['x']==20 and kept[0]['scoreSupportPixels']==4
    assert receipt['rejected'][0]['analysisCenter'][0]==-1
    assert receipt['rejected'][0]['reason']=='OUTSIDE_ANALYSIS'
    assert receipt['sourceOrigin']==[20,30] and receipt['analysisScale']==.5

def test_side_region_identity_not_reassigned():
    support=np.ones((10,10),bool);wrong=box(2,2);wrong['region']='rightCheek'
    kept,receipt=select([wrong],support)
    assert kept==[] and receipt['rejected'][0]['reason']=='REGION_ID_MISMATCH'
    assert wrong['region']=='rightCheek'

def test_tiny_positive_is_not_erased_or_given_a_floor():
    support=np.ones((100,100),bool)
    kept,receipt=select([box(10,10,w=1,h=1)],support)
    raw=(box_area(kept,support.shape,1,(0,0))&support).sum()/support.sum()*100
    assert len(kept)==1 and raw==.01 and round(float(raw))==0
    assert receipt['denominatorAnalysisPixels']==10000
