import json,re,collections,numpy as np,torch,rfdetr,cv2
from PIL import Image
S='/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'; torch.set_num_threads(4)
def cats(ds):
  J=json.load(open(f'{S}/evalds/{ds}/valid/_annotations.coco.json')); c=collections.Counter(a['category_id'] for a in J['annotations']); out={}
  for x in J['categories']:
    if x['name'] not in out or c[x['id']]>c[out[x['name']]]: out[x['name']]=x['id']
  return {v:k for k,v in out.items()}
M={'undereye':(rfdetr.RFDETRSegSmall(pretrain_weights=f'{S}/weights/attune-skin-under-eye-pilot-v1-small/weights.pt'),cats('undereye')),
   'marks':(rfdetr.RFDETRSmall(pretrain_weights=f'{S}/weights/attune-skin-acne-marks-pigmentation-v1-small/weights.pt'),cats('marks'))}
I=[it for tag in ('_k5','_k6') for it in json.load(open(f'items{tag}.json')) if '-front' in it['key']]
out={}
for it in I:
  im=Image.open(it['path']).convert('RGB'); kid=re.match(r'(K-\d+)',it['key']).group(1); out[kid]={'regions':it['regions']}
  for n,(m,cm) in M.items():
    d=m.predict(im,threshold=0.05); out[kid][n]=[(cm.get(int(c),str(c)),float(s),[float(v) for v in b]) for b,s,c in zip(d.xyxy.tolist(),d.confidence,d.class_id)]
json.dump(out,open('extra_preds.json','w')); print(len(out))
