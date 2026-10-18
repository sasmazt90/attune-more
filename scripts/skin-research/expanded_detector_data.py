"""Frozen native-tile active-Pimple pool; positives and reviewed negatives only."""
import collections,json
import numpy as np
from expanded_sources import OUT,PREVIOUS,write,sha

def prepare():
 path=OUT/'detector-data.json'
 if path.exists():return json.loads(path.read_text('utf8'))
 candidates=json.loads((OUT/'candidates.json').read_text('utf8'))['rows'];decisions=json.loads((OUT/'decisions.json').read_text('utf8'));by={d['reviewKey']:d for d in decisions['rows']}
 # Photo/crop relations visually verified in the displayed source boards. They
 # are image families, not inferred identities. Historical ledger is unchanged.
 edges=[(349,401),(460,469)];parents={r['group']:r['group'] for r in candidates}
 def find(g):
  while parents[g]!=g:g=parents[g]
  return g
 for a,b in edges:
  ga=find(candidates[a]['group']);gb=find(candidates[b]['group']);parents[max(ga,gb)]=min(ga,gb)
 related={find(candidates[i]['group']) for e in edges for i in e}
 rows=[]
 for r in candidates:
  d=by.get(r['reviewKey'])
  if r['source']!='smart' or not d or not d['rightsEligible'] or d['excludedReason'] or not d.get('pimpleBoxesReviewed'):continue
  anns=[]
  for a in r['annotations']:
   if a['label']=='Pimple' and a['validBox']:
    x,y,w,h=a['bbox'];anns.append(dict(classId=0,box=[x,y,x+w,y+h],kind='box'))
  if not anns:continue
  group=find(r['group']);rows.append({**r,'annotations':anns,'group':group,'split':'train' if group in related else r['split'],'reviewDecision':d,'negativeROI':None,'negativeScope':'unknown outside reviewed active Pimple boxes'})
 # Preserve exact historical review key instead of last-decision-wins by SHA.
 old=json.loads((PREVIOUS/'review/candidates.json').read_text('utf8'))['rows'];ds=json.loads((PREVIOUS/'review/decisions.json').read_text('utf8'))['rows'];bd={(d['reviewIndex'],d['sha256']):d for d in ds}
 for r in old:
  d=bd[(r['reviewIndex'],r['sha256'])]
  if d['naturalEligible'] and d['rightsEligible'] and d.get('completePimpleROI') and d['appearanceLabels']['acne']=='negative':
   rows.append({**r,'annotations':[],'reviewDecision':d,'negativeROI':'reviewed-visible-face','negativeScope':'whole engineering-reviewed visible face; hair/background/padding unknown'})
 # Quarantine uncertain near matches crossing train/validation rather than
 # asserting dHash establishes a photo relation or reopening test images.
 m=json.loads((PREVIOUS/'manifest.json').read_text('utf8'));lookup={r['sha256']:r for r in m['rows']};blocked=set()
 for a,b,*_ in m['perceptualQuarantinePairs']:
  ra,rb=m['rows'][a],m['rows'][b]
  if ra['split']!=rb['split']:
   if ra['split']=='validation':blocked.add(ra['group'])
   if rb['split']=='validation':blocked.add(rb['group'])
 quarantined=[dict(sha256=r['sha256'],group=r['group'],reason='UNRESOLVED_NEAR_PHOTO_RELATION') for r in rows if r['split']=='validation' and r['group'] in blocked]
 rows=[r for r in rows if not (r['split']=='validation' and r['group'] in blocked)]
 # Exactly duplicated photos must not be repeated as independent examples.
 seen=set();unique=[]
 for r in rows:
  k=r['decodedSHA256'] if 'decodedSHA256' in r else r['sha256']
  if k not in seen:unique.append(r);seen.add(k)
 rows=unique
 assert not ({r['group'] for r in rows if r['split']=='train'}&{r['group'] for r in rows if r['split']=='validation'})
 result=dict(rows=rows,candidatesSHA256=sha(OUT/'candidates.json'),decisionsSHA256=sha(OUT/'decisions.json'),historicalReviewSHA256=sha(PREVIOUS/'review/decisions.json'),verifiedPhotoRelations=edges,quarantined=quarantined,expertLabels=False,independentFinal=False,counts={s:dict(images=sum(r['split']==s for r in rows),groups=len({r['group'] for r in rows if r['split']==s}),positivePhotos=sum(r['split']==s and bool(r['annotations']) for r in rows),fullyReviewedNegativePhotos=sum(r['split']==s and r['negativeROI'] is not None for r in rows),lesions=sum(len(r['annotations']) for r in rows if r['split']==s)) for s in ['train','validation']})
 write('detector-data.json',result);print(json.dumps(result['counts'],indent=2));return result

if __name__=='__main__':prepare()
