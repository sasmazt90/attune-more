"""Full label-blind native classifier on pinned real browser/API inputs."""
import os
os.environ['OMP_NUM_THREADS']='1';os.environ['MKL_NUM_THREADS']='1';os.environ['OPENBLAS_NUM_THREADS']='1'
import base64,hashlib,json,sys,time
from pathlib import Path
import cv2,numpy as np
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/native-material-contour-20261013';sys.path.insert(0,str(ROOT/'services/core-api'))
from native_dry_path import analyze_native_dry
from material_component_features import FrozenMaterialEncoder,filter_material_support
import appearance_analysis as A
cv2.setNumThreads(1)
head=json.loads((OUT/'encoder-material-head.json').read_text('utf8'));assert head['accepted'] is False
encoder=FrozenMaterialEncoder(ROOT/'audit-results/focused-skin-20261010/pretrained/efficientnet_b0_rwightman-7f5810bc.pth.safetensors')
rows=[];previous=json.loads((ROOT/'audit-results/native-dry-scale-20261013/native-staging-path.json').read_text('utf8'))['rows']
paths=list((ROOT/'audit-results/dry-sag-component-followup-20261013/product').glob('*/*-automatic-payload.json'))+[ROOT/'audit-results/dry-sag-source-census-20261013/product/24031977/attempt-2/24031977-automatic-payload.json',ROOT/'audit-results/native-dry-scale-20261013/e1646fda-native-payload.json']
for path in paths:
    payload=json.loads(path.read_text('utf8'));assert not payload['hostedProcessingConsent'];start=time.monotonic();baseline=A.analyze_skin(payload);result=analyze_native_dry(payload,lambda image,field,metric:filter_material_support(image,field,metric,encoder,head));bgr,_=A.decode_photo(payload['photo']);scores=[];maps=[]
    proposal=next(r for r in previous if r['source']==path.name[:8])
    for region,row in result['measurements'].items():
        old=next(v for v in baseline['measurements'][region] if v['id']=='dry');unfiltered=next(v for v in proposal['scores'] if v['region']==region);scores.append(dict(region=region,normalV3=old['value'],proposalOnly=unfiltered['nativeStaging'],encoder=row['value'],reason=row['limitationCode'],acceptedSourcePixels=row['components']['acceptedMaterialSourcePixels'],visibleSourcePixels=row['evaluatedArea']['sourcePixels']))
        if row['value'] is None:continue
        layer=result['maps'][region+':dry'];rgba=cv2.imdecode(np.frombuffer(base64.b64decode(layer['dataUrl'].split(',')[1]),np.uint8),cv2.IMREAD_UNCHANGED);active=rgba[:,:,3]>0;valid=cv2.imdecode(np.frombuffer(base64.b64decode(layer['validMaskUrl'].split(',')[1]),np.uint8),cv2.IMREAD_UNCHANGED)>0
        assert not (active&~valid).any() and layer['step']==1;ys,xs=np.where(active);sx=xs+int(layer['x']);sy=ys+int(layer['y']);mesh=A.closed_surface_mask(bgr.shape[:2],payload['meshes'][region],1);assert mesh[sy,sx].all()
        assert int(active.sum())==row['components']['acceptedMaterialSourcePixels'] and row['value']==100*active.sum()/max(1,valid.sum())
        preview=bgr.copy();preview[sy,sx]=(.4*preview[sy,sx]+.6*np.array([0,0,255])).astype(np.uint8);cv2.imwrite(str(OUT/(path.name[:8]+'-'+region+'-encoder.png')),preview)
        maps.append(dict(region=region,activePixels=int(active.sum()),outsideMesh=int((~mesh[sy,sx]).sum()),step=layer['step'],origin=[layer['x'],layer['y']]))
    (OUT/(path.name[:8]+'-encoder-native-result.json')).write_text(json.dumps(result),'utf8')
    rows.append(dict(source=path.name[:8],payloadSHA256=hashlib.sha256(path.read_bytes()).hexdigest(),scores=scores,maps=maps,metadata=result['nativeMetadata'],seconds=time.monotonic()-start,normalProductEnabled=False))
    print(json.dumps(dict(source=path.name[:8],seconds=rows[-1]['seconds'],scores=scores)),flush=True)
(OUT/'encoder-native-product-comparison.json').write_text(json.dumps(dict(rows=rows,photoSpecificRules=False,labelsAsInferenceInput=False,normalProductEnabled=False),indent=2),'utf8')
