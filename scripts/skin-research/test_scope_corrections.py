import json,tempfile,unittest
from pathlib import Path
import numpy as np,torch
from mask_scope_metrics import SourceScopes,global_score
from selected_yolox_loss import KnownObjectnessBCE
from selected_mask_model import masked_loss
from acceptance_data_evidence import final_data,digest

class ScopeCorrections(unittest.TestCase):
 def row(self,identifier,rect,**kw):return dict(id=identifier,sha256='photo',group='family',target='acne',rect=rect,sourceNativeSize=[3,2],completeROI=False,**kw)
 def test_unknown_and_overlap_are_not_negative_or_extra_photo(self):
  s=SourceScopes();s.add(self.row('a',[0,0,2,2]),np.ones((2,2)),np.array([[1,0],[0,0]]),np.array([[1,0],[0,0]]))
  s.add(self.row('b',[1,0,3,2]),np.ones((2,2)),np.zeros((2,2)),np.ones((2,2)))
  m=s.finish(['acne'])['acne'];self.assertEqual(m['positiveSources'],1);self.assertEqual(m['positiveRecall'],1);self.assertIsNone(m['negativeFPR']);self.assertIsNone(m['Dice']);self.assertFalse(m['rankingUsable']);self.assertEqual(m['rows'][0]['predictedUnknownPixels'],5)
 def test_reviewed_negative_separate_from_partial_positive(self):
  s=SourceScopes();s.add(self.row('p',[0,0,2,2]),np.ones((2,2)),np.array([[1,0],[0,0]]),np.array([[1,0],[0,0]]))
  r=self.row('n',[1,0,3,2],engineeringNegativeROIReviewed=True);r['completeROI']=True
  s.add(r,np.ones((2,2)),np.zeros((2,2)),np.ones((2,2)));m=s.finish(['acne'])['acne']
  self.assertEqual(m['negativeFPR'],1);self.assertEqual(m['reviewedNegativeSupportSources'],1);self.assertEqual(m['positiveSources'],1);self.assertEqual(m['developmentScore'],0);self.assertIsNone(m['Dice'])
 def test_global_does_not_drop_missing_target(self):
  self.assertIsNone(global_score({'acne':{'developmentScore':.7},'tone':{'developmentScore':None}},['acne','tone']))
 def test_objectness_shape_fails_closed_and_class_is_unmasked(self):
  b=KnownObjectnessBCE();b.known=torch.zeros((3,1),dtype=torch.bool)
  with self.assertRaisesRegex(ValueError,'SHAPE'):b(torch.zeros(4,1),torch.zeros(4,1))
  b.known=torch.tensor([[False],[True],[False]]);x=torch.zeros(3,1,requires_grad=True)
  b(x,torch.tensor([[1.],[0.],[0.]])).sum().backward()
  self.assertNotEqual(x.grad[0].item(),0);self.assertNotEqual(x.grad[1].item(),0);self.assertEqual(x.grad[2].item(),0)
  self.assertGreater(b(torch.zeros(1,1),torch.ones(1,1)).sum().item(),0)
  with self.assertRaisesRegex(ValueError,'NOT_ARMED'):b(torch.zeros(3,1),torch.zeros(3,1))
 def test_mask_unknown_zero_gradient_and_equal_image_contribution(self):
  x=torch.zeros(2,1,4,4,requires_grad=True);y=torch.zeros_like(x);s=torch.zeros_like(x);s[0,0,0,0]=1;s[1,0,:,:]=1
  v=masked_loss(x,y,s,image_balanced=True);v.backward();self.assertEqual(x.grad[0,0,1,1].item(),0);self.assertAlmostEqual(x.grad[0].abs().sum().item(),x.grad[1].abs().sum().item())
 def test_missing_final_evidence_is_unknown_and_hash_mismatch_not_true(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);self.assertIsNone(final_data(p,'acne')['unusedHoldout'])
   e=p/'review.json';e.write_text(json.dumps({'done':True}));ref={'file':'review.json','sha256':digest(e),'keyPath':['done']}
   (p/'final-evidence-index.json').write_text(json.dumps({'targets':{'acne':{'unusedHoldout':ref}}}))
   self.assertTrue(final_data(p,'acne')['unusedHoldout']);e.write_text(json.dumps({'done':False}));self.assertIsNone(final_data(p,'acne')['unusedHoldout'])

if __name__=='__main__':unittest.main()
