"""Fixed reviewed optical ROIs, not full segmentation or clinical accuracy."""
import hashlib,json,sys
from pathlib import Path
import cv2,numpy as np
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'services/core-api'))
import appearance_analysis as A
from flake_local_classifier import OUT,proposal,candidate_field,FEATURES
cv2.setNumThreads(1)
c=json.loads((OUT/'controls-reviewed.json').read_text('utf8'))
model=json.loads((OUT/'staging-patch-tree.json').read_text('utf8'))
patches=json.loads((OUT/'patches-reviewed.json').read_text('utf8'))['patches']
fit=json.loads((OUT/'patch-tree-fit.json').read_text('utf8'))
def stats(signal,gray):
    active=signal>.04;n,_,components,_=cv2.connectedComponentsWithStats(active.astype('uint8'))
    areas=components[1:,4]
    background=gray[~active];reference=float(np.median(background)) if background.size else None
    return dict(activePixels=int(active.sum()),reviewedROIPixels=int(active.size),opticalAreaPercent=float(active.mean()*100),componentCount=n-1,largestComponentPixels=int(areas.max()) if areas.size else 0,medianComponentPixels=float(np.median(areas)) if areas.size else 0,meanSupport=float(signal[active].mean()) if active.any() else 0,localContrastFromNonCandidateBackground=float(gray[active].mean()-reference) if active.any() and reference is not None else None)
rows=[];thumbs=[]
for r in c['controls']:
    source=Path(r['sourcePath']);assert hashlib.sha256(source.read_bytes()).hexdigest()==r['sourceSHA256']
    bgr=cv2.imread(str(source));x,y,w,h=r['roi'];gray=cv2.cvtColor(bgr[y:y+h,x:x+w],cv2.COLOR_BGR2GRAY)
    observations=[]
    for factor in (1,.5):
        g=cv2.resize(gray,None,fx=factor,fy=factor,interpolation=cv2.INTER_AREA) if factor!=1 else gray
        signals={'productionV3OpticalOnly':A.compute_dryness_signal(g)[0],'nativeBrightProposal':proposal(g),'patchTreeCandidate':candidate_field(g,model)}
        observations.append(dict(sourceResolutionFactor=factor,fields={name:stats(s,g.astype(float)/255) for name,s in signals.items()}))
        if factor==1:
            for name,s in signals.items():
                rgb=bgr[y:y+h,x:x+w,::-1].copy();mask=s>.04;rgb[mask]=(.3*rgb[mask]+.7*np.array([255,0,0])).astype('uint8')
                im=Image.fromarray(rgb).resize((180,180));d=ImageDraw.Draw(im);d.text((2,2),f"C{r['controlIndex']} {name}\n{int(mask.sum())} / {mask.size}",fill='cyan');thumbs.append(im)
    rows.append(dict(controlIndex=r['controlIndex'],sourceSHA256=r['sourceSHA256'],kind=r['kind'],split=r['split'],reviewedROI=r['roi'],patchPresenceLabel=r['patchPresenceLabel'],outsideROI='unknown',observations=observations))
for start in range(0,len(thumbs),24):
    sheet=Image.new('RGB',(3*180,8*185),'#111')
    for j,im in enumerate(thumbs[start:start+24]):sheet.paste(im,(j%3*180,j//3*185))
    sheet.save(OUT/f'candidate-local-support-{start//24}.png')
domains={}
for kind in ('pul','raw','old'):
    matrix=np.zeros((2,2),int)
    for row in fit['observations']:
        if row['kind']==kind:matrix[row['label'],row['prediction']]+=1
    domains[kind]=dict(confusionMatrix=matrix.tolist(),meaning='reviewed patch presence, not pixel truth')
featureSummary={}
for kind in ('pul','raw'):
    featureSummary[kind]={str(label):{name:float(np.median(np.array([r['features'] for r in patches if r['split']=='train' and r['kind']==kind and r['label']==label])[:,i])) for i,name in enumerate(FEATURES)} for label in (0,1)}
matrix=np.asarray(fit['confusionMatrix']);recall=float(matrix[1,1]/matrix[1].sum());fpr=float(matrix[0,1]/matrix[0].sum())
receipt=dict(controlsSHA256=hashlib.sha256((OUT/'controls-reviewed.json').read_bytes()).hexdigest(),modelSHA256=hashlib.sha256((OUT/'staging-patch-tree.json').read_bytes()).hexdigest(),rows=rows,domains=domains,trainFeatureMedians=featureSummary,reviewedPatchRecall=recall,reviewedPatchFPR=fpr,accepted=False,rejectionReason='Misses 10/14 visibly flake-positive validation patches while accepting 8/14 reviewed texture/reflection negatives. Presence-level gate cannot localize flakes within positive contexts; broad contextual union also preserves pore candidates. This is meaningful failure on fixed separated source groups, not a zero-pixel rule.',sourcePersonIndependent=False,photoColorsChanged=False,productionChanged=False,regionalUserScore='Not produced for partial ROI sources: no valid face geometry; optical ROI density is not a user severity score.',pixelDice=None,pixelPrecision=None)
(OUT/'candidate-local-comparison.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),'utf8')
print(json.dumps(dict(reviewedPatchRecall=recall,reviewedPatchFPR=fpr,domains=domains,accepted=False)))
