"""Lossless original mask/cell units only; not a photo acceptance test."""
import base64,sys
from pathlib import Path
import cv2,numpy as np,pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'services/core-api'))
from dry_dualscale_runtime_staging import _mask,_half_visibility

def test_visible_source_cells_are_not_a_prediction_denominator():
 visible=np.zeros((3,5),bool);visible[0,0]=True;visible[2,4]=True
 half=_half_visibility(visible,(2,2))
 assert half.tolist()==[[True,False],[False,False]] # No invented owner for odd edge.
 assert visible.sum()==2

def test_lossless_valid_mask_step_origin_and_count():
 mask=np.array([[255,0],[255,255]],np.uint8);ok,data=cv2.imencode('.png',mask);assert ok
 layer=dict(validMaskUrl='data:image/png;base64,'+base64.b64encode(data).decode(),step=1,width=2,height=2,x=2,y=1,sampleCount=3)
 result=_mask(layer,(4,5));assert result.sum()==3 and result[1,2] and not result[1,3]
 with pytest.raises(ValueError):_mask({**layer,'step':2},(4,5))
 with pytest.raises(ValueError):_mask({**layer,'sampleCount':4},(4,5))
