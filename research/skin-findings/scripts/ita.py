import json,os,numpy as np,cv2,math,sys,collections
from PIL import Image
TAG=sys.argv[1] if len(sys.argv)>1 else ''
I=json.load(open(f'items{TAG}.json')); out={}
for it in I:
  img=np.array(Image.open(it['path']).convert('RGB')); lab=cv2.cvtColor(img,cv2.COLOR_RGB2LAB).astype(np.float32)
  m=np.zeros(img.shape[:2],np.uint8)
  for k in ('forehead','cheek_imgL','cheek_imgR'): cv2.fillPoly(m,[np.array(it['regions'][k],np.int32)],1)
  if m.sum()<100: continue
  L=lab[...,0][m>0]*100/255; b=lab[...,2][m>0]-128
  ita=math.degrees(math.atan2(np.median(L)-50,max(np.median(b),1e-3)))
  out[it['id']]=round(ita,1)
json.dump(out,open(f'ita{TAG}.json','w'))
g=lambda a:'light' if a>41 else ('medium' if a>10 else 'dark')
print(collections.Counter((it['set'],g(out[it['id']])) for it in I if it['id'] in out))
if TAG=='_cp':
  for it in I:
    if abs(it['yaw'])<8: print(it['key'][:22],out.get(it['id']),g(out.get(it['id'],50)))
