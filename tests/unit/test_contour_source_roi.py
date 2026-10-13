"""Full-source numerical reference for source-origin and border remapping."""
import sys,subprocess,types
from pathlib import Path
import numpy as np,pytest
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'services/core-api'))
import contour_appearance as C
old=types.ModuleType('previous_contour');exec(subprocess.check_output(['git','show','7d876e0:services/core-api/contour_appearance.py'],cwd=ROOT).decode(),old.__dict__)

@pytest.mark.parametrize('shift',[-35,0,142])
def test_exterior_roi_matches_full_source_at_borders_and_subpixel_phase(shift):
    rng=np.random.default_rng(620);image=rng.integers(35,240,(160,192,3),dtype=np.uint8)
    line=np.c_[np.linspace(20,110,96)+shift,np.linspace(35,100,96)];normal=np.tile([.8,.6],(96,1));coords=line[:,None,:]+normal[:,None,:]*np.linspace(-4,4,41)[None,:,None]
    assert np.array_equal(old.exterior_support(image,line,normal,coords,120),C.exterior_support(image,line,normal,coords,120))
