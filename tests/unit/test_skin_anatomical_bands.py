"""Distinct anatomical supports and source-coordinate scaling, not disease labels."""
import numpy as np
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'services/core-api'))
from appearance_analysis import eye_skin_bands
def test_lower_lid_and_outer_corner_bands_exclude_eye_and_brow():
 p=[dict(x=.5,y=.5) for _ in range(478)]
 for i,x,y in [(234,.15,.5),(454,.85,.5)]:p[i]=dict(x=x,y=y)
 for ids,xs in [([33,163,144,145,153,154,155,133],np.linspace(.25,.42,8)),([263,390,373,374,380,381,382,362],np.linspace(.75,.58,8))]:
  for i,x in zip(ids,xs):p[i]=dict(x=float(x),y=.4)
 bands=eye_skin_bands(p,(500,500),1,(0,0),(500,500))
 assert set(bands)=={'dark','bags','lines'}
 assert bands['dark'].any() and bands['bags'].any() and bands['lines'].any()
 assert not bands['dark'][:204].any() # rounded 4.2 px lower-lid margin
 assert not bands['bags'][:208].any() # rounded 7.7 px lower-lid margin
 assert not np.array_equal(bands['dark'],bands['bags'])
 assert not bands['lines'][210,165] and not bands['lines'][210,335] # eye centre is not crow's feet
 shifted=eye_skin_bands(p,(250,250),.5,(0,0),(500,500))
 assert abs(shifted['dark'].sum()*4/bands['dark'].sum()-1)<.12
