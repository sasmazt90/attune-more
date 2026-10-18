"""Private contact sheets for source/crop/label quality review, no history writes."""
import argparse, collections, json, random
import cv2, numpy as np
from prepare_focused_data import OUT,write,sha

def sheet(rows,name):
    for page in range(0,len(rows),48):
        canvas=np.full((6*180,8*160,3),24,np.uint8)
        for i,r in enumerate(rows[page:page+48]):
            image=cv2.imread(r['absolutePath']);a,b,c,d=r.get('crop',[0,0,r['width'],r['height']]);crop=image[b:d,a:c];h,w=crop.shape[:2];scale=min(150/w,140/h);thumb=cv2.resize(crop,(max(1,int(w*scale)),max(1,int(h*scale))))
            for ann in r.get('annotations',[]):
                if ann['classId'] not in [0,1]:continue
                x,y,x1,y1=ann['box'];cv2.rectangle(thumb,(int((x-a)*scale),int((y-b)*scale)),(int((x1-a)*scale),int((y1-b)*scale)),(0,255,255) if ann['classId']==0 else (255,255,0),1)
            x=(i%8)*160;y=(i//8)*180;canvas[y:y+thumb.shape[0],x:x+thumb.shape[1]]=thumb
            cv2.putText(canvas,f'{page+i} {r.get("class",r["corpus"])}', (x+2,y+153),cv2.FONT_HERSHEY_SIMPLEX,.35,(255,255,255),1)
            cv2.putText(canvas,r['sha256'][:12],(x+2,y+170),cv2.FONT_HERSHEY_SIMPLEX,.35,(255,255,255),1)
        cv2.imwrite(str(OUT/f'{name}-{page//48}.jpg'),canvas)
    write(name+'-index.json',[dict(index=i,sha256=r['sha256'],path=r['path'],crop=r.get('crop'),decision=r['qualityDecision']) for i,r in enumerate(rows)])

def main():
    p=argparse.ArgumentParser();p.add_argument('--cache',choices=['skin','eye']);a=p.parse_args();random.seed(20261010)
    rows=json.loads((OUT/(a.cache+'-quality-cache.json')).read_text()) if a.cache else json.loads((OUT/'dataset-manifest.json').read_text())['rows']
    if a.cache:
        grouped=collections.defaultdict(list)
        for r in rows:
            if 'width' in r:grouped[(r.get('class',r['corpus']),r['eligible'])].append(r)
        chosen=[]
        for key,items in sorted(grouped.items()):chosen.extend(random.sample(items,min(12,len(items))))
        sheet(chosen,a.cache+'-quality-review')
    else:
        m=json.loads((OUT/'dataset-manifest.json').read_text());by={r['path']:r for r in rows};chosen=[]
        for conflict in m['conflicts'][:24]:
            for path in conflict['paths'][:2]:
                if path in by:chosen.append(by[path])
        if chosen:sheet(chosen,'conflict-review')
        print(json.dumps(dict(counts=m['counts'],conflicts=len(m['conflicts']),groups=len({r['group'] for r in rows})),indent=2))
if __name__=='__main__':main()
