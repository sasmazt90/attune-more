"""A separate acne negative-photo phase ledger; boxes never become masks."""
import collections,json,sys
from expanded_sources import ROOT,OUT,write,sha
sys.path.insert(0,str(ROOT/'services/core-api'))
from skin_models import photo_input
import cv2
p=OUT/'negative-expanded-detector-data.json'
if p.exists():raise SystemExit('Existing phase ledger preserved')
parent=OUT/'detector-data.json';data=json.loads(parent.read_text('utf8'));rows=data['rows'].copy();n=json.loads((OUT/'negative-expanded-mask-data.json').read_text('utf8'));sources={r['sha256']:r for r in json.loads((OUT/'negative-expansion/candidates.json').read_text('utf8'))['rows']};existing={r['sha256'] for r in rows}
for r in n['preparedNegativePhotos']:
 if 'acne' not in r['targets'] or r['sha256'] in existing:continue
 source=sources[r['sha256']];image=cv2.imread(source['absolutePath']);_,crop=photo_input(image,r['landmarks']);a,b=crop['x'],crop['y'];rows.append({**source,**r,'crop':[a,b,a+crop['width'],b+crop['height']],'annotations':[],'negativeROI':'engineering-reviewed-visible-face','negativeScope':'criterion-specific visible skin; source class not used, non-skin excluded','reviewDecision':{'naturalEligible':True,'rightsEligible':True,'expertLabels':False}})
assert not {r['group'] for r in rows if r['split']=='train'}&{r['group'] for r in rows if r['split']=='validation'}
counts={s:dict(images=sum(r['split']==s for r in rows),groups=len({r['group'] for r in rows if r['split']==s}),positivePhotos=sum(r['split']==s and bool(r['annotations']) for r in rows),fullyReviewedNegativePhotos=sum(r['split']==s and r['negativeROI'] is not None for r in rows),lesions=sum(len(r['annotations']) for r in rows if r['split']==s)) for s in ['train','validation']}
write('negative-expanded-detector-data.json',{**data,'version':'active-pimple-negative-photo-expansion-v1','rows':rows,'counts':counts,'parentDataSHA256':sha(parent),'negativeReviewSHA256':sha(OUT/'negative-expansion/review.json'),'trainingExposure':False,'phaseChangeRequired':True,'originalWeightsOrderAndOptimizerNotModified':True});print(json.dumps(counts))
