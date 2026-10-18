"""Stage attribution, fixed optical labels and exact source coordinates; no fit."""
import os
for key in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[key]='1'
import base64,json,sys
from pathlib import Path
import cv2,numpy as np
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/material-runtime-followup-20261013';PREV=ROOT/'audit-results/native-material-contour-20261013'
sys.path.insert(0,str(ROOT/'services/core-api'))
import appearance_analysis as A,material_component_features as M,native_dry_path as N
from native_flake_support import proposal_tile
from component_flake_gate import masks
cv2.setNumThreads(1)
head=json.loads((PREV/'encoder-material-head.json').read_text('utf8'));enc=M.OnnxMaterialEncoder(OUT/'material-encoder.onnx',OUT/'encoder-parity.json')
controls=json.loads((ROOT/'audit-results/dry-sag-component-followup-20261013/object-labels.json').read_text('utf8'))['controls'];before=json.loads((ROOT/'audit-results/native-dry-scale-20261013/independent-v3-comparison.json').read_text('utf8'))['rows'];cases=[]
corrected=json.loads((PREV/'material-encoder-scale-corrected.json').read_text('utf8'))
for control in controls:
    if control['controlIndex'] not in [0,9] and control['kind']!='raw':continue
    source=cv2.imread(control['sourcePath']);comp=before[control['controlIndex']];a,b=comp['cropOrigin'];x,y,w,h=control['roi'];metric=comp['referenceSpan']/640;pad=max(64,int(np.ceil(40*metric)));crop=source[b:min(source.shape[0],y+h+pad),a:min(source.shape[1],x+w+pad)];known,objects=masks(source.shape[:2],control)
    for factor in [1.,.5]:
        im=crop if factor==1 else cv2.resize(crop,None,fx=.5,fy=.5,interpolation=cv2.INTER_AREA);field=proposal_tile(im,metric*factor,pixel_density=factor);ids,rows=M.describe(im,field,metric*factor)
        refs=next(r for r in corrected['rows'] if r['controlIndex']==control['controlIndex'] and r['factor']==factor)
        # Only already-observed material components are encoded for attribution.
        object_rows=[];preview=im.copy()
        for obj in objects:
            if obj['label']!='visible-material':continue
            mask=obj['mask'][b:b+crop.shape[0],a:a+crop.shape[1]]>0
            if factor!=1:mask=cv2.resize(mask.astype(np.uint8),(im.shape[1],im.shape[0]),interpolation=cv2.INTER_NEAREST)>0
            touch=[row for row in rows if ((ids==row['componentId'])&mask).any()];component_rows=[]
            for row in touch:
                crops,boxes=M.component_crops(im,row,metric*factor,factor);visual=enc.extract(crops).reshape(1,2560);features=np.c_[visual,np.array(row['geometry'])[None,:]];p=float(M.predict(features,head)[0]);z=(features[0]-head['mean'])/head['std'];contrib=z*np.array(head['coefficients'])
                component_rows.append(dict(id=row['componentId'],rectSource=[a+row['rect'][0]/factor,b+row['rect'][1]/factor,row['rect'][2]/factor,row['rect'][3]/factor],candidatePixelsInside=int(((ids==row['componentId'])&mask).sum())/(factor*factor),probability=p,accepted=p>=.5,logitParts=dict(near=float(contrib[:1280].sum()),context=float(contrib[1280:2560].sum()),geometry=float(contrib[2560:].sum()),intercept=head['intercept']),cropBoxes=boxes))
            previous=next(o for o in refs['objects'] if o['index']==obj['index']);object_rows.append(dict(index=obj['index'],partialLabel='visible-material',stages=previous['fields'],components=component_rows,etiology='UNKNOWN'))
            preview[mask]=(preview[mask]*.7+np.array([100,0,100])*.3).astype(np.uint8)
        # Plot proposal and actual retained classifier support, never paint labels.
        gated=np.load(PREV/f'C{control["controlIndex"]:02d}-scale{factor}-gated-field-crop-v2.npz')['field'];preview[field>.04]=(preview[field>.04]*.6+np.array([0,200,200])*.4).astype(np.uint8);preview[gated>.04]=(preview[gated>.04]*.4+np.array([0,255,0])*.6).astype(np.uint8)
        cv2.imwrite(str(OUT/f'C{control["controlIndex"]:02d}-{factor}-stage.png'),preview);cases.append(dict(control=control['controlIndex'],source=control['sourceSHA256'],split=control['split'],factor=factor,objects=object_rows))
        print(json.dumps(dict(control=control['controlIndex'],factor=factor,objects=len(object_rows))),flush=True)
