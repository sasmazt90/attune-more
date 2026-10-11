"""Actual source/tensor/head gradients; no optimizer updates or user records."""
import collections,json
from pathlib import Path
import cv2,numpy as np,torch
from expanded_sources import ROOT,OUT,PREVIOUS,sha,write
from training_checkpoint import resume
from selected_mask_model import SkinUNet,masked_loss
from selected_sources import TARGETS
from prepare_continuation_masks import TARGETS as DATA_TARGETS
from train_focused_local import yolo_model,acne_tiles,yolo_batch
from selected_yolox_loss import KnownObjectnessBCE,known_cells
from source_skin_support import known_skin_scope
from yolox_numeric import install_bounds

def read(p):return json.loads(p.read_text('utf-8-sig'))
def main():
 torch.set_num_threads(1);cv2.setNumThreads(1);ledger=OUT/'scope-v4-mask-data.json';data=read(ledger);sources={}
 for path in [OUT/'candidates.json',OUT/'supplement/candidates.json',OUT/'negative-expansion/candidates.json',PREVIOUS/'review/candidates.json',PREVIOUS/'manifest.json']:
  for r in read(path)['rows']:
   if r.get('absolutePath'):sources[r['sha256']]=r
 folder=OUT/'negative-mask-continuation';state=read(folder/(folder/'CURRENT').read_text().strip()/'state.json');net=SkinUNet()
 for k,p in net.encoder.named_parameters():p.requires_grad_(not k.startswith(('conv1.','bn1.','layer1.','layer2.')))
 opt=torch.optim.AdamW(net.parameters(),lr=.0001,weight_decay=.001);resume(folder,net,opt,state['identity']);net.train()
 for m in net.modules():
  if isinstance(m,torch.nn.BatchNorm2d):m.eval()
 mean=torch.tensor([.485,.456,.406])[:,None,None];std=torch.tensor([.229,.224,.225])[:,None,None];mask_results=[]
 for t in TARGETS:
  pos=next(r for r in data['rows'] if r['target']==t and r['split']=='train' and r['positivePixels']>0)
  neg=next(r for r in data['rows'] if r['target']==t and r['split']=='train' and r.get('engineeringNegativeROIReviewed') is True and r['knownNegativePixels']>0)
  tensors=[];records=[]
  for r in [pos,neg]:
   p=OUT/data['tensorFolder']/r['id']
   with np.load(p) as f:rgb=f['rgb'].copy();y=f['truth'].copy();s=f['support'].copy()
   assert y.shape==s.shape==(8,256,256) and np.all(y<=s);j=DATA_TARGETS.index(t);assert not np.delete(s,j,axis=0).any()
   source=sources[r['sha256']];image=cv2.imread(source['absolutePath']);assert sha(Path(source['absolutePath']))==r['sha256'];h,w=image.shape[:2];assert [w,h]==r['sourceNativeSize'];a,b,c,d=r['rect'];assert np.array_equal(rgb[:d-b,:c-a],image[b:d,a:c,::-1]);assert np.all(rgb[d-b:]==114) and np.all(rgb[:d-b,c-a:]==114)
   mapping=[DATA_TARGETS.index(k) for k in TARGETS];tensors.append(((torch.from_numpy(rgb.transpose(2,0,1).copy()).float()/255-mean)/std,torch.from_numpy(y[mapping].copy()).float(),torch.from_numpy(s[mapping].copy()).float()))
   records.append(dict(id=r['id'],sha256=r['sha256'],tensorSHA256=sha(p),dataChannel=j,modelChannel=TARGETS.index(t),nativeRGBPaddingAndNormalizationVerified=True,otherChannelsUnknown=True,rect=r['rect'],sourceNativeSize=r['sourceNativeSize']))
  x,y,s=[torch.stack([v[i] for v in tensors]) for i in range(3)];checks=[]
  for image_balanced in [False,True]:
   opt.zero_grad();logits=net(x);logits.retain_grad();loss=masked_loss(logits,y,s,balanced=True,image_balanced=image_balanced);assert torch.isfinite(loss);loss.backward();g=logits.grad;known=s>0;positive=known&(y>0);negative=known&~positive
   assert bool((g[~known]==0).all()) and g[positive].abs().sum()>0 and g[negative].abs().sum()>0
   checks.append(dict(imageBalanced=image_balanced,loss=float(loss.detach()),unknownGradientMax=float(g[~known].abs().max()),positiveGradientSum=float(g[positive].abs().sum()),negativeGradientSum=float(g[negative].abs().sum()),perImageGradientSum=[float(v.abs().sum()) for v in g],predictedPositiveAreaFraction=float((logits.sigmoid()[positive]>=.5).float().mean()),predictedNegativeAreaFraction=float((logits.sigmoid()[negative]>=.5).float().mean())))
  mask_results.append(dict(target=t,tensors=records,lossChecks=checks));print('ACTUAL MASK GRADIENT',t,flush=True)
 del net,opt
 folder=OUT/'negative-yolox';state=read(folder/(folder/'CURRENT').read_text().strip()/'state.json');net=yolo_model();install_bounds(net)
 for k,p in net.named_parameters():p.requires_grad_(not k.startswith(('backbone.backbone.stem','backbone.backbone.dark2')))
 opt=torch.optim.AdamW([p for p in net.parameters() if p.requires_grad],lr=.00015,weight_decay=.001);resume(folder,net,opt,state['identity']);net.train()
 for m in net.modules():
  if isinstance(m,torch.nn.BatchNorm2d):m.eval()
 class Probe(KnownObjectnessBCE):
  def forward(self,x,y):
   if self._calls==0:self.x=x;self.y=y;x.retain_grad()
   return super().forward(x,y)
 obj=Probe();net.head.bcewithlog_loss=obj;rows=[r for r in read(OUT/'negative-expanded-detector-data.json')['rows'] if r['split']=='train'];tiles=acne_tiles(rows,False);pos=next(t for t in tiles if t['boxes']);neg=next(t for t in tiles if not t['boxes'] and t['row']['negativeROI'])
 batch=[pos,neg]
 for t in batch:
  im=cv2.imread(t['row']['absolutePath']);scope=known_skin_scope(t['row'],im) if t['row']['negativeROI'] else np.zeros(im.shape[:2],np.uint8);t['known']=known_cells(scope,t['rect'],bool(t['row']['negativeROI']))
 obj.known=torch.cat([t['known'] for t in batch]);x,y=yolo_batch(batch);loss=net(x,y)['total_loss'];assert torch.isfinite(loss);loss.backward();g=obj.x.grad;positive=obj.y>0;negative=obj.known&~positive;unknown=~obj.known&~positive
 assert bool((g[unknown]==0).all()) and g[positive].abs().sum()>0 and g[negative].abs().sum()>0
 yolo=dict(loss=float(loss.detach()),assignedPositives=int(positive.sum()),knownNegativeCells=int(negative.sum()),unknownCells=int(unknown.sum()),unknownGradientMax=float(g[unknown].abs().max()),positiveGradientSum=float(g[positive].abs().sum()),negativeGradientSum=float(g[negative].abs().sum()),classBCECallCount=obj._calls,batch=[dict(sha256=t['row']['sha256'],rect=t['rect'],boxCount=len(t['boxes'])) for t in batch],optimizerUpdates=0)
 write('interim-diagnosis/actual-loss-v2.json',dict(dataChannelMapping=[DATA_TARGETS.index(t) for t in TARGETS],mask=mask_results,yolox=yolo,originalModelAndOptimizerFilesUntouched=True,finalOpened=False));print('ALL REAL LOSS CHECKS COMPLETE',flush=True)
if __name__=='__main__':main()
