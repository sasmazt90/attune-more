"""Bounded parity on actual browser requests; no fit, calibration or model choice."""
import ast,sys,subprocess,json,math,hashlib,time,os
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT.parent;OUT=BASE/'cdc-progress/acne-v5-integration-20261017';FROZEN='cb0948fa2ebc98eb69d22d1b7079752b69ae6cfb'
sys.path[:0]=[str(ROOT/'services/core-api'),str(ROOT/'scripts/skin-research'),str(ROOT/'.runtime/export-frozen-source')]
from heavy_job_lease import HeavyJobLease

def frozen_module(path,names,namespace):
 source=subprocess.check_output(['git','show',FROZEN+':'+path],cwd=ROOT).decode('utf8');tree=ast.parse(source);nodes=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in names];assert len(nodes)==len(names)
 exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),path,'exec'),namespace);return namespace

def main():
 import cv2,torch
 from safetensors.torch import load_file
 from yolox_p2 import build_yolox_p2_model
 from acne_box_support_staging import principled_accepted_boxes
 protocol=json.loads((OUT/'protocol.json').read_text());tol=protocol['tolerances'];checks=[]
 with HeavyJobLease('CDC-acne-v5-real-browser-request-parity',peak_mib=1700,minimum_available_mib=1600,memory_metric='private') as lease:
  torch.set_num_threads(2);net=build_yolox_p2_model();weights=BASE/'attune-live-test/audit-results/acne-takeover-20261015/models/step0.safetensors';assert hashlib.sha256(weights.read_bytes()).hexdigest()==protocol['step0SHA256'];net.load_state_dict(load_file(str(weights)),strict=True);net.eval()
  functions=frozen_module('scripts/skin-research/acne_takeover_support.py',['infer_tiles','current_product_masks','tile_rectangles'],dict(np=np,ast=ast,Path=Path))
  feat=frozen_module('scripts/skin-research/acne_candidate_verifier.py',['level_features','candidate_features','Verifier'],dict(np=np,math=math,Path=Path,json=json,STRIDES=(4,8,16,32),CTX=2,VERSION='acne-candidate-verifier-features-v1'))
  verifier=feat['Verifier'](ROOT/'services/core-api/models/acne-v5-preview/verifier-v5.json')
  for source in ['front','right']:
   f=ROOT/'output/playwright'/f'{source}-browser-api.json';entry=json.loads(f.read_text('utf8'));pl=entry['payload'];api=entry['response'];rt=api['validationTrace'];from appearance_analysis import decode_photo
   bgr,identity=decode_photo(pl['photo']);assert identity==api['photoId']==pl['photoId'];rects=functions['tile_rectangles'](bgr,pl['landmarks']);assert rects==rt['rects'];maps=[]
   h=net.backbone.register_forward_hook(lambda m,i,o:maps.append([t[0].detach().numpy().copy() for t in o]));started=time.perf_counter()
   try:raw,trace=functions['infer_tiles'](net,bgr,rects,lease.check)
   finally:h.remove()
   masks=functions['current_product_masks'](pl);assigned,rejected=principled_accepted_boxes(raw,masks['acne_envelopes'],masks['acne_skin'],masks['hair'],masks['acne_exclusion'],identity,masks['scale'],masks['origin'],visible_regions=list(pl['meshes']),landmarks=pl['landmarks'],source_shape=bgr.shape[:2],bgr=bgr)
   final=[b for rows in assigned.values() for b in rows];lookup={tuple(round(x,4) for x in v['box'])+(round(v['confidence'],6),):v for v in trace['confidenceCandidates']};features=[];ids=[]
   for b in final:
    xy=[b['x'],b['y'],b['x']+b['width'],b['y']+b['height']];m=lookup[tuple(round(x,4) for x in xy)+(round(b['confidence'],6),)];a,y=rects[m['tile']][:2];features.append(feat['candidate_features'](maps[m['tile']],(xy[0]+xy[2])/2-a,(xy[1]+xy[3])/2-y));ids.append([m['tile'],m['anchor']])
   X=np.stack(features) if features else np.zeros((0,1920),np.float32);Y=np.asarray(rt['features'],np.float32).reshape(-1,1920);prob=verifier.proba(X);keep=verifier.keep(X);nmsids=[[v['tile'],v['anchor']] for v in trace['nmsCandidates']];apiids=[[v['tile'],v['anchor']] for v in rt['identities']];boxes=np.asarray(raw);other=np.asarray(rt['nms'])
   counts=len(raw)==len(rt['nms']) and len(final)==len(rt['preVerifier']);sameids=ids==apiids and nmsids==[[v['tile'],v['anchor']] for v in rt['nmsMetadata']]
   coords=counts and np.allclose(boxes[:,:4],other[:,:4],atol=tol['sourceBoxesATol'],rtol=0);scores=counts and np.allclose(boxes[:,4],other[:,4],atol=tol['scoreATol'],rtol=0);featuresok=X.shape==Y.shape and np.allclose(X,Y,atol=tol['tensorsATol'],rtol=tol['tensorsRTol']);probok=len(prob)==len(rt['probabilities']) and np.allclose(prob,rt['probabilities'],atol=tol['verifierProbabilityATol'],rtol=0);decisions=np.array_equal(keep,rt['keep']);dom=entry['browser'];display=len(dom['points'])==int(keep.sum())==api['candidateCount'] and dom['dataset']['requestId']==api['requestId'] and dom['dataset']['photoId']==identity
   np.savez_compressed(OUT/f'{source}-parity-arrays.npz',reference=X,runtime=Y,referenceProb=prob,runtimeProb=rt['probabilities']);delta=((X.astype(np.float64)-Y.astype(np.float64))/verifier.scale)*verifier.coef;worst=np.unravel_index(np.abs(delta).argmax(),delta.shape) if delta.size else None;print('FEATURE_DIAGNOSTIC',worst,dict(contribution=float(delta[worst]),reference=float(X[worst]),runtime=float(Y[worst]),scale=float(verifier.scale[worst[1]]),coef=float(verifier.coef[worst[1]])) if worst else {},flush=True)
   accepted=[b for b,k in zip(rt['preVerifier'],rt['keep']) if k];centres=[[(b['x']+b['width']/2),(b['y']+b['height']/2)] for b in accepted];render=np.array([[b['x'],b['y']] for b in dom['points']]);display=display and np.allclose(render,np.asarray(centres),atol=1e-8,rtol=0)
   row=dict(source=source,requestId=api['requestId'],photoId=identity,pose=pl['pose'],tiles=len(rects),detectorForwards=api['detectorForwardCount'],nms=len(raw),filtered=len(final),kept=int(keep.sum()),exactTileAnchors=sameids,countsExact=counts,sourceCoordinatesPassed=bool(coords),scorePassed=bool(scores),featuresPassed=bool(featuresok),verifierProbabilityPassed=bool(probok),decisionsExact=bool(decisions),browserPointsSameRequest=bool(display),maxBoxAbs=float(np.max(np.abs(boxes[:,:4]-other[:,:4]))),maxScoreAbs=float(np.max(np.abs(boxes[:,4]-other[:,4]))),maxFeatureAbs=float(np.max(np.abs(X-Y))) if X.shape==Y.shape and X.size else None,maxVerifierAbs=float(np.max(np.abs(prob-rt['probabilities']))) if len(prob) else None,referenceSeconds=time.perf_counter()-started,externalRequests=dom['external'],localStorageKeys=dom['storage'],runtimeTiming=api['timing'],runtimeResources=api['resources'],photoToVisibleMs=float(dom['dataset']['visibleMs']))
   row['passed']=all([counts,sameids,coords,scores,featuresok,probok,decisions,display,api['detectorForwardCount']==len(rects)]);checks.append(row);print(json.dumps(row),flush=True)
   temp=OUT/'parity-results.tmp';temp.write_text(json.dumps(dict(checks=checks,tolerances=tol,resource=lease.receipt(),noTraining=True),indent=2));temp.replace(OUT/'parity-results.json');assert row['passed'],'BOUNDED_RUNTIME_PARITY_FAILED';del maps,X,Y
if __name__=='__main__':main()
