import pickle,json,numpy as np
S='/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
M=pickle.load(open('fuse2_models.pkl','rb')); R=json.load(open('fuse2_results.json'))
def cats(ds):
  import collections
  J=json.load(open(f'{ds}/valid/_annotations.coco.json')); c=collections.Counter(a['category_id'] for a in J['annotations']); out={}
  for x in J['categories']:
    if x['name'] not in out or c[x['id']]>c[out[x['name']]]: out[x['name']]=x['id']
  return {str(v):k for k,v in out.items()}
L6=pickle.load(open('l6qra_clf.pkl','rb')); sc,lr=L6[0],L6[-1]
P=dict(version='regional-skin-v3-params-20261025e',minCleanFraction=0.3,sensDarkEvidenceThreshold=0.35,
  stats={g:{k:[float(m),float(s)] for k,(m,s) in d.items()} for g,d in M['STATS'].items()},
  models={t:dict(coef=M[k].coef_[0].tolist(),intercept=float(M[k].intercept_[0])) for t,k in (('oily','Mo'),('dry','Md'),('sens','Ms'))},
  thresholds=dict(oily=M['To'],dry=M['Td'],sens=M['Ts']),
  detectors={'skinmap':dict(arch='RFDETRSegSmall',weights='skinmap.pt',classes=cats(f'{S}/evalds/skinmap')),
             'findings':dict(arch='RFDETRSmall',weights='findings.pt',classes=cats(f'{S}/evalds/findings')),
             'acnes':dict(arch='RFDETRSegSmall',weights='acnes.pt',classes=cats(f'{S}/evalds/acnes')),
             'regional':dict(arch='RFDETRSmall',weights='regional.pt',classes={'1':'dry','2':'oily'}),
             'wrinkles':dict(arch='RFDETRSegSmall',weights='wrinkles.pt',role='wrinkle-mask',threshold=float(json.load(open(f'{S}/evalres/wrinkles_2.json'))['classes']['wrinkles']['L1']['thr']))},
  validation=dict(oily=R['oily']['testToneThr'],dry=R['dry']['testToneThr'],sens=R['sens']['testToneThr'],threeClass=R['threeClassTest'],scinDarkSensitivity=dict(fitzpatrickVtoVI_positives=19,recall_at_045=0.32,recall_at_035=0.47,falseAlarm_testbedDark=0.09,falseAlarm_customerProfilesDark='1/12 images'),note='thresholds chosen on fit split (grouped OOF F1); test reported once; periorbital not validated'))
D=f'{S}/repo/claude-skin/services/core-api/models/regional-skin-v3'; import os; os.makedirs(D,exist_ok=True)
json.dump(P,open(f'{D}/params.json','w'),indent=1,ensure_ascii=False); print('ok',P['thresholds'])
