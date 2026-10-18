"""Pin official detection-pretrained weights and retain separate model/code terms.
Local research only. Never deserialize arbitrary globals from the pickle.
"""
from pathlib import Path
import json, hashlib, urllib.request, re, pickle
import numpy as np
from collections import OrderedDict
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'audit-results/all-health-20261010/detection-startup'
OUT.mkdir(parents=True,exist_ok=True)
def get(url):
 with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Attune-source-review'}),timeout=60) as r:return r.read()
revision=json.loads(get('https://api.github.com/repos/facebookresearch/detectron2/commits/main'))['sha']
base=f'https://raw.githubusercontent.com/facebookresearch/detectron2/{revision}/'
files={}
for name in ['MODEL_ZOO.md','LICENSE','configs/COCO-Detection/faster_rcnn_R_50_FPN_3x.yaml','configs/Base-RCNN-FPN.yaml','detectron2/config/defaults.py']:
 data=get(base+name);dest=OUT/name.replace('/','_');dest.write_bytes(data);files[name]=hashlib.sha256(data).hexdigest()
zoo=(OUT/'MODEL_ZOO.md').read_text()
assert 'Attribution-ShareAlike 3.0' in zoo
url=re.search(r'https://dl\.fbaipublicfiles\.com/detectron2/COCO-Detection/faster_rcnn_R_50_FPN_3x/[^\s\"<>]+model_final_[a-f0-9]+\.pkl',zoo).group(0)
target=OUT/'model.pkl'
if not target.exists():
 with urllib.request.urlopen(url,timeout=120) as r, target.open('wb') as f:
  while data:=r.read(1024*1024):f.write(data)
class ArrayOnly(pickle.Unpickler):
 def find_class(self,module,name):
  if (module,name)==('collections','OrderedDict'):return OrderedDict
  if (module,name) in {('numpy.core.multiarray','_reconstruct'),('numpy._core.multiarray','_reconstruct'),('numpy','ndarray'),('numpy','dtype')}:
   return {'_reconstruct':np.core.multiarray._reconstruct,'ndarray':np.ndarray,'dtype':np.dtype}[name]
  raise pickle.UnpicklingError(f'Unexpected global {module}.{name}')
with target.open('rb') as f:state=ArrayOnly(f,encoding='latin1').load()
assert set(state['model']) and all(isinstance(v,np.ndarray) and np.isfinite(v).all() for v in state['model'].values())
np.savez(OUT/'arrays.npz',**state['model'])
report=dict(revision=revision,url=url,codeLicense='Apache-2.0',weightsLicense='CC BY-SA 3.0',datasetPretraining='COCO train2017; official distributor grants model terms',researchOnly=True,files=files,sha256=hashlib.sha256(target.read_bytes()).hexdigest(),bytes=target.stat().st_size,convertedArraySHA256=hashlib.sha256((OUT/'arrays.npz').read_bytes()).hexdigest(),keys={k:list(v.shape) for k,v in state['model'].items()},safeArrayOnlyLoad=True)
(OUT/'rights.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps({k:v for k,v in report.items() if k!='keys'},indent=2))
