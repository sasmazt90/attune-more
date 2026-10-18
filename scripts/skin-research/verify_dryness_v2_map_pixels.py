"""Check native map numerators/denominators from real saved HTTP results."""
import json,base64,io
from pathlib import Path
from heavy_job_lease import HeavyJobLease
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/dryness-integration-v2-20261014'
with HeavyJobLease('CDC-dry-native-PNG-support',peak_mib=150,minimum_available_mib=600) as lease:
 from PIL import Image,ImageChops
 checks=[]
 names=['cold-normal-camera','warm-normal-camera','camera-1280x960','24031977','dedbb492','new-camera-normal-result','nonzero-camera-result']
 unions=[]
 for name in names:
  path=OUT/(name+'.json' if name.endswith('-result') else name+'-api.json');data=json.loads(path.read_text('utf8'));union_active=Image.new('L',(data['sourceWidth'],data['sourceHeight']));union_visible=union_active.copy();overview=None
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
   source_active=Image.new('L',union_active.size);source_visible=source_active.copy();source_active.paste(alpha.point(lambda value:255 if value else 0),(int(layer['x']),int(layer['y'])));source_visible.paste(valid,(int(layer['x']),int(layer['y'])))
   if row['region']=='overview':overview=(source_active,source_visible)
   else:union_active=ImageChops.lighter(union_active,source_active);union_visible=ImageChops.lighter(union_visible,source_visible)
  if overview is not None:
   active_equal=ImageChops.difference(union_active,overview[0]).getbbox() is None;visible_equal=ImageChops.difference(union_visible,overview[1]).getbbox() is None;assert active_equal and visible_equal
   unions.append(dict(source=name,acceptedUnionEqualsOverview=active_equal,visibleDenominatorUnionEqualsOverview=visible_equal))

 result=dict(checks=checks,unions=unions,passed=True,actualSavedHTTP=True,clinicalPixelLabelsInvented=False,resource=lease.receipt());(OUT/'native-map-pixel-checks.json').write_text(json.dumps(result,indent=2),'utf8');print(json.dumps(dict(checked=len(checks),passed=True)))