actual=[]
paths=[ROOT/'audit-results/dry-sag-component-followup-20261013/product/9bab7ab2/9bab7ab2-automatic-payload.json',ROOT/'audit-results/dry-sag-source-census-20261013/product/24031977/attempt-2/24031977-automatic-payload.json']
for path in paths:
    payload=json.loads(path.read_text('utf8'));photo,_=A.decode_photo(payload['photo']);captured={}
    def observe(image,field,metric):
        captured.update(image=image.copy(),field=field.copy(),metric=metric)
        return field,{'classifierVersion':'diagnostic-proposal-only'}
    raw=N.analyze_native_dry(payload,observe);origin=raw['nativeMetadata']['cropOrigin'];ids,components=M.describe(captured['image'],captured['field'],captured['metric']);details=json.loads((OUT/(path.name[:8]+'-components.json')).read_text('utf8'));result=json.loads((OUT/(path.name[:8]+'-native-result.json')).read_text('utf8'));accepted=np.zeros(photo.shape[:2],bool)
    for layer in result['maps'].values():
        rgba=cv2.imdecode(np.frombuffer(base64.b64decode(layer['dataUrl'].split(',')[1]),np.uint8),cv2.IMREAD_UNCHANGED);ys,xs=np.where(rgba[:,:,3]>0);accepted[ys+int(layer['y']),xs+int(layer['x'])]=True
    targets=[[[212,326],[281,326],[281,350],[212,350]]] if path.name.startswith('9bab') else [[[58,243],[70,244],[87,258],[93,285],[83,306],[71,286]],[[254,242],[279,245],[295,265],[306,292],[286,297],[267,272]]]
    preview=photo.copy();target_rows=[]
    for poly in targets:
        mask=np.zeros(photo.shape[:2],np.uint8);cv2.fillPoly(mask,[np.asarray(poly,np.int32)],1);local=mask[origin[1]:origin[1]+ids.shape[0],origin[0]:origin[0]+ids.shape[1]]>0
        touched=[r for r in details if ((ids==r['componentId'])&local).any()];count=int(((captured['field']>.04)&local).sum());target_rows.append(dict(polygon=poly,proposalPixels=count,acceptedPixels=int((accepted&(mask>0)).sum()),components=touched,stage='classifier' if count else 'proposal/exclusion'))
        cv2.polylines(preview,[np.asarray(poly,np.int32)],True,(255,0,255),1)
    ys,xs=np.where(captured['field']>.04);sy=ys+origin[1];sx=xs+origin[0];preview[sy,sx]=(preview[sy,sx]*.6+np.array([0,200,200])*.4).astype(np.uint8);preview[accepted]=(preview[accepted]*.4+np.array([0,255,0])*.6).astype(np.uint8);cv2.imwrite(str(OUT/(path.name[:8]+'-source-stage.png')),preview)
    actual.append(dict(source=path.name[:8],targets=target_rows,proposalFrozen=True,sourceEtiology='UNKNOWN',outsideReviewedTargets='UNKNOWN'))
(OUT/'failure-attribution.json').write_text(json.dumps(dict(optical=cases,product=actual,classifierRefitted=False,validationAddedToTrain=False),indent=2),'utf8')
