"""Additional native annotation boards, preserving the running frozen pools."""
import hashlib,json
import cv2,numpy as np
from PIL import Image,ImageDraw
from expanded_sources import OUT,PREVIOUS,TARGETS,LABELS,key,sha,write,targets,annotations,mask

def main():
 path=OUT/'supplement/candidates.json'
 if path.exists():print('Existing supplement preserved');return
 allrows=json.loads((PREVIOUS/'manifest.json').read_text('utf8'))['rows']
 previous=json.loads((OUT/'candidates.json').read_text('utf8'))['rows']
 seen={(r['source'],r['group']) for r in previous};chosen=[]
 for source in ['v11','care']:
  rows=sorted([r for r in allrows if r['source']==source and r['split']!='test' and not r.get('excluded') and targets(r)],key=lambda r:hashlib.sha256(key(r).encode()).hexdigest())
  for r in rows:
   if (source,r['group']) in seen:continue
   seen.add((source,r['group']));chosen.append({**r,'annotations':annotations(r),'reviewTargets':targets(r),'reviewIndex':len(chosen),'reviewKey':key(r)})
 write('supplement/candidates.json',dict(rows=chosen,parentManifestSHA256=sha(PREVIOUS/'manifest.json'),existingCandidatesSHA256=sha(OUT/'candidates.json'),testPixelsOpened=False,predictionsUsed=False))
 boards=OUT/'supplement/boards';boards.mkdir(parents=True,exist_ok=True);cv2.setNumThreads(1)
 for start in range(0,len(chosen),12):
  sheet=Image.new('RGB',(1440,1640),(12,18,30));draw=ImageDraw.Draw(sheet)
  for k,r in enumerate(chosen[start:start+12]):
   im=cv2.imread(r['absolutePath']);assert im is not None and sha(__import__('pathlib').Path(r['absolutePath']))==r['sha256']
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
 print('Supplement',len(chosen),'photos',len(range(0,len(chosen),12)),'boards; running training data untouched',flush=True)

if __name__=='__main__':main()
