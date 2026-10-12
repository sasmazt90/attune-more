"""Normal API: same real captured inputs, computed geometry/label/preservation."""
import json,sys,hashlib
from pathlib import Path
import cv2
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
import evaluate_periorbital_and_acne_comparative as audit
OUT=ROOT/'audit-results/bag-label-followup-20261012';rows=[]
audit.request('http://127.0.0.1:8000/api/vehicle/speed',dict(speedKmH=0))
sources=json.loads((audit.OUT/'sources.json').read_text('utf8'))['sources']
for source in sources:
 assert audit.compute_sha256(source['absolutePath'])==source['sha256'],'Source inventory drift'
 prefix=source['sha256'][:8];p=json.loads((OUT/(prefix+'-v2-payload.json')).read_text('utf8'));old=json.loads((audit.OUT/(prefix+'-browser-api.json')).read_text('utf8'))['response'];offline=json.loads((OUT/(prefix+'-v2-offline.json')).read_text('utf8'));actual=audit.request('http://127.0.0.1:8000/api/local-health/skin',p)
 matchesOffline=actual['measurements']==offline['measurements'] and actual['maps']==offline['maps'];assert matchesOffline
 bag=next(v for v in actual['measurements']['periorbital'] if v['id']=='bags');before=next(v for v in old['measurements']['periorbital'] if v['id']=='bags');assert bag['components']['samplingSupportVersion']=='tracked-center-closed-cells-v2'
 image=cv2.imread(source['absolutePath']);geometry=audit.anatomy(actual['maps'].get('periorbital:bags'),p,image.shape,'bags');bandAndRegion=geometry['outsideEyeBandAnalysisPixels']==0 and geometry['outsideSelectedRegionAnalysisPixels']==0;assert bandAndRegion
 roi=audit.known_roi(source,image.shape,['acne','oil','dry','redness','tone','lines','dark','bags'],positive=source['sampleCategory']=='development_positive_polygon');active=audit.project_map_alpha(actual['maps'].get('periorbital:bags'),image.shape)>0
 preservation=[]
 for region,values in actual['measurements'].items():
  for value in values:
   if value['id']=='bags':continue
   prior=next(v for v in old['measurements'][region] if v['id']==value['id']);key=region+':'+value['id'];same=value==prior and actual['maps'].get(key)==old['maps'].get(key);assert same,(prefix,key);preservation.append(dict(key=key,same=same))
 row=dict(sourceSHA256=source['sha256'],category=source['sampleCategory'],before=before['value'],after=bag['value'],beforeReason=before['limitationCode'],afterReason=bag['limitationCode'],samplingVersion=bag['components']['samplingSupportVersion'],matchesOffline=matchesOffline,anatomy=geometry,insideBandAndSelectedClosedCells=bandAndRegion,labelScope=dict(kind='partial-positive' if source['sampleCategory']=='development_positive_polygon' else 'reviewed-negative' if source['sampleCategory']=='natural_reviewed_negative' else 'transformed-regression',knownPixels=int(roi.sum()),activeWithinKnownPixels=int((active&roi).sum()),unknownOutsidePixels=int((~roi).sum())),nonBagPreservation=preservation)
 (OUT/(prefix+'-normal-api.json')).write_text(json.dumps(actual,ensure_ascii=False,indent=2),'utf8');rows.append(row);print(json.dumps({k:row[k] for k in ('sourceSHA256','before','after','afterReason','labelScope')}),flush=True)
def sample(prefix):return next(v for v in rows if v['sourceSHA256'].startswith(prefix))
acceptance=dict(visible20031BagSignal=sample('20031f35')['after']>0 and sample('20031f35')['anatomy']['activeAnalysisPixels']>0,annotated20031PolygonCaptured=sample('20031f35')['labelScope']['activeWithinKnownPixels']>0,positive36Preserved=sample('36e4010b')['after']>0 and sample('36e4010b')['labelScope']['activeWithinKnownPixels']>0,reviewedE0NoSignal=sample('e0ee9f0c')['after']==0 and sample('e0ee9f0c')['labelScope']['activeWithinKnownPixels']==0,allNonBagPreserved=all(v['same'] for r in rows for v in r['nonBagPreservation']),allMapsAnatomical=all(r['insideBandAndSelectedClosedCells'] for r in rows))
assert all(v for k,v in acceptance.items() if k!='annotated20031PolygonCaptured')
(OUT/'normal-api-comparison.json').write_text(json.dumps(dict(rows=rows,acceptance=acceptance),ensure_ascii=False,indent=2),'utf8');print(json.dumps(acceptance))
