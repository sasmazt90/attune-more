"""Real normal API vs independently computed same-input result and source maps."""
import copy,hashlib,json,sys
from pathlib import Path
import cv2,numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
import evaluate_periorbital_and_acne_comparative as audit
import appearance_analysis as A
IMPULSE='--lines-impulse' in sys.argv
OUT=ROOT/'audit-results'/('lines-impulse-20261012' if IMPULSE else 'lines-bags-followup-20261012')
INPUT=ROOT/'audit-results/lines-bags-followup-20261012'
rows=json.loads((OUT/'same-input-comparison.json').read_text('utf8'))
audit.request('http://127.0.0.1:8000/api/vehicle/speed',{'speedKmH':0})
proof=[]
for row in rows:
 prefix=row['sourceSHA256'][:8];f=INPUT/(prefix+'-payload.json')
 if not f.exists():f=ROOT/'audit-results/bag-label-followup-20261012'/(prefix+'-v2-payload.json')
 p=json.loads(f.read_text('utf8'));actual=audit.request('http://127.0.0.1:8000/api/local-health/skin',p)
 expected=json.loads((OUT/(prefix+'-offline.json')).read_text('utf8'))
 def comparable_general(response):
  general=copy.deepcopy(response['general'])
  for model in general.get('modelInference',{}).values():
   model.pop('loadMs',None);model.pop('inferenceMs',None)
  return general
 matches=all(actual.get(key)==expected.get(key) for key in ('measurements','maps','contours')) and comparable_general(actual)==comparable_general(expected)
 assert matches,(prefix,'API differs from actual working source')
 (OUT/(prefix+'-normal-api.json')).write_text(json.dumps(actual,ensure_ascii=False),'utf8')
 shape=A.decode_photo(p['photo'])[0].shape
 geometry={c:audit.anatomy(actual['maps'].get('periorbital:'+c),p,shape,c) for c in ('lines','bags')}
 assert all(g['outsideEyeBandAnalysisPixels']==0 and g['outsideSelectedRegionAnalysisPixels']==0 for g in geometry.values())
 lines=next(v for v in actual['measurements']['periorbital'] if v['id']=='lines');bag=next(v for v in actual['measurements']['periorbital'] if v['id']=='bags')
 assert lines['normalizationVersion']=='outer-canthus-gabor-radiating-hair-excluded-v4'
 if IMPULSE:assert lines['components']['samplingSupportVersion']=='native-impulse-one-cycle-lines-v1'
 assert bag['components']['samplingSupportVersion']=='tracked-center-closed-cells-impulse-v3'
 bgr=A.decode_photo(p['photo'])[0]
 for criterion in ('lines','bags'):
  layer=actual['maps'].get('periorbital:'+criterion);active=audit.project_map_alpha(layer,shape)>0;image=bgr.copy();image[active]=(image[active]*.3+np.array([255,240,0])*.7).astype('uint8')
  for m in p['meshes']['periorbital']['edges']:
   pts=p['meshes']['periorbital']['points'];cv2.line(image,tuple(np.rint([pts[m[0]]['x'],pts[m[0]]['y']]).astype(int)),tuple(np.rint([pts[m[1]]['x'],pts[m[1]]['y']]).astype(int)),(60,180,180),1)
  cv2.imwrite(str(OUT/(prefix+'-'+criterion+'-normal-map.png')),image)
 proof.append(dict(sourceSHA256=row['sourceSHA256'],actualAPIEqualsOffline=matches,actualAPIPhotoMatches=p['photoId']==actual['photoId'],lines=lines['value'],bags=bag['value'],geometry=geometry))
 print(json.dumps({'source':prefix,'lines':lines['value'],'bags':bag['value'],'matches':matches}),flush=True)
(OUT/'normal-api-receipt.json').write_text(json.dumps(proof,indent=2),'utf8')
