"""Meaningful object-label scope tests; no unlabelled pixel-health assumption."""
import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/skin-research'))
from heavy_job_lease import HeavyJobLease
from acne_object_negatives import reviewed_object_negative_mask

class ObjectNegativeScope(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import torch
        cls.torch=torch
    def mask(self,decoded,negatives,protected=()):
        t=self.torch
        return reviewed_object_negative_mask(t.tensor(decoded,dtype=t.float32).reshape(-1,4),t.tensor(negatives,dtype=t.float32).reshape(-1,4),t.tensor(protected,dtype=t.float32).reshape(-1,4)).flatten().tolist()
    def test_same_object_known(self):self.assertEqual(self.mask([[10,10,8,8]],[[6,6,14,14]]),[True])
    def test_unknown_surrounding_stays_unknown(self):self.assertEqual(self.mask([[30,30,8,8]],[[6,6,14,14]]),[False])
    def test_pimple_safety_margin_wins(self):self.assertEqual(self.mask([[10,10,8,8]],[[6,6,14,14]],[[4,4,16,16]]),[False])
    def test_no_labels_no_new_negative(self):self.assertEqual(self.mask([[10,10,8,8]],[]),[False])
    def test_tiny_subregion_is_not_full_object(self):self.assertEqual(self.mask([[10,10,1,1]],[[6,6,14,14]]),[False])
    def test_inner_object_box_can_match(self):self.assertEqual(self.mask([[10,10,4,4]],[[6,6,14,14]]),[True])
    def test_source_origin_translation(self):self.assertEqual(self.mask([[110,210,8,8]],[[106,206,114,214]]),[True])
    def test_native_half_scale_contract(self):self.assertEqual(self.mask([[5,5,4,4]],[[3,3,7,7]]),[True])
    def test_assigned_positive_is_never_overridden(self):
        from focal_objectness_loss import SigmoidFocalObjectnessLoss
        t=self.torch;f=SigmoidFocalObjectnessLoss();f.known=t.tensor([[True],[False]]);f.boundary_weights=t.ones((2,1));logits=t.tensor([[1.],[1.]],requires_grad=True);truth=t.tensor([[1.],[0.]])
        f(logits,truth).sum().backward();self.assertLess(logits.grad[0].item(),0);self.assertEqual(logits.grad[1].item(),0)

if __name__=='__main__':
    with HeavyJobLease('CDC-acne-object-negative-focused-tests',peak_mib=1350,minimum_available_mib=1600,memory_metric='private'):
        unittest.main()
