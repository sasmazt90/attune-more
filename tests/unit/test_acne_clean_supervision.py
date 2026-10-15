"""Focused partial-label safety regressions; no dataset-wide campaign."""
import sys,unittest
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/skin-research'))
from acne_takeover_support import strict_clean_mask

class CleanSupervision(unittest.TestCase):
    def test_generated_whole_image_polygon_is_not_clean_truth(self):
        row=dict(split='train',annotations=[dict(box=[20,20,25,25])],negativeROI=None,negativeROIs=[dict(polygon=[[0,0],[0,63],[63,63],[63,0]])])
        mask,weight=strict_clean_mask(row,np.full((64,64,3),128,np.uint8))
        self.assertFalse(mask.any());self.assertFalse(weight.any())

    def test_unlabeled_photo_is_not_a_reviewed_negative(self):
        mask,weight=strict_clean_mask(dict(split='train',annotations=[]),np.full((32,32,3),128,np.uint8))
        self.assertFalse(mask.any());self.assertFalse(weight.any())

    def test_whole_face_marker_without_approved_local_support_is_unknown(self):
        row=dict(split='train',annotations=[],negativeROI='reviewed-visible-face',landmarks=[dict(x=.5,y=.5)]*478)
        mask,weight=strict_clean_mask(row,np.full((32,32,3),128,np.uint8))
        self.assertFalse(mask.any());self.assertFalse(weight.any())

    def test_validation_cannot_enter_train_mask_builder(self):
        with self.assertRaisesRegex(ValueError,'TRAIN_ONLY_MASK'):
            strict_clean_mask(dict(split='validation',annotations=[]),np.zeros((32,32,3),np.uint8))

    def test_pseudo_box_does_not_create_positive_or_negative_truth(self):
        row=dict(split='train',annotations=[],negativeROI=None)
        mask,_=strict_clean_mask(row,np.full((64,64,3),128,np.uint8),all_holes=[[10,10,20,20]])
        self.assertFalse(mask.any())

if __name__=='__main__':unittest.main()
