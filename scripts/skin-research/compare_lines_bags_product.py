"""Same actual browser inputs, frozen delivered baseline, no hosted requests.

Reports raw support separately from UI/PNG quantization and only evaluates known
criterion-specific source support. Untagged areas are unknown.
"""
import copy,hashlib,importlib.util,json,sys
from pathlib import Path
import cv2,numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
import evaluate_periorbital_and_acne_comparative as audit
import appearance_analysis as A
OUT=ROOT/'audit-results/lines-bags-followup-20261012';OUT.mkdir(exist_ok=True)
def load(name,file):
 spec=importlib.util.spec_from_file_location(name,file);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
baseline=ROOT/'.runtime/lines-v4-frozen-20261012/baseline'
B=load('delivered_lines_v3',baseline/'appearance_analysis.py');I=load('delivered_bag_profile',baseline/'instant_appearance.py');B.instant_proxy=I.instant_proxy
manifest=json.loads((ROOT/'audit-results/skin-selected-20261011/manifest.json').read_text('utf8'))
ledger=json.loads((ROOT/'audit-results/skin-expanded-20261011/scope-v4-mask-data.json').read_text('utf8'))['rows']
prefixes=['a94f1646','02386f86','01955323',*audit.PREFIXES]
rows=[]
for prefix in prefixes:
 source=next(v for v in manifest['rows'] if v['sha256'].startswith(prefix))
 assert hashlib.sha256(Path(source['absolutePath']).read_bytes()).hexdigest()==source['sha256']
 f=OUT/(prefix+'-payload.json')
 if not f.exists():f=ROOT/'audit-results/bag-label-followup-20261012'/(prefix+'-v2-payload.json')
 p=json.loads(f.read_text('utf8'));shape=A.decode_photo(p['photo'])[0].shape
 results={};fields={}
 for name,mod in [('before',B),('after',A)]:
  original=mod.map_result;captured={}
  def capture(values,mask,region,criterion,*args,**kw):
   if region=='periorbital' and criterion in ('lines','bags'):
    captured[criterion]=(np.asarray(values).copy(),np.asarray(mask).copy(),args,kw)
   return original(values,mask,region,criterion,*args,**kw)
  mod.map_result=capture
  try:results[name]=mod.analyze_skin(copy.deepcopy(p))
  finally:mod.map_result=original
  fields[name]=captured
 after=results['after'];before=results['before'];preservation=[]
 for region,values in after['measurements'].items():
  for v in values:
   if region=='periorbital' and v['id'] in ('lines','bags'):continue
   old=next(x for x in before['measurements'][region] if x['id']==v['id']);key=region+':'+v['id']
   # Normalization is target-specific. Every non-target full row/map must match.
   same=v==old and after['maps'].get(key)==before['maps'].get(key)
   assert same,(prefix,key);preservation.append(key)
 row=dict(sourceSHA256=source['sha256'],sourceRelativePath=source['path'],split=source.get('split'),rights=source.get('rights'),inputSHA256=hashlib.sha256(f.read_bytes()).hexdigest(),conditions=p['conditions'],targets={},nonTargetExactMatches=preservation)
 for criterion in ('lines','bags'):
  scope=[x for x in ledger if x.get('sha256')==source['sha256'] and x.get('target')==criterion]
  positive=any(x.get('positivePixels',0)>0 for x in scope)
  known=audit.known_roi({'scopeLedgerRows':scope},shape,['acne','oil','dry','redness','tone','lines','dark','bags'],positive=positive)
  pair=dict(labelScope='partial-positive-polygons' if positive else 'engineering-reviewed-negative-ROI' if scope else 'exploratory-visual-control-no-pixel-label',knownSourcePixels=int(known.sum()),unlabeledOutsideIsUnknown=True)
  for name,mod in [('before',B),('after',A)]:
   response=results[name];v=next(x for x in response['measurements']['periorbital'] if x['id']==criterion);layer=response['maps'].get('periorbital:'+criterion)
   previous=audit.A;audit.A=mod
   try:geometry=audit.anatomy(layer,p,shape,criterion)
   finally:audit.A=previous
   native=audit.project_map_alpha(layer,shape)>0
   info=dict(value=v['value'],ui=audit.half_up_round(v['value']),reason=v['limitationCode'],quality=v['quality'],normalizationVersion=v['normalizationVersion'],samplingVersion=v['components'].get('samplingSupportVersion'),components=v['components'],geometry=geometry,activeWithinKnownSourcePixels=int((native&known).sum()))
   if criterion in fields[name]:
    vals,mask,args,kw=fields[name][criterion];raw=(vals>0)&mask
    # Production map_result owns origin/scale; map PNG quantizes alpha 0..100.
    info['rawAcceptedAnalysisPixels']=int(raw.sum());info['rawSupportSum']=float(vals[mask].sum());info['rawSupportPeak']=float(vals[mask].max()) if mask.any() else 0
    sampling_scale=args[3];sampling_origin=args[6] if len(args)>6 else kw.get('origin',(0,0))
    ys,xs=np.where(mask);rx,ry=int(xs.min()),int(ys.min());rw,rh=int(xs.max()-rx+1),int(ys.max()-ry+1)
    # Match the renderer's cropped map grid, fractional origin, rounded native
    # extent and step. A whole-frame resize has different raster cell boundaries.
    sw=max(1,round(rw/sampling_scale));sh=max(1,round(rh/sampling_scale))
    projected=cv2.resize(raw[ry:ry+rh,rx:rx+rw].astype('uint8'),(sw,sh),interpolation=cv2.INTER_NEAREST)>0
    native_raw=np.zeros(shape[:2],bool);sx=round(rx/sampling_scale+sampling_origin[0]);sy=round(ry/sampling_scale+sampling_origin[1])
    a,b=max(0,sx),max(0,sy);c,d=min(shape[1],sx+sw),min(shape[0],sy+sh)
    if c>a and d>b:native_raw[b:d,a:c]=projected[b-sy:d-sy,a-sx:c-sx]
    info['rawSupportWithinKnownSourcePixels']=int((native_raw&known).sum())
   pair[name]=info
   if name=='after':assert geometry['outsideEyeBandAnalysisPixels']==0 and geometry['outsideSelectedRegionAnalysisPixels']==0
  row['targets'][criterion]=pair
 (OUT/(prefix+'-baseline.json')).write_text(json.dumps(before,ensure_ascii=False),'utf8')
 (OUT/(prefix+'-offline.json')).write_text(json.dumps(after,ensure_ascii=False),'utf8')
 rows.append(row);print(json.dumps({'source':prefix,**{c:{n:pair[c][n]['value'] for n in ('before','after')} for c in ('lines','bags') for pair in [row['targets']]}}),flush=True)
(OUT/'same-input-comparison.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),'utf8')
