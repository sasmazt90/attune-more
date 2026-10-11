import sys,unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'services/core-api'))
from skin_native_mask import infer_native_mask,CONTRACT
from train_corrected_scope import scheduler_step
import torch

class ColorSession:
 def run(self,names,inputs):
  x=inputs['native_rgb_tile'];rgb=x[0]*np.array(CONTRACT['std'])[:,None,None]+np.array(CONTRACT['mean'])[:,None,None]
  y=np.full((1,7,256,256),-1,np.float32);y[0,2]=rgb[0]-rgb[2];return [y]

class NativeAdapter(unittest.TestCase):
 def test_actual_source_offset_overlap_edges_and_density(self):
  im=np.zeros((410,625,3),np.uint8);im[:]=[210,50,10];im[69:301,137:417]=[10,50,210]
  support=np.ones(im.shape[:2],np.uint8);support[100:130,180:201]=0
  crop=[49,39,587,373];meta=dict(preprocessing=CONTRACT,channel=2,sha256='pinned-full-model')
  v=infer_native_mask(im,ColorSession(),meta,'redness',crop,support)
  expected=np.zeros_like(support,bool);expected[69:301,137:417]=True;expected&=support.astype(bool)
  np.testing.assert_array_equal(v['mask'],expected);self.assertGreater(v['tileCount'],1)
  self.assertEqual(v['visiblePixels'],int(support[39:373,49:587].sum()));self.assertFalse(v['clinicalSeverity'])
 def test_bad_channel_and_contract_fail_closed(self):
  im=np.zeros((30,50,3),np.uint8);s=np.ones((30,50),np.uint8)
  with self.assertRaisesRegex(ValueError,'CHANNEL'):infer_native_mask(im,ColorSession(),dict(preprocessing=CONTRACT,channel=0,sha256='x'),'redness',[0,0,50,30],s)
  with self.assertRaisesRegex(ValueError,'CONTRACT'):infer_native_mask(im,ColorSession(),dict(preprocessing={**CONTRACT,'tile':128},channel=2,sha256='x'),'redness',[0,0,50,30],s)
 def test_inherited_cosine_never_rebounds(self):
  p=torch.nn.Parameter(torch.ones(1));o=torch.optim.AdamW([p],lr=.001);s=torch.optim.lr_scheduler.CosineAnnealingLR(o,4);rates=[]
  for _ in range(9):o.step();scheduler_step(s);rates.append(o.param_groups[0]['lr'])
  self.assertTrue(all(b<=a for a,b in zip(rates,rates[1:])));self.assertEqual(s.last_epoch,4)

if __name__=='__main__':unittest.main()
