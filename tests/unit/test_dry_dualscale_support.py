"""Tiny exact source-cell controls; no model/photo/replay campaign."""
import sys
from pathlib import Path
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'services/core-api'))
from dry_dualscale_support import merge_accepted_supports,project_sampled_cells

def test_half_cells_native_preservation_and_unique_original_area():
 native=np.zeros((4,5),np.float32);native[3,4]=.8
 half=np.array([[.5,0],[0,.7]],np.float32);visible=np.ones((4,5),bool)
 r=merge_accepted_supports(native,half,source_shape=(4,5),native_origin=(0,0),half_origin=(0,0),visible_source=visible)
 assert np.array_equal(r.combined[:2,:2],np.full((2,2),.5,np.float32))
 assert r.combined[3,4]==native[3,4] and not r.combined[:3,4].any()
 assert r.metadata['nativeLostSourcePixels']==0 and r.metadata['combinedAcceptedSourcePixels']==9
 # Odd source edge has no half-cell owner: never clamp/replicate the last cell.
 assert not project_sampled_cells(np.ones((2,2)),(4,5),(0,0),.5,visible)[:,4].any()

def test_origin_mask_exclusion_and_max_not_sum():
 visible=np.ones((5,6),bool);visible[1,2]=False
 native=np.array([[.6]],np.float32);half=np.array([[.4]],np.float32)
 r=merge_accepted_supports(native,half,source_shape=(5,6),native_origin=(1,1),half_origin=(1,1),visible_source=visible)
 assert r.combined[1,1]==native[0,0] and r.combined[1,2]==0
 assert (r.combined>.04).sum()==3 and r.metadata['visibleSourcePixels']==29
 assert r.combined.max()==native.max()

def test_clip_and_invalid_contract_fail_closed():
 visible=np.ones((2,2),bool)
 assert project_sampled_cells(np.ones((2,2)),(2,2),(-1,-1),1.,visible).sum()==1
 for factor in [.25,2.]:
  with pytest.raises(ValueError):project_sampled_cells(np.ones((1,1)),(2,2),(0,0),factor,visible)
 with pytest.raises(ValueError):project_sampled_cells(np.ones((1,1)),(2,2),(.5,0),.5,visible)
 with pytest.raises(ValueError):project_sampled_cells(np.ones((1,1)),(2,2),(0,0),.5,np.ones((2,2),np.uint8))
