"""Reproduce the next saved native batch without altering the checkpoint."""
import json,collections,sys
import cv2,numpy as np,torch
from safetensors.torch import load_file
from expanded_sources import OUT
from train_focused_local import yolo_model,acne_tiles,yolo_batch
from selected_yolox_loss import KnownObjectnessBCE,known_cells
from training_checkpoint import resume
from yolox_numeric import install_bounds

def main():
 torch.set_num_threads(2);cv2.setNumThreads(1);folder=OUT/'yolox';generation=folder/(folder/'CURRENT').read_text('utf8');state=json.loads((generation/'state.json').read_text('utf8'));data=json.loads((OUT/'detector-data.json').read_text('utf8'));rows=[r for r in data['rows'] if r['split']=='train'];scopes={}
 for r in rows:
  roi=np.zeros((r['height'],r['width']),np.uint8)
  if r['negativeROI']:
   p=np.array([[v['x']*r['width'],v['y']*r['height']] for v in r['landmarks'][:468]],np.float32);cv2.fillConvexPoly(roi,cv2.convexHull(np.rint(p).astype(np.int32)),1)
  scopes[r['sha256']]=roi
 items=[t for t in acne_tiles(rows,training=False) if t['boxes'] or t['row']['negativeROI'] and known_cells(scopes[t['row']['sha256']],t['rect'],True).any()]
 net=yolo_model();net.load_state_dict(load_file(str(generation/'model.safetensors')));net.train()
 if '--bounded' in sys.argv:install_bounds(net)
 for k,p in net.named_parameters():p.requires_grad_(not k.startswith(('backbone.backbone.stem','backbone.backbone.dark2')))
 for m in net.modules():
  if isinstance(m,torch.nn.BatchNorm2d):m.eval()
 obj=KnownObjectnessBCE();net.head.bcewithlog_loss=obj;logs=[]
 for k,conv in enumerate(net.head.reg_preds):
  def observe(module,inputs,output,level=k):logs.append(dict(level=level,rawWHMin=float(output[:,2:4].min()),rawWHMax=float(output[:,2:4].max())))
  conv.register_forward_hook(observe)
 opt=torch.optim.AdamW([p for p in net.parameters() if p.requires_grad],lr=.00015,weight_decay=.001);state=resume(folder,net,opt,state['identity'])
 for cursor in range(state['cursor'],min(len(state['order']),state['cursor']+128),2):
  ids=state['order'][cursor:cursor+2];batch=[items[i] for i in ids];obj.known=torch.cat([known_cells(scopes[t['row']['sha256']],t['rect'],bool(t['row']['negativeROI'])) for t in batch]);x,y=yolo_batch(batch);opt.zero_grad();logs.clear()
  print('replay epoch/cursor',state['epoch'],cursor,'batch',[(t['row']['sha256'],t['rect'],len(t['boxes'])) for t in batch],flush=True)
  with torch.autograd.detect_anomaly(check_nan=True):
   value=net(x,y)['total_loss'];print('loss',float(value),logs,flush=True);value.backward()
  bad=[k for k,p in net.named_parameters() if p.grad is not None and not torch.isfinite(p.grad).all()];maximum=max(float(p.grad.abs().max()) for p in net.parameters() if p.grad is not None)
  print('bad gradients',bad,'maximum',maximum,flush=True);torch.nn.utils.clip_grad_norm_(net.parameters(),1,error_if_nonfinite=True);opt.step()

if __name__=='__main__':main()
