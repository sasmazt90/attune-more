import json,cv2,numpy as np
lm=json.load(open('stageA-lm.json'));out=[]
for it in lm:
    if not it['face']:continue
    im=cv2.imread(it['frame']);h,w=im.shape[:2]
    xs=[p['x']*w for p in it['landmarks'][:468]];ys=[p['y']*h for p in it['landmarks'][:468]]
    fw=max(xs)-min(xs);cx=(max(xs)+min(xs))/2;cy=(max(ys)+min(ys))/2
    for frac in (0.14,0.18,0.24):
        s=frac*1280/fw;M=np.float32([[s,0,640-cx*s],[0,s,360-cy*s]])
        fr=cv2.warpAffine(im,M,(1280,720),flags=cv2.INTER_AREA if s<1 else cv2.INTER_LINEAR,borderMode=cv2.BORDER_REPLICATE)
        p=f'frames/{it["id"]}_lr{int(frac*100)}.png';cv2.imwrite(p,fr)
        out.append({'id':f'{it["id"]}_lr{int(frac*100)}','src':it['id'],'faceFrac':frac,'res':'1280x720','frame':p})
json.dump(out,open('stageC.json','w'));print(len(out))
