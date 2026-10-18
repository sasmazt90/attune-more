import sys,unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'services/core-api'))
from acne_box_support import accepted_boxes,region_envelopes,box_area

class BoxSupport(unittest.TestCase):
 def test_visible_skin_and_single_region_ownership(self):
  support=np.ones((100,100),bool);envelopes={'forehead':support,'nose':support};hole=np.zeros_like(support);hair=hole.copy()
  assigned,rejected=accepted_boxes([[20,20,30,30,.8]],envelopes,support,hair,hole,'photo',1,(0,0))
  self.assertEqual(len(assigned['forehead']),1);self.assertEqual(assigned['nose'],[]);self.assertFalse(rejected)
  self.assertEqual(box_area(assigned['forehead'],support.shape,1,(0,0)).sum(),100)
 def test_holes_hair_background_and_visible_coverage_stay_gated(self):
  support=np.ones((100,100),bool);env={'forehead':support.copy()};hole=np.zeros_like(support);hair=hole.copy();hole[25,25]=True;hair[45,45]=True;support[60:]=False
  assigned,rejected=accepted_boxes([[20,20,30,30,.8],[40,40,50,50,.9],[65,65,80,80,.9]],env,support,hair,hole,'p',1,(0,0))
  self.assertFalse(assigned['forehead']);self.assertEqual(len(rejected),3)
 def test_envelope_fills_triangle_gaps_without_changing_mesh(self):
  mesh={'forehead':{'points':[dict(x=10,y=10),dict(x=80,y=10),dict(x=80,y=80),dict(x=10,y=80)],'edges':[]}}
  m=region_envelopes(mesh,(100,100),1,(0,0));self.assertTrue(m['forehead'][50,50]);self.assertFalse(m['forehead'][0,0]);self.assertEqual(mesh['forehead']['edges'],[])
if __name__=='__main__':unittest.main()
