"""Target-specific continuation of the immutable selected ledger.

No test pixels are opened; pending review is not an exclusion. Local lesion and
texture eligibility does not require a face detector or natural color. Publisher
declarations remain declarations, not proof of every third party image's rights.
"""
import collections, hashlib, json
from pathlib import Path
import cv2, numpy as np
from PIL import Image, ImageDraw
from selected_sources import ROOT, OUT as PREVIOUS, MAP, geometry, sha

OUT = ROOT/'audit-results/skin-expanded-20261011'
TARGETS=['type','acne','oil','dry','redness','tone','lines','dark','bags','sag']
LABELS={**MAP,'merve':{'akne':'acne','pul':'dry'},
 'clean3':{**MAP['clean3'],'Skin-Redness':'redness'},
 'skin5':{**MAP['skin5'],'melasma':'tone'},
 'arnold':{**MAP['arnold'],'pigmentation':'tone'}}
# These preserve target semantics: other freckles/moles/marks are confounders.
def write(name,value):
 p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True)
 q=p.with_suffix(p.suffix+'.tmp');q.write_text(json.dumps(value,indent=2,ensure_ascii=False),'utf8');q.replace(p)

def key(r):return r['source']+':'+r['path']+':'+r['sha256']

def annotations(r):
 if r['source']!='old-eye':return r['annotations']
 result=[]
 for a in r['oldMetadata']['annotations']:
  if a['classId'] not in (0,1):continue
  x,y,c,d=a['box'];raw=dict(label='Acne' if a['classId']==0 else 'Eyebags',bbox=[x,y,c-x,d-y],segmentation=[np.asarray(a['polygon']).reshape(-1).tolist()] if a['kind']=='polygon' else [])
  result.append(geometry(raw,r['width'],r['height']))
 return result

def targets(r):
 ts={LABELS.get(r['source'],{}).get(a['label']) for a in annotations(r) if a['validBox'] or a['validMask']}-{None}
 if r['source']=='csv':ts|={t for label,t in [('Oily-Skin','oil'),('Dry-Skin','dry'),('Eyebags','bags')] if (r.get('csvLabels') or {}).get(label)==1}
 if r['source']=='old-skin':ts|={'type','sag'}
 return sorted(ts)

def mask(r,t):
 from review_selected_sources import annotation_mask
 # annotation_mask uses its historical mapping; temporarily supply the target
 # directly by selecting valid geometry, without changing frozen old semantics.
 rr={**r,'annotations':[dict(a,label='Acne') for a in r['annotations'] if LABELS.get(r['source'],{}).get(a['label'])==t],'source':'v11'}
 return annotation_mask(rr,'acne')

def prepare():
 OUT.mkdir(parents=True,exist_ok=True)
 if (OUT/'candidates.json').exists():return
 source=PREVIOUS/'manifest.json';m=json.loads(source.read_text('utf8'));rows=m['rows']
 inventory={t:dict(sourceImages=0,sourceAnnotations=0,sourceGroups=set(),sources={},exclusions=collections.Counter(),splits=collections.Counter(),pendingCandidates=0) for t in TARGETS}
 statuses=[]
 for r in rows:
  ts=targets(r);status={}
  for t in ts:
   v=inventory[t];anns=annotations(r);n=sum(LABELS.get(r['source'],{}).get(a['label'])==t for a in anns)
   v['sourceImages']+=1;v['sourceAnnotations']+=n;v['sourceGroups'].add(r['group']);v['splits'][r['split']]+=1
   s=v['sources'].setdefault(r['source'],dict(images=0,annotations=0));s['images']+=1;s['annotations']+=n
   if r.get('excluded'):v['exclusions'][r['excluded']]+=1;status[t]='excluded:'+r['excluded']
   else:v['pendingCandidates']+=1;status[t]='unreviewed/unprepared'
  statuses.append(dict(key=key(r),sha256=r['sha256'],group=r['group'],split=r['split'],targets=status,naturalColorEligible=r.get('naturalRGB'),textureMayRemainEligible=True))
 for v in inventory.values():v['sourceGroups']=len(v['sourceGroups'])
 write('inventory.json',dict(parentManifestSHA256=sha(source),criteria=inventory,imageStatuses=statuses,rights=m['sources'],personIndependent=False,oldOpenedTestsDevelopmentOnly=True,testPixelsOpened=False))
 # Fixed source/target quotas select distinct groups, without using predictions.
 # A photo may be reviewed for multiple targets. Local crops do not require face.
 quotas={'v11':300,'smart':200,'dc':180,'face':150,'wrinkles':70,'skin5':60,'merve':80,'clean3':100,'arnold':50,'csv':60,'old-eye':60}
 chosen=[]
 for s,limit in quotas.items():
  rs=sorted([r for r in rows if r['source']==s and r['split']!='test' and not r.get('excluded') and targets(r)],key=lambda r:hashlib.sha256(key(r).encode()).hexdigest())
  seen=set();counts=collections.Counter()
  # Round robin by target protects rare redness/oil against abundant acne.
  queues={t:[r for r in rs if t in targets(r)] for t in TARGETS}
  while len(seen)<limit and any(queues.values()):
   for t,q in queues.items():
    while q and q[0]['group'] in seen:q.pop(0)
    if q and len(seen)<limit:
     r=q.pop(0);seen.add(r['group']);counts[t]+=1
     chosen.append({**r,'annotations':annotations(r),'reviewTargets':targets(r),'reviewIndex':len(chosen),'reviewKey':key(r),'crop':[0,0,r['width'],r['height']]})
 write('candidates.json',dict(parentManifestSHA256=sha(source),rows=chosen,testPixelsOpened=False,predictionsUsed=False))
 boards=OUT/'boards';boards.mkdir(exist_ok=True);cv2.setNumThreads(1)
 for start in range(0,len(chosen),12):
  sheet=Image.new('RGB',(1440,1640),(12,18,30));draw=ImageDraw.Draw(sheet)
  for k,r in enumerate(chosen[start:start+12]):
   im=cv2.imread(r['absolutePath']);assert im is not None and sha(Path(r['absolutePath']))==r['sha256']
   h,w=im.shape[:2];scale=min(470/w,350/h);thumb=cv2.resize(im,None,fx=scale,fy=scale);rgb=thumb[:,:,::-1].copy()
   for j,t in enumerate(TARGETS[1:]):
    if t not in r['reviewTargets']:continue
    color=[(j*53+30)%255,(j*79+70)%255,(j*31+180)%255]
    mm=cv2.resize(mask(r,t),(thumb.shape[1],thumb.shape[0]),interpolation=cv2.INTER_NEAREST).astype(bool)
    rgb[mm]=(rgb[mm]*.8+np.array(color)*.2).astype('uint8')
    for a in r['annotations']:
     if LABELS.get(r['source'],{}).get(a['label'])!=t or not a['validBox'] or a['validMask']:continue
     x,y,bw,bh=np.asarray(a['bbox'])*scale;cv2.rectangle(rgb,(round(x),round(y)),(round(x+bw),round(y+bh)),color,1)
   x=k%3*480;y=k//3*410;sheet.paste(Image.fromarray(rgb),(x,y));draw.text((x+4,y+355),f"{r['reviewIndex']} {r['source']} {r['split']} {','.join(r['reviewTargets'])}",fill='white');draw.text((x+4,y+375),r['sha256'][:22],fill='white')
  sheet.save(boards/f'{start//12:03d}.jpg')
 print('Prepared',len(chosen),'review candidates. No training before decisions.',flush=True)

if __name__=='__main__':prepare()
