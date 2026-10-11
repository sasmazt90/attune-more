"""Export exact selected weights; train-only confidence calibration, sealed test.

Development confidence precision remains development evidence. This exporter
does not install a rejected candidate or write the production manifest.
"""
import json,time
from pathlib import Path
import numpy as np,torch,onnxruntime as ort
from scipy.optimize import minimize_scalar
from scipy.special import softmax
from safetensors.torch import load_file
from expanded_sources import OUT,PREVIOUS,write,sha
from train_focused_type import model,image,scores,CLASSES
from skin_acceptance import decide

def main():
 torch.set_num_threads(1);folder=OUT/'type';selection=json.loads((folder/'selection.json').read_text('utf8'));assert selection['trainingComplete']
 weights=folder/'selected.safetensors';assert sha(weights)==selection['weightsSHA256'];net=model('efficientnet_b0');net.load_state_dict(load_file(str(weights)));net.eval()
 source=PREVIOUS.parent/'skin-followup-20261011/development-manifest-v2.json';rows=[r for r in json.loads(source.read_text('utf8'))['rows'] if r.get('typeEligible') and r['split'] in ['train','validation']];tr=[r for r in rows if r['split']=='train'];va=[r for r in rows if r['split']=='validation']
 def logits(rs):
  values=[]
  with torch.inference_mode():
   for start in range(0,len(rs),8):values.append(net(torch.stack([image(r) for r in rs[start:start+8]])).numpy())
  return np.concatenate(values)
 training=logits(tr);validation=logits(va);truth=np.array([CLASSES.index(r['class']) for r in tr]);vtruth=np.array([CLASSES.index(r['class']) for r in va]);frozen=np.load(folder/'validation-logits.npy');assert np.allclose(validation,frozen,atol=1e-5,rtol=1e-5),'SELECTED_WEIGHT_METRIC_MISMATCH'
 def objective(t):
  p=softmax(training/t,axis=1);return float(-np.log(np.maximum(p[np.arange(len(tr)),truth],1e-12)).mean())
 temperature=float(minimize_scalar(objective,bounds=(.1,10.),method='bounded').x);prob=softmax(training/temperature,axis=1);confidence=prob.max(1);correct=prob.argmax(1)==truth
 thresholds=[t for t in np.linspace(.25,.95,71) if (confidence>=t).sum()>=10 and correct[confidence>=t].mean()>=.7];threshold=float(min(thresholds)) if thresholds else None
 vp=softmax(validation/temperature,axis=1);selected=vp.max(1)>=threshold if threshold is not None else np.zeros(len(va),bool);metrics=scores(vtruth,validation);metrics.update(scope='source-group-development',confidenceSupport=int(selected.sum()),confidencePrecision=float((vp.argmax(1)[selected]==vtruth[selected]).mean()) if selected.any() else None)
 path=folder/'candidate.onnx';sample=image(va[0])[None]
 torch.onnx.export(net,sample,str(path),input_names=['rgb'],output_names=['logits'],opset_version=17,dynamo=False)
 options=ort.SessionOptions();options.intra_op_num_threads=1;options.inter_op_num_threads=1;session=ort.InferenceSession(str(path),options,providers=['CPUExecutionProvider']);parity=[]
 for r in va[:8]:
  x=image(r)[None].numpy();actual=session.run(None,{'rgb':x})[0]
  with torch.inference_mode():expected=net(torch.from_numpy(x)).numpy()
  delta=float(np.max(np.abs(actual-expected)));assert np.allclose(actual,expected,atol=1e-4,rtol=1e-4);parity.append(dict(sha256=r['sha256'],sourceCrop=r['crop'],maxAbsoluteLogitDifference=delta,nativeSourceDimensions=[r['width'],r['height']]))
 export=dict(sha256=sha(path),numericalParity=True,realImagePreprocessingParity=True,sourceCoordinateParity=True,realSourceRows=parity,scope='offline declared source crop/RGB224/ImageNet parity; normal API not staged')
 data=dict(sourceReviewComplete=False,rightsReviewComplete=False,labelSemanticsMatched=False,splitRelationsResolved=True,unusedHoldout=False,naturalCameraDomainReviewed=False,engineeringLabelsDisclosed=True)
 evidence=dict(data=data,metrics=metrics,export=export,product={},calibration=dict(temperature=temperature,confidenceThreshold=threshold,fittedOn='training only',validationUsedForFit=False,oldTestOpened=False,independentFinal=False))
 write('type/final-evidence.json',evidence);decision=decide('type',evidence);write('type/acceptance.json',decision);print(json.dumps(dict(selection=selection['selectedEpoch'],epochs=selection['epochsCompleted'],macroF1=metrics['macroF1'],confidenceSupport=metrics['confidenceSupport'],confidencePrecision=metrics['confidencePrecision'],onnxSHA256=export['sha256'],decision=decision)),flush=True)

if __name__=='__main__':main()
