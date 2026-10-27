"""Re-frame each portrait as a 1920x1080 cabin-camera frame at a given face width
fraction (geometric resize/translate only; no pixel synthesis inside the face)."""
import json,cv2,numpy as np,sys
lm=json.load(open('stageA-lm.json'));out=[]
for it in lm:
    if not it['face']:continue
    im=cv2.imread(it['frame']);h,w=im.shape[:2]
    xs=[p['x']*w for p in it['landmarks'][:468]];ys=[p['y']*h for p in it['landmarks'][:468]]
    fw=max(xs)-min(xs);cx=(max(xs)+min(xs))/2;cy=(max(ys)+min(ys))/2
    for frac in (0.16,0.22,0.30):
        s=frac*1920/fw;M=np.float32([[s,0,960-cx*s],[0,s,540-cy*s]])
        interp=cv2.INTER_AREA if s<1 else cv2.INTER_LINEAR
        fr=cv2.warpAffine(im,M,(1920,1080),flags=interp,borderMode=cv2.BORDER_REPLICATE)
        p=f'frames/{it["id"]}_f{int(frac*100)}.png';cv2.imwrite(p,fr)
        out.append({'id':f'{it["id"]}_f{int(frac*100)}','src':it['id'],'faceFrac':frac,'scale':s,'frame':p})
json.dump(out,open('stageB.json','w'));print(len(out))
