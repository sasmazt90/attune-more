import sys,unittest
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'services/core-api'))
from acne_box_support_staging import principled_accepted_boxes

class StagingSupport(unittest.TestCase):
    def setUp(self):
        self.skin=np.ones((100,100),bool);self.hair=np.zeros((100,100),bool);self.holes=np.zeros((100,100),np.uint8);self.envelope={'forehead':np.ones((100,100),bool)};self.image=np.full((200,200,3),128,np.uint8)
    def run_box(self,**kwargs):
        return principled_accepted_boxes([[80,90,100,110,.7]],self.envelope,self.skin,self.hair,self.holes,'arbitrary-source',.5,(20,30),source_shape=(200,200),bgr=self.image,**kwargs)
    def test_source_coordinates_remain_native(self):
        assigned,rejected=self.run_box();self.assertFalse(rejected);box=assigned['forehead'][0];self.assertEqual([box['x'],box['y'],box['width'],box['height']],[80,90,20,20]);self.assertEqual(box['coordinateSpace'],'source-pixels')
    def test_eyes_are_not_rescued_by_redness(self):
        self.holes[35,35]=255;self.image[90:110,80:100]=[50,50,200]
        assigned,rejected=self.run_box();self.assertFalse(assigned['forehead']);self.assertEqual(rejected[0]['reason'],'ANATOMICAL_HOLE')
    def test_dense_hair_remains_blocked(self):
        self.hair[30:40,30:40]=True
        assigned,rejected=self.run_box();self.assertFalse(assigned['forehead']);self.assertEqual(rejected[0]['reason'],'ANATOMICAL_HAIR_DENSE')
    def test_hidden_region_is_not_assigned(self):
        assigned,rejected=self.run_box(visible_regions=['leftCheek']);self.assertFalse(assigned['forehead']);self.assertEqual(rejected[0]['reason'],'UNCERTAIN_ANATOMICAL_REGION')
    def test_single_center_dark_pixel_can_be_supported_by_tissue(self):
        self.hair[35,35]=True;self.skin[35,35]=False;self.image[90:110,80:100]=[65,70,180]
        assigned,rejected=self.run_box();self.assertFalse(rejected);self.assertEqual(len(assigned['forehead']),1)

if __name__=='__main__':unittest.main()
