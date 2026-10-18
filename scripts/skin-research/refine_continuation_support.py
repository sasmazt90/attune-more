"""Remove observed non-skin support; never create new negative pixel labels.

The active ledger remains immutable. Native tensors are copied to a distinct
version and all differences are monotone support exclusions. Whole ROI expert
and hair-boundary review still remain separate acceptance requirements.
"""
import collections,json,sys
from pathlib import Path
import cv2,numpy as np
from expanded_sources import ROOT,OUT,PREVIOUS,sha,write
sys.path.insert(0,str(ROOT/'services/core-api'))
from appearance_analysis import elongated_dark_mask

def main():
 output=OUT/'continuation-valid-skin-data.json'
 if output.exists():print('Existing refined support ledger preserved');return
 oldpath=OUT/'continuation-mask-data.json';data=json.loads(oldpath.read_text('utf8'));sources=json.loads((PREVIOUS/'review/candidates.json').read_text('utf8'))['rows'];by={r['sha256']:r for r in sources};folder=OUT/'continuation-valid-skin/tensors';folder.mkdir(parents=True,exist_ok=True);cached={};totals=collections.Counter();rows=[]
 for r in data['rows']:
  source=OUT/'continuation-mask/tensors'/r['id'];dest=folder/r['id']
  with np.load(source) as v:rgb=v['rgb'].copy();truth=v['truth'].copy();support=v['support'].copy()
  prior=support.copy();positive_before=int(truth.sum());reason='PARTIAL_POSITIVE_SOURCE_MASK_NO_NEW_NEGATIVES'
  if r['completeROI']:
   candidate=by.get(r['sha256']);reason='ORIGINAL_WHOLE_ROI_REQUIRES_MANUAL_SKIN_BOUNDARY_REVIEW'
   if candidate and len(candidate.get('landmarks',[]))>=468:
    if r['sha256'] not in cached:
     im=cv2.imread(candidate['absolutePath']);assert sha(Path(candidate['absolutePath']))==r['sha256'];h,w=im.shape[:2];p=np.array([[v['x']*w,v['y']*h] for v in candidate['landmarks']],np.float32);unknown=np.zeros((h,w),np.uint8)
     holes=[[33,160,158,133,153,144],[263,387,385,362,380,373],[61,40,37,0,267,270,291,321,314,17,84,91],[98,97,2,326,327,294],[70,63,105,66,107,55,65,52],[300,293,334,296,336,285,295,282]]
     for ids in holes:cv2.fillPoly(unknown,[np.rint(p[ids]).astype(np.int32)],1)
     # Algorithmic long-filament exclusion is loss-unknown, not healthy truth.
     unknown|=elongated_dark_mask(cv2.cvtColor(im,cv2.COLOR_BGR2GRAY)).astype(np.uint8);cached[r['sha256']]=unknown
    a,b,c,d=r['rect'];unknown=cached[r['sha256']][b:d,a:c].astype(bool);support[:,:d-b,:c-a]*=~unknown;truth*=support;reason='LANDMARK_EYE_LIP_NOSTRIL_BROW_AND_LONG_FILAMENT_SUPPORT_REMOVED'
  assert np.all(support<=prior) and np.all(truth<=support)
  totals['removedKnownPixels']+=int(prior.sum()-support.sum());totals['removedPositivePixels']+=positive_before-int(truth.sum());np.savez_compressed(dest,rgb=rgb,truth=truth,support=support);rows.append({**r,'positivePixels':int(truth.sum()),'knownNegativePixels':int((support>truth).sum()),'supportRefinement':reason,'wholeValidSkinExpertReviewed':False})
 counts={t:{s:dict(photos=len({r['sha256'] for r in rows if r['target']==t and r['split']==s}),positivePhotos=len({r['sha256'] for r in rows if r['target']==t and r['split']==s and r['positivePixels']}),groups=len({r['group'] for r in rows if r['target']==t and r['split']==s}),tiles=sum(r['target']==t and r['split']==s for r in rows)) for s in ['train','validation','test']} for t in data['targets']}
 write('continuation-valid-skin-data.json',{**data,'rows':rows,'counts':counts,'parentLedgerSHA256':sha(oldpath),'tensorFolder':'continuation-valid-skin/tensors','monotoneSupportExclusion':True,'newNegativePixelLabels':0,'refinementTotals':dict(totals),'wholeSkinExpertBoundaryReviewComplete':False});print(json.dumps(dict(totals)),flush=True)

if __name__=='__main__':main()
