import json,sys,os,numpy as np,torch,cv2
from PIL import Image
import rfdetr
S='/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'; torch.set_num_threads(2)
TAG=os.environ.get('TAG',''); I=json.load(open(f'{S}/rf/items{TAG}.json')); os.makedirs(f'{S}/rf/wmask{TAG}',exist_ok=True)
M=rfdetr.RFDETRSegSmall(pretrain_weights=f'{S}/weights/wrinkles-79rrf-t7kyp-v1-small/weights.pt')
THR=float(json.load(open(f'{S}/evalres/wrinkles_2.json'))['classes']['wrinkles']['L1']['thr'])
for it in I:
  fn=f"{S}/rf/wmask{TAG}/{it['id']}.png"
  if os.path.exists(fn): continue
  d=M.predict(Image.open(it['path']).convert('RGB'),threshold=THR)
  m=np.zeros((it['h'],it['w']),np.uint8)
  if d.mask is not None:
    for mm in d.mask: m|=mm.astype(np.uint8)
  cv2.imwrite(fn,m*255)
print('done',THR)
