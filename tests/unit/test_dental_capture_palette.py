"""Pixel-class mutual exclusion, not clinical color calibration."""
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'services/core-api'))
from dental_analysis import dental_pixels

def test_native_warm_enamel_is_not_also_tongue_support():
    mask=np.ones((80,120),bool)
    for bgr in [(150,190,220),(120,170,210),(190,205,220),(195,200,205),(160,165,190),(180,185,215)]:
        image=np.full((80,120,3),bgr,np.uint8)
        tooth,glare,gum,tongue,_=dental_pixels(image,mask,native_capture=True)
        assert tooth.mean()>.95 and not gum.any() and not tongue.any() and not glare.any()

def test_native_pink_tissue_and_clipped_glare_cannot_supply_enamel():
    mask=np.ones((80,120),bool)
    for bgr in [(105,110,175),(100,110,135),(255,255,255)]:
        tooth,glare,gum,tongue,_=dental_pixels(np.full((80,120,3),bgr,np.uint8),mask,native_capture=True)
        assert not tooth.any()
        assert glare.any() if bgr==(255,255,255) else gum.any()
