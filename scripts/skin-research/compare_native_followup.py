"""Frozen db3 versus working dry/sag, exact same browser payload, no cloud."""
import base64,hashlib,importlib.util,json,sys,time
from pathlib import Path
import cv2,numpy as np
cv2.setNumThreads(1)
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
import evaluate_periorbital_and_acne_comparative as audit
import appearance_analysis as A
OUT=ROOT/'audit-results/dry-sag-native-followup-20261013';frozen=ROOT/'.runtime/dry-sag-native-baseline-20261013'
saved={n:sys.modules[n] for n in ('instant_appearance','skin_general')}
for n in ['instant_appearance','skin_general','appearance_analysis']:
 name=n if n!='appearance_analysis' else 'native_frozen_analysis';spec=importlib.util.spec_from_file_location(name,frozen/(n+'.py'));m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m)
 if n=='appearance_analysis':B=m
sys.modules.update(saved)
rows=[];started=time.monotonic()
files=list(OUT.glob('*-payload.json'))
# Prior FRONT diagnostic d3 is deliberately kept separate from its real LEFT capture.
files.append(ROOT/'audit-results/dry-sag-product-20261013/d3e8bb60-payload.json')
if '--boundary-trial' in sys.argv:files=[f for f in files if f.name.startswith(('515cc548','d3e8bb60','0642d4ab','36e4010b'))]
for f in files:
 prefix=f.name[:8]+('-front-replay' if f.parent!=OUT else '');p=json.loads(f.read_text('utf8'));assert not p['hostedProcessingConsent'];tic=time.monotonic();old=B.analyze_skin(p);new=A.analyze_skin(p)
 (OUT/(prefix+('-boundary-working.json' if '--boundary-trial' in sys.argv else '-working.json'))).write_text(json.dumps(new,ensure_ascii=False),'utf8')
 if not (OUT/(prefix+'-baseline.json')).exists():(OUT/(prefix+'-baseline.json')).write_text(json.dumps(old,ensure_ascii=False),'utf8')
 protected=[];targets=[];shape=A.decode_photo(p['photo'])[0].shape
 for region in [*new['measurements'],'overview']:
  if region=='overview' and 'general' not in new:continue
  before=old['general']['measurements'] if region=='overview' else old['measurements'][region];after=new['general']['measurements'] if region=='overview' else new['measurements'][region]
  for v in after:
   b=next(i for i in before if i['id']==v['id'])
   if v['id'] not in ('dry','sag'):assert v==b,(prefix,region,v['id']);protected.append(v==b);continue
   layer=new['maps'].get(region+':'+v['id']);alpha=audit.project_map_alpha(layer,shape);oldalpha=audit.project_map_alpha(old['maps'].get(region+':'+v['id']),shape)
   targets.append(dict(region=region,id=v['id'],before=b['value'],after=v['value'],beforeActiveSourcePixels=int((oldalpha>0).sum()),activeSourcePixels=int((alpha>0).sum()),mapStep=layer['step'] if layer else None,limitation=v['limitationCode'],components=v['components']))
 oldmaps={k:v for k,v in old['maps'].items() if k.split(':')[-1] not in ('dry','sag')};newmaps={k:v for k,v in new['maps'].items() if k.split(':')[-1] not in ('dry','sag')};assert oldmaps==newmaps,prefix
 row=dict(source=prefix,payloadSHA256=hashlib.sha256(f.read_bytes()).hexdigest(),seconds=time.monotonic()-tic,protectedMeasurements=len(protected),protectedEqual=all(protected),protectedMapsEqual=oldmaps==newmaps,targets=targets);rows.append(row);print(json.dumps(dict(source=prefix,seconds=row['seconds'],targets=[{k:v for k,v in t.items() if k!='components'} for t in targets if t['region'] in ['overview','chin','leftCheek','rightCheek'] and (t['id']=='dry' or t['region']=='overview')])),flush=True)
(OUT/('same-input-boundary-trial.json' if '--boundary-trial' in sys.argv else 'same-input-working.json')).write_text(json.dumps(dict(totalSeconds=time.monotonic()-started,sources=rows),ensure_ascii=False,indent=2),'utf8')
