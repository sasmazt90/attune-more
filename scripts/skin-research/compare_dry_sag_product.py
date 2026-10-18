"""Small pinned actual-browser payload comparison; no training or hosted consent."""
import base64,copy,hashlib,importlib.util,json,sys
from pathlib import Path
import cv2,numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
import evaluate_periorbital_and_acne_comparative as audit
import appearance_analysis as A
OUT=ROOT/'audit-results/dry-sag-product-20261013'
rows=[]
for source in json.loads((OUT/'source-selection.json').read_text('utf8')):
 prefix=source['sha256'][:8];f=OUT/(prefix+'-payload.json')
 if not f.exists():continue
 p=json.loads(f.read_text('utf8'));assert not p.get('hostedProcessingConsent')
 before=json.loads((OUT/(prefix+'-browser.json')).read_text('utf8'))['response']
 after=A.analyze_skin(p)
 (OUT/(prefix+'-offline.json')).write_text(json.dumps(after,ensure_ascii=False),'utf8')
 def get(r,region,c):return next(v for v in (r['general']['measurements'] if region=='overview' else r['measurements'][region]) if v['id']==c)
 retained=[];target=[]
 for region,values in after['measurements'].items():
  for item in values:
   if item['id'] not in ('dry','sag'):
    old=get(before,region,item['id']);same=item==old;assert same,(prefix,region,item['id'],'unrelated regional change');retained.append(same)
 for c in ('lines','dark','bags','tone','redness','oil','acne'):
  same=get(before,'overview',c)==get(after,'overview',c);assert same,(prefix,c,'unrelated overview change');retained.append(same)
 shape=A.decode_photo(p['photo'])[0].shape
 for region in ['overview',*after['measurements']]:
  for c in ('dry','sag'):
   if region!='overview' and not any(v['id']==c for v in after['measurements'][region]):continue
   old,new=get(before,region,c),get(after,region,c);layer=after['maps'].get(region+':'+c)
   alpha=audit.project_map_alpha(layer,shape);pixels=int((alpha>0).sum())
   target.append(dict(region=region,criterion=c,before=old['value'],after=new['value'],ui=None if new['value'] is None else int(np.floor(new['value']+.5)),quality=new['quality'],limitation=new['limitationCode'],activeSourcePixels=pixels,evaluatedArea=new['evaluatedArea'],components=new['components']))
 bgr=A.decode_photo(p['photo'])[0]
 for c in ('dry','sag'):
  image=bgr.copy();active=audit.project_map_alpha(after['maps'].get('overview:'+c),shape)>0;image[active]=(image[active]*.35+np.array([0,240,240])*.65).astype('uint8')
  for region in ('rightCheek','leftCheek','chin'):
   m=p['meshes'][region]
   for a,b in m['edges']:cv2.line(image,tuple(np.rint([m['points'][a]['x'],m['points'][a]['y']]).astype(int)),tuple(np.rint([m['points'][b]['x'],m['points'][b]['y']]).astype(int)),(200,80,60),1)
  cv2.imwrite(str(OUT/(prefix+'-'+c+'-after.png')),image)
 row=dict(sourceSHA256=source['sha256'],category=source['imageCategory'],payloadSHA256=hashlib.sha256(f.read_bytes()).hexdigest(),preservedMeasurements=len(retained),allUnrelatedEqual=all(retained),targets=target)
 rows.append(row);print(json.dumps(dict(source=prefix,overview=[v for v in target if v['region']=='overview'])),flush=True)
def preservation():
 # Nine previous lines/bags inputs, frozen source code instead of stale metrics.
 frozen=ROOT/'.runtime/dry-sag-baseline-20261013';saved={n:sys.modules[n] for n in ('instant_appearance','skin_general')}
 def load(n,path):
  spec=importlib.util.spec_from_file_location(n,path);m=importlib.util.module_from_spec(spec);sys.modules[n]=m;spec.loader.exec_module(m);return m
 load('instant_appearance',frozen/'instant_appearance.py');load('skin_general',frozen/'skin_general.py');B=load('frozen_appearance',frozen/'appearance_analysis.py')
 sys.modules.update(saved);proof=[]
 files=[*(ROOT/'audit-results/lines-bags-followup-20261012').glob('*-payload.json'),*(ROOT/'audit-results/bag-label-followup-20261012').glob('*-v2-payload.json')]
 seen=set()
 for f in files:
  digest=hashlib.sha256(f.read_bytes()).hexdigest()
  if digest in seen:continue
  seen.add(digest)
  p=json.loads(f.read_text('utf8'));old=B.analyze_skin(p);new=A.analyze_skin(p);count=0
  for region,items in new['measurements'].items():
   for item in items:
    if item['id'] in ('dry','sag'):continue
    assert item==next(v for v in old['measurements'][region] if v['id']==item['id']),(f.name,region,item['id']);count+=1
  old_maps={k:v for k,v in old['maps'].items() if k.split(':')[-1] not in ('dry','sag')};new_maps={k:v for k,v in new['maps'].items() if k.split(':')[-1] not in ('dry','sag')};same=old_maps==new_maps;assert same,f.name
  before_general=[v for v in old['general']['measurements'] if v['id'] not in ('dry','sag')];after_general=[v for v in new['general']['measurements'] if v['id'] not in ('dry','sag')];general_same=before_general==after_general;assert general_same,f.name
  proof.append(dict(input=f.name,payloadSHA256=digest,preservedRegionalMeasurements=count,preservedGeneralMeasurements=len(after_general),unrelatedGeneralEqual=general_same,unrelatedMapsEqual=same))
 return proof
proof=preservation();(OUT/'same-input-comparison.json').write_text(json.dumps(dict(sources=rows,previousInputPreservation=proof),ensure_ascii=False,indent=2),'utf8')
