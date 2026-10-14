"""Check native map numerators/denominators from real saved HTTP results."""
import json,base64,io
from pathlib import Path
from heavy_job_lease import HeavyJobLease
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/dryness-integration-v2-20261014'
with HeavyJobLease('CDC-dry-native-PNG-support',peak_mib=150,minimum_available_mib=600) as lease:
 from PIL import Image,ImageChops
 checks=[]
 for name in ['cold-normal-camera','warm-normal-camera','camera-1280x960','24031977','dedbb492']:
  data=json.loads((OUT/(name+'-api.json')).read_text('utf8'))
  for rows in [*data['measurements'].values(),data['general']['measurements']]:
   row=next(r for r in rows if r['id']=='dry')
   if row['value'] is None:
    assert row['localMap'] is None;continue
   layer=data['maps'][row['localMap']['key']];alpha=Image.open(io.BytesIO(base64.b64decode(layer['dataUrl'].split(',')[1]))).getchannel('A');valid=Image.open(io.BytesIO(base64.b64decode(layer['validMaskUrl'].split(',')[1]))).convert('L')
   active=sum(n for i,n in enumerate(alpha.histogram()) if i>0);eligible=sum(n for i,n in enumerate(valid.histogram()) if i>0)
   assert active==row['components']['acceptedMaterialSourcePixels'] and eligible==row['components']['uniqueVisibleSourcePixels']
   assert ImageChops.multiply(alpha,ImageChops.invert(valid)).getbbox() is None
   assert layer['step']==1 and 0<=layer['x']<layer['x']+layer['width']<=data['sourceWidth'] and 0<=layer['y']<layer['y']+layer['height']<=data['sourceHeight']
   assert abs(row['value']-100*active/eligible)<1e-10
   checks.append(dict(source=name,region=row['region'],activeSourcePixels=active,visibleSourcePixels=eligible,value=row['value'],outsideEligibleActivePixels=0,sourceCoordinatesWithinFrame=True))
 result=dict(checks=checks,passed=True,actualSavedHTTP=True,clinicalPixelLabelsInvented=False,resource=lease.receipt());(OUT/'native-map-pixel-checks.json').write_text(json.dumps(result,indent=2),'utf8');print(json.dumps(dict(checked=len(checks),passed=True)))
