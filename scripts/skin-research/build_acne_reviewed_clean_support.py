"""Conservative TRAIN negative support, grounded in explicit existing review.

Anatomical/quality/eyewear masks refine an already-reviewed negative photo;
they never turn an unreviewed positive/UNKNOWN photo into healthy truth.
"""
import base64,hashlib,json
from pathlib import Path
from acne_takeover_support import ROOT,OUT,read,digest,current_product_masks
from heavy_job_lease import HeavyJobLease

def main():
    dest=OUT/'train-clean-support';dest.mkdir(exist_ok=True);original=read(OUT/'inputs/original-reviewed-detector-data.json');rows={r['sha256']:r for r in original['rows'] if r['split']=='train'};cohort=read(OUT/'inputs/controlled_train_cohort.json');allowed=set(cohort['pilotTrainShas']);pre={r['sha256']:r for r in read(OUT/'browser-preflight.json')['rows']};evaluated={r['sha256']:r for r in read(OUT/'evaluation-step0/summary.json')['rows']};result=[]
    with HeavyJobLease('CDC-acne-reviewed-anatomical-clean-support',peak_mib=1350,minimum_available_mib=1600,memory_metric='private') as lease:
        import cv2,numpy as np
        for s in sorted(allowed):
            r=rows[s]
            if r.get('annotations') or not r.get('negativeROI'):continue
            lease.check();a=pre[s];e=evaluated[s];h,w=r['height'],r['width'];support=np.zeros((h,w),np.uint8);reason='CAPTURE_OR_EYEWEAR_NOT_ADMISSIBLE'
            if e['fullStaticProductPass'] and a.get('snapshot'):
                p=OUT/'product-inputs'/s/'snapshot.png';image=cv2.imread(str(p));assert image.shape[:2]==(h,w);pixel_id=hashlib.sha256(cv2.cvtColor(image,cv2.COLOR_BGR2RGBA).tobytes()).hexdigest();snap=a['snapshot'];payload=dict(photo='data:image/png;base64,'+base64.b64encode(p.read_bytes()).decode(),photoId=pixel_id,landmarks=a['alignment']['landmarks'],meshes=snap['meshes'],exclusions=snap['exclusions'],qualityValid=True)
                m=current_product_masks(payload)
                # Chin beard/white stubble in the old whole-face review is
                # not asserted to be clean skin. Remaining support comes from
                # the actual visible product envelopes, holes/hair/exposure.
                regions=[v for k,v in m['acne_envelopes'].items() if k!='chin']
                if regions:
                    safe=np.logical_or.reduce(regions)&m['acne_skin'];safe=cv2.erode(safe.astype(np.uint8),np.ones((3,3),np.uint8))
                    xx=np.floor((np.arange(w)+.5-m['origin'][0])*m['scale']).astype(int);yy=np.floor((np.arange(h)+.5-m['origin'][1])*m['scale']).astype(int);inside=(yy[:,None]>=0)&(yy[:,None]<safe.shape[0])&(xx[None,:]>=0)&(xx[None,:]<safe.shape[1]);support=(safe[yy.clip(0,safe.shape[0]-1)[:,None],xx.clip(0,safe.shape[1]-1)[None,:]]*inside).astype(np.uint8);reason='EXPLICIT_NEGATIVE_REVIEW_INTERSECT_CURRENT_VISIBLE_SKIN_NONCHIN'
            path=dest/(s+'.png');cv2.imwrite(str(path),support*255);result.append(dict(sha256=s,group=r['group'],split='train',maskSHA256=digest(path),sourceSize=[w,h],knownPixels=int(support.sum()),reason=reason))
        report=dict(version='explicit-reviewed-current-visible-skin-nonchin-v2',trainOnly=True,partialPositivePhotosNeverMadeNegative=True,regions='current visible forehead/nose/cheeks; chin and non-skin UNKNOWN',source='explicit original criterion-specific negative review intersect actual product support; not pseudo labels',rows=result,resource=lease.receipt());(dest/'manifest.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(dict(photos=len(result),withSupport=sum(r['knownPixels']>0 for r in result),pixels=sum(r['knownPixels'] for r in result))),flush=True)

if __name__=='__main__':main()
