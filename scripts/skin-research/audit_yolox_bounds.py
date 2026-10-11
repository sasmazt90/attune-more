"""Audit current YOLOX assignment saturation without optimizer updates."""
import json,math,shutil
from pathlib import Path
import cv2,numpy as np,torch
from safetensors.torch import load_file
from expanded_sources import OUT,write,sha
from train_focused_local import yolo_model,acne_tiles,yolo_batch
from yolox_numeric import install_bounds
from source_skin_support import known_skin_scope
from selected_yolox_loss import KnownObjectnessBCE,known_cells

def main():
 torch.set_num_threads(2);cv2.setNumThreads(1)
 folder=OUT/'yolox';dest=folder/'coordinate-saturation-audit';dest.mkdir(exist_ok=True)
 generation=folder/(folder/'CURRENT').read_text('utf8');state=json.loads((generation/'state.json').read_text('utf8'));shutil.copy2(generation/'model.safetensors',dest/'snapshot.safetensors')
 assert sha(dest/'snapshot.safetensors')==state['modelSHA256']
 rows=[r for r in json.loads((OUT/'detector-data.json').read_text('utf8'))['rows'] if r['split']=='train'];items=acne_tiles(rows,False)
 pos=[t for t in items if t['boxes']];neg=[t for t in items if not t['boxes'] and t['row']['negativeROI']]
 # Diverse source photos, not six repeated tiles from one source.
 selected=[];seen=set()
 for pool in [pos,neg]:
  count=0
  for t in pool:
   if t['row']['sha256'] in seen:continue
   seen.add(t['row']['sha256']);selected.append(t);count+=1
   if count==6:break
 net=yolo_model();net.load_state_dict(load_file(str(dest/'snapshot.safetensors')));raw={};assigned=[]
 for level,(conv,stride) in enumerate(zip(net.head.reg_preds,net.head.strides)):
  def capture(module,inputs,output,level=level,stride=stride):raw[level]=dict(values=output[:,2:4].detach().flatten(2).permute(0,2,1),stride=stride)
  conv.register_forward_hook(capture)
 install_bounds(net);original=net.head.get_assignments
 def audit(*args,**kwargs):
  result=original(*args,**kwargs);batch_idx=args[0];fg=result[1].cpu();saturated=torch.cat([((v['values']<math.log(.1/v['stride']))|(v['values']>math.log(768/v['stride']))).any(2) for _,v in sorted(raw.items())],1)[batch_idx].cpu()
  assigned.append(dict(assigned=int(fg.sum()),assignedSaturated=int((saturated&fg).sum()),unassigned=int((~fg).sum()),unassignedSaturated=int((saturated&~fg).sum()),matchedIoUMean=float(result[2].mean()),rawWHMin=min(float(v['values'].min()) for v in raw.values()),rawWHMax=max(float(v['values'].max()) for v in raw.values())))
  return result
 net.head.get_assignments=audit;net.train()
 for m in net.modules():
  if isinstance(m,torch.nn.BatchNorm2d):m.eval()
 obj=KnownObjectnessBCE();net.head.bcewithlog_loss=obj;receipts=[]
 for t in selected:
  a,b,c,d=t['rect'];boxes=np.array(t['boxes'],np.float32).reshape(-1,4)
  assert not len(boxes) or (np.all(boxes[:,0:2]>=0) and np.all(boxes[:,2]<=c-a) and np.all(boxes[:,3]<=d-b) and np.all(boxes[:,2:]-boxes[:,:2]>=2))
  x,y=yolo_batch([t]);reconstruction=torch.cat([y[0,:,1:3]-y[0,:,3:5]/2,y[0,:,1:3]+y[0,:,3:5]/2],1)
  assert np.allclose(reconstruction.numpy(),boxes,atol=1e-4)
  im=cv2.imread(t['row']['absolutePath']);scope=known_skin_scope(t['row'],im) if t['row']['negativeROI'] else np.zeros(im.shape[:2],np.uint8);obj.known=known_cells(scope,t['rect'],bool(t['row']['negativeROI']));raw.clear();start=len(assigned)
  with torch.no_grad():loss=float(net(x,y)['total_loss'])
  assert math.isfinite(loss)
  receipts.append(dict(sha256=t['row']['sha256'],rect=t['rect'],boxCount=len(boxes),boxSizes=(boxes[:,2:]-boxes[:,:2]).tolist(),targetRoundtripPassed=True,nativeBGRNoNormalization=True,noSourceUpsampling=True,loss=loss,assignments=assigned[start:]))
 totals={k:sum(r[k] for r in assigned) for k in ['assigned','assignedSaturated','unassigned','unassignedSaturated']}
 write('yolox/coordinate-saturation-audit/receipt.json',dict(version='assigned-native-bounds-audit-v1',checkpointModelSHA256=state['modelSHA256'],epoch=state['epoch'],cursor=state['cursor'],rows=receipts,totals=totals,trainingUpdates=0,originalOptimizerUntouched=True,coordinateContract='source xyxy -> tile xyxy -> class/cx/cy/w/h native384 -> source xyxy',finiteIsAcceptance=False))
 print(json.dumps(totals),flush=True)
if __name__=='__main__':main()
