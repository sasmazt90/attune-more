"""Research detector contracts. No claim of detection quality or product approval."""
import importlib.util
from pathlib import Path
import numpy as np
import pytest
import torch
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('research_acne',ROOT/'scripts/skin-research/train_native_acne.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def test_overlap_candidates_merge_and_one_truth_cannot_match_twice():
 p=[{'box':[20,30,45,55],'confidence':.9},{'box':[21,31,46,56],'confidence':.8},{'box':[100,30,124,54],'confidence':.7}]
 merged=m.filtered(p,.5,[]);assert len(merged)==2
 usedp,usedg=m.matches(p,[[20,30,45,55]])
 assert len(usedp)==len(usedg)==1

def test_technical_failure_never_becomes_valid_zero():
 class Broken(torch.nn.Module):
  def forward(self,x):
   h,w=x.shape[-2:];return torch.full((1,1,h//4,w//4),float('nan')),torch.zeros((1,2,h//4,w//4))
 with pytest.raises(RuntimeError,match='INVALID_MODEL_OUTPUT'):m.infer(Broken(),np.zeros((384,384,3),np.uint8))
 with pytest.raises(ValueError,match='INVALID_NATIVE_RGB'):m.infer(Broken(),np.zeros((384,384),np.uint8))

def test_negative_false_candidates_are_not_hidden_by_positive_averages():
 rows=[{'index':1,'boxes':[[20,30,45,55]],'ignore':[],'cropBox':[0,0,300,300]},{'index':2,'boxes':[],'ignore':[],'cropBox':[0,0,300,300]}]
 p={'box':[20,30,45,55],'confidence':.9}
 metric=m.metrics(rows,[[p],[p]],.5)
 assert (metric['tp'],metric['fp'],metric['fn'])==(1,1,0)
 assert metric['positivePhotos']==metric['negativePhotos']==1
 assert metric['meanFPPerNegativePhoto']==1 and metric['precision']==.5
