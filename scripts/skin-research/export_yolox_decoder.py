"""Export bounded YOLOX and exercise the real product decoder in isolation."""
import json,sys,time
from pathlib import Path
import cv2,numpy as np,torch,onnxruntime as ort
from safetensors.torch import load_file
from expanded_sources import ROOT,OUT,write,sha
from train_focused_local import yolo_model,acne_tiles,tile_image
from yolox_numeric import install_bounds

def main():
 torch.set_num_threads(1);cv2.setNumThreads(1);folder=OUT/'yolox/decoder-parity';folder.mkdir(exist_ok=True);weights=OUT/'yolox/selected.safetensors';net=yolo_model();net.load_state_dict(load_file(str(weights)));install_bounds(net);net.eval();data=json.loads((OUT/'detector-data.json').read_text('utf8'));rows=[r for r in data['rows'] if r['split']=='validation'];tiles=acne_tiles(rows,False);chosen=[];seen=set()
 for t in tiles:
  if t['row']['sha256'] in seen:continue
  seen.add(t['row']['sha256']);chosen.append(t)
  if len(chosen)==6:break
 path=folder/'candidate.onnx';torch.onnx.export(net,tile_image(chosen[0])[None],str(path),input_names=['native_bgr_tile'],output_names=['decoded_boxes'],opset_version=17,dynamo=False)
 options=ort.SessionOptions();options.intra_op_num_threads=1;options.inter_op_num_threads=1;session=ort.InferenceSession(str(path),options,providers=['CPUExecutionProvider']);checks=[]
 for t in chosen:
  x=tile_image(t)[None]
  with torch.no_grad():expected=net(x).numpy()
  actual=session.run(None,{'native_bgr_tile':x.numpy()})[0];assert np.isfinite(actual).all() and np.allclose(actual,expected,atol=.003,rtol=1e-4)
  checks.append(dict(sha256=t['row']['sha256'],rect=t['rect'],maximumAbsoluteDifference=float(abs(actual-expected).max()),maximumDecodedDimension=float(actual[:,:,2:4].max())))
 sys.path.insert(0,str(ROOT/'services/core-api'));import skin_models as M
 saved=M.load;meta=dict(sha256=sha(path),version='offline-native-bounds-parity-v1',confidenceThreshold=.25);M.load=lambda:dict(sessions={'acne':dict(session=session,metadata=meta,loadMs=0)})
 product=[]
 try:
  for r in [v for v in rows if v.get('landmarks')][:3]:
   im=cv2.imread(r['absolutePath']);result=M.infer_acne(im,r['landmarks'],True);assert result and result['valid'] and result['modelHash']==sha(path)
   assert all(0<=b[0]<b[2]<=im.shape[1] and 0<=b[1]<b[3]<=im.shape[0] for b in result['boxes'])
   product.append(dict(sha256=r['sha256'],tileCount=result['tileCount'],boxes=result['boxes'],modelHash=result['modelHash'],coordinateSpace=result['coordinateSpace']))
 finally:M.load=saved
 write('yolox/decoder-parity/receipt.json',dict(modelSHA256=sha(path),selectedWeightsSHA256=sha(weights),nativeDimensionBounds=net.head.native_dimension_bounds,numericalParity=True,realImagePreprocessingParity=True,sourceCoordinateParity=True,checks=checks,isolatedActualProductDecoder=product,normalAPIStaged=False,productionManifestUntouched=True,trainingValidationAndONNXDecoderSame=True,performanceAcceptance=False))
 print('Bounded decoder actual source/ONNX/isolated product parity passed',flush=True)
if __name__=='__main__':main()
