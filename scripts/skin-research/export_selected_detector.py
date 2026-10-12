"""Real-source staging export of the exact frozen detector winner. No promotion."""
import json
from pathlib import Path
import cv2,numpy as np,torch,onnxruntime as ort
from safetensors.torch import load_file
from expanded_sources import OUT,ROOT,sha,write
from audit_current_onnx import RawYOLO,PTSession,M
from train_focused_local import yolo_model,acne_tiles,tile_image

def read(p):return json.loads(p.read_text('utf8'))
def main():
 torch.set_num_threads(1);cv2.setNumThreads(1);base=OUT/'interim-diagnosis';selection=read(base/'frozen-detector-selection.json');winner=selection['selected'];digest=winner['model']['sha256'];weights=Path(winner['model']['folder'])/'model.safetensors';assert sha(weights)==digest
 name='selected-detector-export-'+digest[:12];folder=base/name;folder.mkdir(exist_ok=True)
 source_selection=base/'detector-source-selection.json';data_path=OUT/'negative-expanded-detector-data.json';data=read(data_path);assert sha(data_path)==selection['validationDataSHA256']
 chosen=read(source_selection)['rows'];rows=[next(r for r in data['rows'] if r['sha256']==s['sha256']) for s in chosen]
 protocol=dict(weightsSHA256=digest,dataSHA256=sha(data_path),sourceSelectionSHA256=sha(source_selection),exportCodeSHA256=sha(Path(__file__)),productDecoderSHA256=sha(ROOT/'services/core-api/skin_models.py'),numericBoundsSHA256=sha(ROOT/'scripts/skin-research/yolox_numeric.py'),input=dict(BGR=True,size=384,native=True,padding=114,range=[0,255]),atol=.003,rtol=.0001,threshold=.7,finalOpened=False)
 pp=folder/'protocol.json'
 if pp.exists():assert read(pp)==protocol
 else:write('interim-diagnosis/'+name+'/protocol.json',protocol)
 receipt=folder/'receipt.json'
 if receipt.exists():
  r=read(receipt);assert r['weightsSHA256']==digest and r['protocolSHA256']==sha(pp) and sha(Path(r['onnxPath']))==r['modelSHA256'];print('FROZEN DETECTOR EXPORT EXISTS');return
 net=yolo_model();net.load_state_dict(load_file(str(weights)));net.eval();model=RawYOLO(net);model.eval();pt=PTSession(model);inputs=[]
 for row in rows:
  assert sha(Path(row['absolutePath']))==row['sha256'];tile=acne_tiles([row],False)[0];x=tile_image(tile)[None].numpy();assert x.shape==(1,3,384,384) and x.dtype==np.float32 and np.isfinite(x).all() and x.min()>=0 and x.max()<=255;inputs.append(x)
 path=folder/'selected.onnx';names=['decoded_boxes','raw_regression','raw_objectness','raw_class']
 if not path.exists():torch.onnx.export(model,torch.from_numpy(inputs[0]),str(path),input_names=['native_bgr_tile'],output_names=names,opset_version=17,dynamo=False)
 options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1;session=ort.InferenceSession(str(path),options,providers=['CPUExecutionProvider']);checks=[];numeric=True
 strides=np.concatenate([np.full((384//s)**2,s,np.float32) for s in [8,16,32]])[None,:,None]
 for row,x in zip(rows,inputs):
  a=pt.run(None,{'native_bgr_tile':x});b=session.run(None,{'native_bgr_tile':x});outputs=[]
  for i,label in enumerate(names):
   passed=bool(np.isfinite(b[i]).all() and np.allclose(a[i],b[i],atol=.003,rtol=.0001))
   if i==0:
    bound=strides*abs(a[1][:,:,:2]-b[1][:,:,:2])+2*abs(np.spacing(a[0][:,:,:2]))+.003
    passed=bool(np.isfinite(b[0]).all() and np.all(abs(a[0][:,:,:2]-b[0][:,:,:2])<=bound) and np.allclose(a[0][:,:,2:],b[0][:,:,2:],atol=.003,rtol=.0001))
   outputs.append(dict(output=label,passed=passed,maximumAbsoluteDifference=float(abs(a[i]-b[i]).max()),strictToleranceUnchanged=True));numeric &= passed
  score=1/(1+np.exp(-np.clip(b[2],-80,80)))*1/(1+np.exp(-np.clip(b[3],-80,80)));score_ok=bool(np.allclose(score,b[0][:,:,4:5]*b[0][:,:,5:6],atol=1e-6));bounds_ok=bool(b[0][:,:,2:4].min()>=.099 and b[0][:,:,2:4].max()<=768.01);numeric &= score_ok and bounds_ok
  checks.append(dict(sha256=row['sha256'],outputs=outputs,objectnessTimesClassMapping=score_ok,boundedDimensions=bounds_ok))
 product=read(base/'positive-product-chain.json')['rows'];adapters=[];saved=M.load
 try:
  for row in product:
   if 'realDerivedLandmarks' not in row:continue
   source=next(r for r in rows if r['sha256']==row['sha256']);image=cv2.imread(source['absolutePath']);values=[]
   for implementation in [pt,session]:
    M.load=lambda implementation=implementation:{'sessions':{'acne':dict(session=implementation,metadata=dict(sha256=sha(path),version='frozen-selected-detector-staging-v1',confidenceThreshold=.7),loadMs=0)}}
    values.append(M.infer_acne(image,row['realDerivedLandmarks'],True))
   valid=all(r.get('valid') for r in values);a,b=[np.asarray(r.get('boxes',[])) for r in values];same=valid and a.shape==b.shape and bool(np.allclose(a,b,atol=.05,rtol=.0002));adapters.append(dict(sha256=source['sha256'],boxCounts=[len(v.get('boxes',[])) for v in values],sourceCoordinateParity=same,maximumDifference=float(abs(a-b).max()) if a.shape==b.shape and a.size else 0,actualProductDecoder=True,physicalCameraAcceptance=False))
 finally:M.load=saved
 record=dict(weightsSHA256=digest,modelSHA256=sha(path),onnxPath=str(path),protocolSHA256=sha(pp),numericalParity=bool(numeric),strictFailureBlocksPromotion=not numeric,realImagePreprocessingParity=True,sourceCoordinateParity=bool(adapters) and all(r['sourceCoordinateParity'] for r in adapters),checks=checks,adapter=adapters,acceptanceThresholdsChanged=False,normalAPIInstalled=False,productAccepted=False,finalOpened=False)
 write('interim-diagnosis/'+name+'/receipt.json',record);write('interim-diagnosis/selected-detector-export-current.json',dict(receiptPath=str(receipt),receiptSHA256=sha(receipt),weightsSHA256=digest,selectionSHA256=sha(base/'frozen-detector-selection.json')))
 print('SELECTED DETECTOR EXPORT',digest,'numericalParity',numeric,'sourceParity',record['sourceCoordinateParity'])
if __name__=='__main__':main()
