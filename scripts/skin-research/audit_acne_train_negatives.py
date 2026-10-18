"""Inspect actual Step-0 TRAIN detections against loss-eligible clean support."""
import argparse,json,math
from pathlib import Path
from acne_takeover_support import ROOT,OUT,read,digest,strict_clean_mask,known_cells
from heavy_job_lease import HeavyJobLease

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--model',choices=['step0','control_iou','candidate_giou'],default='step0');args=parser.parse_args()
    original=read(OUT/'inputs/original-reviewed-detector-data.json');rows={r['sha256']:r for r in original['rows'] if r['split']=='train'}
    cohort=read(OUT/'inputs/controlled_train_cohort.json');allowed=set(cohort['pilotTrainShas']);summary=read(OUT/('evaluation-'+args.model)/'summary.json');assert summary['model']==args.model;records=[]
    support_rows={r['sha256']:r for r in read(OUT/'train-clean-support/manifest.json')['rows']}
    with HeavyJobLease('CDC-acne-train-supervision-audit',peak_mib=1350,minimum_available_mib=1600,memory_metric='private') as lease:
        import cv2,numpy as np
        from PIL import Image,ImageDraw
        old_order=np.arange(len(cohort['pilotTrainTiles']));np.random.RandomState(20261015).shuffle(old_order);old_selected=set(old_order[:600].tolist())
        board=Image.new('RGB',(1000,800),'#222222');draw=ImageDraw.Draw(board);shown=0
        for p in summary['rows']:
            if p['sha256'] not in allowed:continue
            lease.check();s=p['sha256'];r=rows[s];dest=OUT/'product-inputs'/s;image=cv2.imread(str(dest/'snapshot.png')) if (dest/'snapshot.png').exists() else cv2.imread(r['absolutePath']);support=None
            if s in support_rows:
                support_path=OUT/'train-clean-support'/(s+'.png');assert digest(support_path)==support_rows[s]['maskSHA256'];support=cv2.imread(str(support_path),cv2.IMREAD_GRAYSCALE)
            mask,weight=strict_clean_mask(r,image,reviewed_support=support)
            for cand in sorted(p['trace']['nmsCandidates'],key=lambda v:-v['confidence']):
                x,y,ex,ey=cand['box'];a=max(0,int(math.floor(x)));b=max(0,int(math.floor(y)));c=min(image.shape[1],int(math.ceil(ex)));d=min(image.shape[0],int(math.ceil(ey)));patch=mask[b:d,a:c]
                if not patch.size or patch.mean()<.8:continue
                kt,wt=known_cells(mask,weight,cand['rect']);index=cand['anchor'];cx=(x+ex)/2;cy=(y+ey)/2;exposures=[]
                offset=index;stride=None
                for candidate_stride in (4,8,16,32):
                    count=(384//candidate_stride)**2
                    if offset<count:stride=candidate_stride;break
                    offset-=count
                assert stride is not None
                side=384//stride;emitter_x=cand['rect'][0]+(offset%side+.5)*stride;emitter_y=cand['rect'][1]+(offset//side+.5)*stride
                for ti,tile in enumerate(cohort['pilotTrainTiles']):
                    if tile['imageSha256']!=s:continue
                    ta,tb,tc,td=tile['rect']
                    if ta<=emitter_x<tc and tb<=emitter_y<td:
                        # Same head/stride and actual supervised emitter location;
                        # a decoded box center is not the loss-mask anchor center.
                        px=int(ta+(max(0,min(side-1,round((emitter_x-ta)/stride-.5)))+.5)*stride);py=int(tb+(max(0,min(side-1,round((emitter_y-tb)/stride-.5)))+.5)*stride)
                        known=bool(0<=px<mask.shape[1] and 0<=py<mask.shape[0] and mask[py,px])
                        exposures.append(dict(tileIndex=ti,rect=tile['rect'],sourceAnchor=[px,py],known=known,selectedInOld150=ti in old_selected))
                record=dict(model=args.model,sha256=s,group=r['group'],split='train',box=cand['box'],confidence=cand['confidence'],productTileRect=cand['rect'],productAnchor=index,emittingStride=stride,emittingSourceAnchor=[emitter_x,emitter_y],decodedSourceCenter=[cx,cy],knownAtProductGridAnchor=bool(kt[index]),boundaryWeight=float(wt[index]),actualTrainExposures=exposures,knownAtTrainingAnchor=any(e['known'] and e['selectedInOld150'] for e in exposures),cleanBoxAreaFraction=float(patch.mean()),explicitNegativeReview=bool(r.get('negativeROI')),originalPositiveOverlap=False)
                assert not r.get('annotations') and r.get('negativeROI');records.append(record)
                if shown<12:
                    cx=(x+ex)/2;cy=(y+ey)/2;im=Image.fromarray(image[:,:,::-1]);crop=im.crop((int(cx-40),int(cy-40),int(cx+40),int(cy+40))).resize((200,200));left=(shown%4)*250;top=(shown//4)*265;board.paste(crop,(left,top+25));draw.rectangle((left+100+(x-cx)*2.5,top+125+(y-cy)*2.5,left+100+(ex-cx)*2.5,top+125+(ey-cy)*2.5),outline='red',width=2);draw.text((left,top),s[:8]+' '+str(round(cand['confidence'],3)),fill='white');draw.text((left,top+230),'known='+str(bool(kt[index]))+' weight='+str(round(float(wt[index]),2)),fill='white');shown+=1
        board.save(OUT/('train-hard-negative-board-'+args.model+'.png'))
        reason='No confidence>=.30 decoded boxes with >=80% verified-clean TRAIN support' if not records else 'Verified-clean high-score candidates already supervised' if all(r['knownAtTrainingAnchor'] for r in records) else 'Some proposal anchors are UNKNOWN; inspect exact holes/borders before changing supervision'
        report=dict(model=args.model,trainOnly=True,heldoutOrScopeBUsedForMining=False,verifiedCleanFalseCandidates=len(records),knownAtTrainingAnchor=sum(r['knownAtTrainingAnchor'] for r in records),records=records,visualReview='PENDING',resource=lease.receipt(),rootCause=reason)
        (OUT/('train-negative-audit-'+args.model+'.json')).write_text(json.dumps(report,indent=2),'utf8')
        (OUT/'train-negative-audit.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps({k:v for k,v in report.items() if k not in ['records','resource']}))

if __name__=='__main__':main()
