import json,numpy as np,cv2
exec(open('rules.py').read().split("out={}")[0])
I={it['id']:it for it in json.load(open('items.json'))}
sc=SC['oily_models+shine']; rows,yl,_=TASKS['oily']; te=[r for r in rows if r['test']]
fp=[r for r in te if sc(r)>=0.25 and yl(r)==0 and not any(k in r['classes'] for k in('Oily',)) and max(r['gt'].get('oily',0),r['gt'].get('Oily',0))==0]
tiles=[]
for r in fp[:24]:
  it=I[r['id']]; img=cv2.imread(it['path']); poly=np.array(it['regions'][r['region']])
  x0,y0=poly.min(0).astype(int); x1,y1=poly.max(0).astype(int); pad=int(0.6*max(x1-x0,y1-y0))
  X0,Y0=max(0,x0-pad),max(0,y0-pad); c=img[Y0:y1+pad,X0:x1+pad].copy()
  cv2.polylines(c,[(poly-[X0,Y0]).astype(np.int32)],True,(0,255,0),2)
  c=cv2.resize(c,(300,300)); cv2.putText(c,f"{r['set']} {r['region']} {sc(r):.2f} gt={list(r['gt'])}"[:46],(4,18),0,0.42,(255,255,255),2); cv2.putText(c,f"{r['set']} {r['region']} {sc(r):.2f} gt={list(r['gt'])}"[:46],(4,18),0,0.42,(0,0,0),1)
  tiles.append(c)
while len(tiles)%6: tiles.append(np.zeros((300,300,3),np.uint8))
G=np.vstack([np.hstack(tiles[i:i+6]) for i in range(0,len(tiles),6)]); cv2.imwrite('oily_fp.jpg',G); print(len(fp))
