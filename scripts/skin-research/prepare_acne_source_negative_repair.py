"""Review-pinned source-category supervision repair; TRAIN-only Step-0 probe."""
import gc,json,math
from pathlib import Path
from acne_takeover_support import ROOT,OUT,read,digest,infer_tiles
from heavy_job_lease import HeavyJobLease

def main():
    review=read(OUT/'train-mole-label-review.json');assert review['reviewStatus']=='REVIEWED'
    data=read(OUT/'inputs/original-reviewed-detector-data.json');rows={r['sha256']:r for r in data['rows'] if r['split']=='train'};cohort=read(OUT/'inputs/controlled_train_cohort.json');allowed=set(cohort['pilotTrainShas']);components=review['selected'];result=[]
    curated={r['sha256']:r for r in read(OUT/'inputs/train-data-engineering-reviewed-20261013.json')['rows'] if r['split']=='train'}
    with HeavyJobLease('CDC-acne-source-negative-repair-probe',peak_mib=1350,minimum_available_mib=1600,memory_metric='private') as lease:
        import cv2,numpy as np,torch
        from safetensors.torch import load_file
        from yolox_p2 import build_yolox_p2_model
        from acne_object_negatives import reviewed_object_negative_mask
        torch.set_num_threads(4);path=OUT/'models/step0.safetensors';net=build_yolox_p2_model();net.load_state_dict(load_file(str(path)),strict=True);net.eval()
        for component in components:
            lease.check();s=component['sha256'];assert s in allowed and s in rows;r=rows[s];p=Path(r['absolutePath']);assert digest(p)==s;image=cv2.imread(str(p));x,y,ex,ey=component['box'];a,b,c,d=r['crop'];xs=sorted(set([*range(a,max(a+1,c-384+1),288),max(a,c-384)]));ys=sorted(set([*range(b,max(b+1,d-384+1),288),max(b,d-384)]));rects=[[u,v,min(c,u+384),min(d,v+384)] for u in xs for v in ys if u<=x and v<=y and u+384>=ex and v+384>=ey]
            all_raw=[];choices=[];overridden={z.get('sourceId') for item in components if item['sha256']==s for z in item['contradictedPseudo']}
            for rect in rects:
                ta,tb,tc,td=rect;tile=np.full((384,384,3),114,np.uint8);patch=image[tb:td,ta:tc];tile[:patch.shape[0],:patch.shape[1]]=patch
                with torch.no_grad():pred=net(torch.from_numpy(tile.transpose(2,0,1).copy()).float()[None])[0]
                protected_source=r['annotations']+[z for z in curated[s].get('annotations',[]) if z.get('reviewStatus')=='engineering_review' and z.get('sourceId') not in overridden]
                neg=torch.tensor([[x-ta,y-tb,ex-ta,ey-tb]],dtype=torch.float32);protected=torch.tensor([[z['box'][0]-ta-16,z['box'][1]-tb-16,z['box'][2]-ta+16,z['box'][3]-tb+16] for z in protected_source],dtype=torch.float32).reshape(-1,4);mask=reviewed_object_negative_mask(pred[:,:4],neg,protected)[:,0];scores=pred[:,4]*pred[:,5];hits=torch.where(mask&(scores>=.30))[0]
                best=max([float(scores[i]) for i in hits],default=0);listed=any(t['imageSha256']==s and t['rect']==rect for t in cohort['pilotTrainTiles']);choices.append(dict(rect=rect,matchingAnchors=int(mask.sum()),aboveThresholdAnchors=len(hits),maxConfidence=best,oldTrainingTileListed=listed))
            best=max(choices,key=lambda z:z['maxConfidence'],default=None)
            result.append(dict(**component,choices=choices,selectedTile=best,sourceFileSHA256=digest(p),sourceAnnotationsSHA256=digest(Path(component['sourceAnnotationPath'])),labelTask='publisher Mole object is non-Pimple, not healthy-skin or segmentation truth',overriddenPseudoSourceIds=sorted(overridden)))
            print(json.dumps(dict(sha=s[:8],sourceAnnotationId=component['sourceAnnotationId'],best=best)),flush=True)
        report=dict(version='reviewed-source-Mole-object-negative-repair-v3',trainOnly=True,modelSHA256=digest(path),components=result,eligibleComponents=sum(bool(r['selectedTile'] and r['selectedTile']['aboveThresholdAnchors']) for r in result),heldoutOrScopeBUsedForMining=False,matchingRule='IoU>=.50 OR >=90% predicted-box containment with area ratio>=.25; no intersection with any original Pimple+16px',resource=lease.receipt());(OUT/'source-negative-repair-probe.json').write_text(json.dumps(report,indent=2),'utf8')

if __name__=='__main__':main()
