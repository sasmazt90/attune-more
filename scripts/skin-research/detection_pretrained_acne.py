"""One bounded detection-pretrained comparison; no reuse of exposed test for tuning.
Official CC BY-SA weights converted into Torchvision's mature detector. Both
architectures differ in pooling/anchor edge rounding; this is fine-tuning, not
a claim of numerically identical Detectron2 inference. Product remains separate.
"""
from pathlib import Path
import importlib.util,sys,json,re
import numpy as np
import torch
from torchvision.ops.misc import FrozenBatchNorm2d
from torchvision.models.detection.backbone_utils import resnet_fpn_backbone
from torchvision.models.detection import FasterRCNN
from torchvision.models.detection.anchor_utils import AnchorGenerator
HERE=Path(__file__).parent;sys.path.insert(0,str(HERE))
import train_fasterrcnn_acne as run
STARTUP=run.ROOT/'audit-results/all-health-20261010/detection-startup';OUT=STARTUP.parent/'fasterrcnn-detection-pretrained'
def create():
 rights=json.loads((STARTUP/'rights.json').read_text());assert run.native.sha(STARTUP/'arrays.npz')==rights['convertedArraySHA256'];source=np.load(STARTUP/'arrays.npz',allow_pickle=False)
 body=resnet_fpn_backbone(backbone_name='resnet50',weights=None,norm_layer=FrozenBatchNorm2d,trainable_layers=1)
 model=FasterRCNN(body,num_classes=2,min_size=256,max_size=256,image_mean=[123.675/255,116.280/255,103.530/255],image_std=[1/255]*3,rpn_anchor_generator=AnchorGenerator(((8,),(16,),(32,),(64,),(128,)),((.5,1.,2.),)*5),rpn_pre_nms_top_n_train=600,rpn_post_nms_top_n_train=200,rpn_pre_nms_top_n_test=600,rpn_post_nms_top_n_test=200,box_score_thresh=.01,box_detections_per_img=100)
 for name in ('layer2','layer3','layer4'):
  block=getattr(model.backbone.body,name)[0];block.conv1.stride=(2,2);block.conv2.stride=(1,1)
 mapped={};used=[]
 for key,array in source.items():
  dest=None
  if key.startswith('backbone.bottom_up.stem.conv1.'):
   end=key.removeprefix('backbone.bottom_up.stem.conv1.');dest='backbone.body.'+('bn1.'+end[5:] if end.startswith('norm.') else 'conv1.'+end)
   if end=='weight':array=array[:,::-1].copy() # BGR official input -> RGB source
  elif (m:=re.match(r'backbone.bottom_up.res([2-5])\.(\d+)\.(.+)',key)):
   stage,index,end=m.groups();end=re.sub(r'conv([123])\.norm\.',r'bn\1.',end);end=end.replace('shortcut.norm.','downsample.1.').replace('shortcut.','downsample.0.');dest=f'backbone.body.layer{int(stage)-1}.{index}.{end}'
  elif (m:=re.match(r'backbone.fpn_(lateral|output)([2-5])\.(.+)',key)):
   kind,stage,end=m.groups();dest=f'backbone.fpn.{"inner_blocks" if kind=="lateral" else "layer_blocks"}.{int(stage)-2}.0.{end}'
  elif key.startswith('proposal_generator.rpn_head.'):
   end=key.removeprefix('proposal_generator.rpn_head.').replace('objectness_logits.','cls_logits.').replace('anchor_deltas.','bbox_pred.').replace('conv.','conv.0.0.');dest='rpn.head.'+end
  elif key.startswith('roi_heads.box_head.'):
   dest=key.replace('fc1.','fc6.').replace('fc2.','fc7.')
  if dest:
   assert dest in model.state_dict() and tuple(array.shape)==tuple(model.state_dict()[dest].shape),(key,dest,array.shape)
   mapped[dest]=torch.from_numpy(array.copy());used.append(key)
 missing,unexpected=model.load_state_dict(mapped,strict=False)
 assert not unexpected and all(v.startswith('roi_heads.box_predictor.') for v in missing),missing
 OUT.mkdir(parents=True,exist_ok=True)
 (OUT/'initialization.json').write_text(json.dumps(dict(sourceSHA256=rights['sha256'],sourceTerms=rights['weightsLicense'],mappedTensors=len(mapped),missingTaskSpecificOnly=missing,used=used,adaptations=['RGB channel permutation','ResNet stride in 1x1','native small anchors','new two-class predictor','Torchvision native ROI pooling; not exact D2 inference'],protectedTestNotLoaded=True),indent=2),'utf8')
 return model
run.create=create;run.OUT=OUT;run.STARTUP=OUT/'source'
# Balance flag retains the prior training-only correction. No test response is
# used to set a threshold, schedule or class weight in this comparison.
if __name__=='__main__':
 if sys.argv[1]=='test':raise SystemExit('Exposed prior engineering test is not a fresh protected holdout. No new test allowed.')
 run.main()
