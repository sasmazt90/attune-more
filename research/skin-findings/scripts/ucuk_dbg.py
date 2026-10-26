import numpy as np, cv2, json, sys
exec(open('rf/ucuk_sev.py').read().split('out={}')[0].)
K=json.load(open('rate/key.json'))['ucuk']; tiles=[]
for k in K[:8]:
    feats(f'gen/approved/{k}/{k}-front.png'); img,les,zone=dbg
    ys,xs=np.where(zone); c=img[ys.min():ys.max(),xs.min():xs.max()].copy(); m=les[ys.min():ys.max(),xs.min():xs.max()]>0
    o=c.copy(); o[m]=(0,255,0); tiles.append(cv2.resize(np.hstack([c,o]),(500,150)))
cv2.imwrite('rate/ucuk_dbg.jpg',np.vstack(tiles))
