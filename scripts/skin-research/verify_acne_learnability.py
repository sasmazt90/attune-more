"""Focused feature-graph/checkpoint checks and inference-only prior-arm TRAIN replay."""
import gc
import importlib.util
import json
import random
import unittest
from pathlib import Path
from acne_takeover_support import ROOT,OUT,read,digest,one_to_one
from heavy_job_lease import HeavyJobLease

DEST=OUT.parent/'acne-learnability-20261015'


def tuples(value):return tuple(tuples(v) for v in value) if isinstance(value,list) else value


def main():
    receipt=read(DEST/'receipt.json');plan=read(DEST/'preregistration.json');pointer=read(DEST/'CURRENT');folder=DEST/pointer['directory'];assert folder.resolve().is_relative_to(DEST.resolve())
    for name,expected in pointer['hashes'].items():assert digest(folder/name)==expected
    assert digest(DEST/'model.safetensors')==receipt['modelSHA256']
    with HeavyJobLease('CDC-acne-learnability-verification',peak_mib=1350,minimum_available_mib=1600,memory_metric='private') as lease:
        import cv2
        import numpy as np
        import torch
        from safetensors.torch import load_file
        from yolox_p2 import build_yolox_p2_model
        from acne_objectness_features import build_feature_model,install_objectness_features,frozen_hash,VERSION
        from acne_object_negatives import reviewed_object_negative_mask
        from skin_models import _nms
        torch.set_num_threads(4)
        suite=unittest.TestSuite()
        for filename in ('test_acne_objectness_features.py','test_acne_object_negative_scope.py','test_acne_clean_supervision.py','test_acne_staging_support.py'):
            spec=importlib.util.spec_from_file_location(filename[:-3],ROOT/'tests/unit'/filename);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))
        result=unittest.TextTestRunner(verbosity=1).run(suite);assert result.wasSuccessful();gc.collect()
        candidate=build_feature_model();candidate.load_state_dict(load_file(str(folder/'model.safetensors')),strict=True);assert receipt['graphVersion']==VERSION;assert frozen_hash(candidate,receipt['trainable'])==receipt['frozenSHA256']
        initial=build_yolox_p2_model();initial.load_state_dict(load_file(str(OUT/'models/step0.safetensors')),strict=True);install_objectness_features(initial)
        changed=[]
        for name,tensor in candidate.state_dict().items():
            delta=float((tensor-initial.state_dict()[name]).abs().max())
            if delta:changed.append(dict(name=name,maxAbsDelta=delta));assert name in receipt['trainable']
        opt=torch.optim.AdamW([p for n,p in candidate.named_parameters() if n in receipt['trainable']],lr=plan['learningRate']);sched=torch.optim.lr_scheduler.LambdaLR(opt,lambda step:1.)
        state=read(folder/'state.json');tensors=load_file(str(folder/'optimizer-rng.safetensors'));opt.load_state_dict(dict(state={int(i):{k:tensors[v['tensor']] if isinstance(v,dict) and 'tensor' in v else v for k,v in values.items()} for i,values in state['optimizerState'].items()},param_groups=state['paramGroups']));sched.load_state_dict(state['scheduler'])
        assert len(opt.state)==16 and sched.last_epoch==150
        for p,values in opt.state.items():assert values['exp_avg'].shape==values['exp_avg_sq'].shape==p.shape and float(values['step'])==150
        torch.set_rng_state(tensors['torch_rng']);random.setstate(tuples(state['pythonRNG']));rng=state['numpyRNG'];np.random.set_state((rng[0],np.array(rng[1],np.uint32),*rng[2:]));assert torch.equal(torch.get_rng_state(),tensors['torch_rng'])
        del candidate,initial,opt,sched,tensors;gc.collect()
        old_path=OUT/'clean-pilot-hard-negative/model.safetensors';assert digest(old_path)==plan['previousReferenceModelSHA256'];old=build_yolox_p2_model();old.load_state_dict(load_file(str(old_path)),strict=True);old.eval()
        components=read(OUT/'source-negative-repair-probe.json')['components'];sequence=read(OUT/'clean-pilot-hard-negative/sequence.json');rows=[next(r for r in sequence if r['sha256']==c['sha256'] and r['rect']==c['selectedTile']['rect']) for c in components]+plan['positiveProbes'];original={r['sha256']:r for r in read(OUT/'inputs/original-reviewed-detector-data.json')['rows'] if r['split']=='train'}
        objects=[];positive=[]
        with torch.inference_mode():
            for index,row in enumerate(rows):
                lease.check();path=Path(original[row['sha256']]['absolutePath']);assert digest(path)==row['sha256'];image=cv2.imread(str(path));a,b,c,d=row['rect'];tile=np.full((384,384,3),114,np.uint8);patch=image[b:d,a:c];tile[:patch.shape[0],:patch.shape[1]]=patch;pred=old(torch.from_numpy(tile.transpose(2,0,1).copy()).float()[None])[0];score=pred[:,4]*pred[:,5]
                if index<5:
                    item=components[index];x,y,ex,ey=item['box'];mask=reviewed_object_negative_mask(pred[:,:4],torch.tensor([[x-a,y-b,ex-a,ey-b]]),torch.tensor(row['protectedBoxes']).reshape(-1,4))[:,0];ids=torch.where(mask)[0];best=int(ids[score[ids].argmax()]);objects.append(dict(sourceAnnotationId=item['sourceAnnotationId'],objectness=float(pred[best,4]),classProbability=float(pred[best,5]),objTimesCls=float(score[best]),aboveThresholdAnchors=int((score[ids]>=.30).sum())))
                boxes=[]
                for cx,cy,w,h,obj,cls in pred[score>=.30].tolist():
                    box=[max(0,cx-w/2),max(0,cy-h/2),min(c-a,cx+w/2),min(d-b,cy+h/2),obj*cls]
                    if box[2]>box[0] and box[3]>box[1]:boxes.append(box)
                final=_nms(boxes,threshold=.30) if boxes else [];pairs=one_to_one(row['boxes'],[v[:4] for v in final]);positive.append(dict(sha256=row['sha256'],tile=row['rect'],targets=len(row['boxes']),pairs=pairs))
        payload=dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),strictFeatureGraphLoad=True,changedTensors=changed,allOtherStateAndBNUnchanged=True,optimizerSchedulerAndRNGLoadVerified=True,previousArmReplay=dict(optimizerUpdates=0,modelSHA256=digest(old_path),objects=objects,positiveProbeTiles=positive,positiveTargets=sum(r['targets'] for r in positive),positiveMatched=sum(len(r['pairs']) for r in positive)),resource=lease.receipt())
    (DEST/'verification.json').write_text(json.dumps(payload,indent=2),encoding='utf8');print(json.dumps({k:v for k,v in payload.items() if k not in ['previousArmReplay','resource','changedTensors']}))


if __name__=='__main__':main()
