"""The learnability branch must not silently change boxes/classes or BN."""
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/skin-research'))
from heavy_job_lease import HeavyJobLease


class ObjectnessFeatures(unittest.TestCase):
    def setUp(self):
        import torch
        from yolox_p2 import build_yolox_p2_model
        from acne_objectness_features import install_objectness_features,configure_learnable,frozen_hash
        self.torch=torch;self.install=install_objectness_features;self.configure=configure_learnable;self.frozen_hash=frozen_hash
        torch.set_num_threads(2);torch.manual_seed(128)
        self.net=build_yolox_p2_model().eval();self.x=torch.randn(1,3,64,64)

    def test_initial_complete_output_parity_and_no_stale_frame(self):
        with self.torch.inference_mode():before=self.net(self.x).clone()
        self.install(self.net);self.net.eval()
        with self.torch.inference_mode():after=self.net(self.x)
        self.assertTrue(self.torch.equal(before,after));self.assertFalse(self.net.head._objectness_feature_inputs)

    def test_learning_feature_weights_cannot_change_boxes_or_classes(self):
        self.install(self.net);names=self.configure(self.net);self.net.eval();frozen=self.frozen_hash(self.net,names)
        with self.torch.inference_mode():before=self.net(self.x).clone()
        with self.torch.no_grad():
            self.net.head.obj_convs[0][0].conv.weight.add_(.01)
        with self.torch.inference_mode():after=self.net(self.x)
        self.assertTrue(self.torch.equal(before[:,:,:4],after[:,:,:4]));self.assertTrue(self.torch.equal(before[:,:,5:],after[:,:,5:]));self.assertGreater(float((before[:,:,4]-after[:,:,4]).abs().max()),0)
        self.assertEqual(frozen,self.frozen_hash(self.net,names))

    def test_trainable_scope_and_frozen_bn(self):
        self.install(self.net);names=self.configure(self.net)
        self.assertEqual(len(names),16);self.assertFalse(any('stems' in name or '.bn.' in name or 'reg_convs' in name or 'cls_' in name for name in names))
        self.assertFalse(any(m.training for m in self.net.modules() if isinstance(m,self.torch.nn.modules.batchnorm._BatchNorm)))

    def test_new_graph_requires_its_own_strict_checkpoint_loader(self):
        self.install(self.net)
        from yolox_p2 import build_yolox_p2_model
        with self.assertRaisesRegex(RuntimeError,'Unexpected key'):
            build_yolox_p2_model().load_state_dict(self.net.state_dict(),strict=True)

    def test_independent_weights_and_double_install_rejected(self):
        self.install(self.net)
        a=self.net.head.reg_convs[0][0].conv.weight;b=self.net.head.obj_convs[0][0].conv.weight
        self.assertNotEqual(a.data_ptr(),b.data_ptr());self.assertTrue(self.torch.equal(a,b))
        with self.assertRaisesRegex(ValueError,'already installed'):self.install(self.net)


if __name__=='__main__':
    with HeavyJobLease('CDC-acne-feature-branch-regressions',peak_mib=1350,minimum_available_mib=1600,memory_metric='private'):
        unittest.main()
