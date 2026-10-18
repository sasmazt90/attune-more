"""Export/evaluate a completed early-stopped run; never resumes or tunes it."""
import hashlib,json,time
import numpy as np
import torch
import train_dental_yolox as training
from collections import defaultdict


def main():
    out=training.OUT;root=training.ROOT
    decision=json.loads((out/'early-stopping-decision.json').read_text('utf8'))
    assert decision['reason']=='VALIDATION_PLATEAU' and not decision['heldoutEvaluated']
    assert hashlib.sha256((out/'best-weights.npz').read_bytes()).hexdigest()==decision['bestWeightsSHA256']
    assert hashlib.sha256((out/'training-history.json').read_bytes()).hexdigest()==decision['trainingHistorySHA256']
    assert not (out/'heldout-predictions.json').exists(), 'Do not silently repeat final model selection/evaluation'
    history=json.loads((out/'training-history.json').read_text('utf8'))
    selected=max(history,key=lambda row:row['validation']['macroF1'])
    threshold=selected['validation']['threshold'];torch.set_num_threads(2);started=time.monotonic()
    inventory=json.loads((out/'dataset-split.json').read_text('utf8'));classes=inventory['classes']
    test=[row for row in inventory['rows'] if row['split']=='test']
    for row in test:assert hashlib.sha256(training.Path(row['path']).read_bytes()).hexdigest()==row['sha256']
    model=training.YOLOX(training.YOLOPAFPN(depth=.33,width=.50),training.YOLOXHead(len(classes),width=.50))
    with np.load(out/'best-weights.npz',allow_pickle=False) as archive:model.load_state_dict({key:torch.from_numpy(archive[key]) for key in archive.files})
    model.eval();predictions=training.predict(model,test,320,len(classes))
    evaluation=training.metrics(test,predictions,threshold,len(classes));evaluation['mAP50']=evaluation.pop('mAP')
    evaluation['mAP50_95']=float(np.mean([training.metrics(test,predictions,threshold,len(classes),overlap)['mAP'] for overlap in np.arange(.5,.96,.05)]))
    evaluation.update(images=len(test),patientIndependent=False,negatives='Unannotated images excluded; no healthy-specificity claim')
    groups=defaultdict(list)
    for i,item in enumerate(test):groups[item['group']].append(i)
    counts=[]
    for indices in groups.values():
        total=np.zeros((len(classes),3),dtype=np.int64)
        for i in indices:
            item_metrics=training.metrics([test[i]],[predictions[i]],threshold,len(classes))
            total+=np.array([[c['truePositive'],c['falsePositive'],c['falseNegative']] for c in item_metrics['classes']])
        counts.append(total)
    counts=np.asarray(counts);rng=np.random.default_rng(8102026);bootstrap=[]
    for _ in range(200):
        sampled=counts[rng.integers(0,len(counts),len(counts))].sum(axis=0)
        bootstrap.append((2*sampled[:,0]/np.maximum(2*sampled[:,0]+sampled[:,1]+sampled[:,2],1)).tolist())
    evaluation['groupBootstrapF1_95CI']=np.quantile(np.mean(bootstrap,axis=1),[.025,.975]).tolist()
    evaluation['classGroupBootstrapF1_95CI']=np.quantile(bootstrap,[.025,.975],axis=0).T.tolist()
    destination=root/'services/core-api/models';path=destination/'dental-yolox-s.onnx'
    example=training.image_tensor(test[0],320)[0][None]
    torch.onnx.export(model,example,str(path),input_names=['images'],output_names=['detections'],opset_version=17,dynamo=False)
    import onnx,onnxruntime as ort
    onnx.checker.check_model(str(path));options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1
    session=ort.InferenceSession(str(path),sess_options=options,providers=['CPUExecutionProvider']);errors=[]
    for item in test[:10]:
        x=training.image_tensor(item,320)[0][None]
        with torch.no_grad():expected=model(x).numpy()
        actual=session.run(None,{'images':x.numpy()})[0];errors.append(float(np.max(np.abs(actual-expected))))
        assert np.allclose(actual,expected,rtol=.002,atol=.005),'ONNX_EQUIVALENCE_FAILED'
    source=json.loads((out.parent/'source-manifest.json').read_text('utf8'))
    result=dict(modelVersion='yolox-s-dental-from-scratch-v1',modelHash=hashlib.sha256(path.read_bytes()).hexdigest(),
        inputSize=320,confidenceThreshold=threshold,classes=classes,codeRevision=training.REV,codeLicense='Apache-2.0',
        startupWeights='none; random initialization',weightsLicense='Project-created; existing repository ownership policy; source data CC-BY-4.0 attribution retained',
        dataset=source,evaluation=evaluation,onnxMaxAbsoluteErrors=errors,epochs=len(history),selectedEpoch=selected['epoch'],
        trainingStop=decision,finalizationSeconds=time.monotonic()-started,clinicalValidation=False,batchSize=2,torchCPUThreads=2,
        splitVersion=inventory['splitVersion'])
    (destination/'dental-yolox-s.json').write_text(json.dumps(result,indent=2),'utf8')
    (out/'heldout-predictions.json').write_text(json.dumps(predictions),'utf8')
    print('DELIVERABLE '+json.dumps(result),flush=True)


if __name__=='__main__':main()
