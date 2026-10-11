"""Blind engineering negative review candidates; source class is not truth."""
import collections,hashlib,json
from pathlib import Path
import cv2
from PIL import Image,ImageDraw
from expanded_sources import OUT,PREVIOUS,write,sha
p=OUT/'negative-expansion/candidates.json'
if p.exists():raise SystemExit('Existing negative review preserved')
rows=json.loads((PREVIOUS/'manifest.json').read_text('utf8'))['rows'];seen=set();exposed=set()
for name in ['candidates.json','supplement/candidates.json','sag-controls/candidates.json','sag-controls/additional-candidates.json','local-control-review/dry-negative-index.json']:
 v=json.loads((OUT/name).read_text('utf8'));rs=v if isinstance(v,list) else v['rows'];exposed|={r['sha256'] for r in rs};seen|={r['group'] for r in rs}
chosen=[]
for source,limit in [('old-skin',72),('old-eye',48)]:
 candidates=sorted([r for r in rows if r['source']==source and r['split']!='test' and not r.get('excluded') and min(r['width'],r['height'])>=450 and r['sha256'] not in exposed and r['group'] not in seen and (source!='old-skin' or r['oldMetadata'].get('typeEligible'))],key=lambda r:hashlib.sha256(r['sha256'].encode()).hexdigest())
 for r in candidates:
  if r['group'] in seen:continue
  seen.add(r['group']);chosen.append({**r,'reviewIndex':len(chosen),'classUsedAsNegativeTruth':False})
  if sum(r['source']==source for r in chosen)>=limit:break
write('negative-expansion/candidates.json',dict(rows=chosen,oldOpenedDataDevelopmentOnly=True,predictionsUsed=False,testPixelsOpened=False))
folder=OUT/'negative-expansion/boards';folder.mkdir(parents=True,exist_ok=True);cv2.setNumThreads(1)
for start in range(0,len(chosen),12):
 sheet=Image.new('RGB',(1440,1640),(12,18,30));draw=ImageDraw.Draw(sheet)
 for j,r in enumerate(chosen[start:start+12]):
  assert sha(Path(r['absolutePath']))==r['sha256'];im=cv2.imread(r['absolutePath']);h,w=im.shape[:2];scale=min(470/w,350/h);thumb=cv2.resize(im,None,fx=scale,fy=scale);x=j%3*480;y=j//3*410;sheet.paste(Image.fromarray(thumb[:,:,::-1]),(x,y));draw.text((x+4,y+355),f"{r['reviewIndex']} {r['source']} {r['split']} source class is NOT truth",fill='white');draw.text((x+4,y+375),r['sha256'][:22],fill='white')
 sheet.save(folder/f'{start//12:02d}.jpg')
print('negative review',len(chosen),'photos',collections.Counter(r['split'] for r in chosen),flush=True)
