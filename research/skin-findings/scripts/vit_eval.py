import sys,json,re,collections,numpy as np,cv2,io,contextlib
S='/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
sys.path.insert(0,f'{S}/repo/claude-skin/services/core-api')
import local_skin_type as L
def vit(path):
  r=L.infer(cv2.imread(path)); p=np.exp(np.array(r['logits'])-max(r['logits'])); p/=p.sum(); return r['value'],dict(zip(L.CLASSES,p.round(3).tolist()))
out={}
# K set (front crops) + K-004
for f,tag in (('items_k.json','k'),('items_k4.json','k4'),('items_cp.json','cp')):
  for it in json.load(open(f)):
    if abs(it['yaw'])<8: out[it['key']]=vit(it['path'])
# ka1tj whole-face labelled (all splits) via dataset files
import glob
for sp in ('train','valid','test'):
  J=json.load(open(f'{S}/ds/ka1tj/{sp}/_annotations.coco.json')); cats={c['id']:c['name'] for c in J['categories']}
  lab=collections.defaultdict(set)
  for a in J['annotations']: lab[a['image_id']].add(cats[a['category_id']])
  for im in J['images']:
    l=[x for x in lab[im['id']] if x in('dry','normal','oily')]
    if len(l)==1: out['ka1tj/'+sp+'/'+im['file_name']]=(*vit(f"{S}/ds/ka1tj/{sp}/{im['file_name']}"),l[0])
json.dump(out,open('vit_scores.json','w'),ensure_ascii=False)
k=[(v[2],v[0]) for kk,v in out.items() if kk.startswith('ka1tj')]
print('ka1tj (tüm yüz etiketli) n',len(k),'doğruluk',round(np.mean([a==b for a,b in k]),3),collections.Counter(k))
