"""Same real automatic payload: trace support, isolated candidate, normal API.

No source/production rewrite. Reviewed boxes assert local presence only;
their pixels and all outside areas are not full segmentation labels.
"""
import base64,hashlib,json,sys,urllib.request
from pathlib import Path
import cv2,numpy as np
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/dry-sag-source-census-20261013'
sys.path.insert(0,str(ROOT/'services/core-api'))
import appearance_analysis as A
from flake_local_classifier import candidate_field,OUT as CONTROL
cv2.setNumThreads(1)
def decode(url):return cv2.imdecode(np.frombuffer(base64.b64decode(url.split(',')[1]),np.uint8),cv2.IMREAD_UNCHANGED)
def api(payload):
    assert not payload['hostedProcessingConsent']
    request=urllib.request.Request('http://localhost:8000/api/local-health/skin',json.dumps(payload).encode(),{'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=45) as response:return json.load(response)
def scalar(result):
    groups=[*result['measurements'].items()]
    if result.get('general'):groups.append(('overview',result['general']['measurements']))
    return {region+':'+v['id']:{key:v.get(key) for key in ('value','quality','limitationCode','normalizationVersion','modelHash')} for region,values in groups for v in values}
def geometry(payload,bgr):
    h,w=bgr.shape[:2];face=abs(payload['landmarks'][454]['x']-payload['landmarks'][234]['x'])*w;scale=min(1,320/max(face,1))
    points=np.array([[v['x'],v['y']] for mesh in payload['meshes'].values() for v in mesh['points']],np.float32);pad=max(20,face*.1)
    x0=max(0,int(points[:,0].min()-pad));y0=max(0,int(points[:,1].min()-pad));x1=min(w,int(points[:,0].max()+pad+1));y1=min(h,int(points[:,1].max()+pad+1))
    return scale,(x0,y0),(x1,y1)
def visual(payload,response,prefix,tag=''):
    bgr=decode(payload['photo'])[:,:,:3];h,w=bgr.shape[:2];scale,origin,end=geometry(payload,bgr)
    images=[];maps=[]
    for key,layer in response['maps'].items():
        if key.endswith(':dry') or key.endswith(':sag'):
            rgba=decode(layer['dataUrl']);known=decode(layer['validMaskUrl'])>0;active=rgba[:,:,3]>0
            region=layer['region'];mask=A.closed_surface_mask((h,w),payload['meshes'][region],1) if region!='overview' else np.logical_or.reduce([A.closed_surface_mask((h,w),m,1) for m in payload['meshes'].values()])
            source_x=layer['x']+np.arange(layer['width'])*layer['step'];source_y=layer['y']+np.arange(layer['height'])*layer['step']
            yy,xx=np.meshgrid(source_y,source_x,indexing='ij');ix=np.clip(np.rint(xx).astype(int),0,w-1);iy=np.clip(np.rint(yy).astype(int),0,h-1)
            # Rasterization at the source grid can differ by one source cell.
            outside=int((active&~mask[iy,ix]).sum());tolerance=cv2.dilate(mask.astype('uint8'),np.ones((5,5),np.uint8))>0
            far=int((active&~tolerance[iy,ix]).sum());assert not far,(prefix,key,far)
            im=bgr[:,:,::-1].copy();im[iy[active],ix[active]]=[255,30,30]
            for mesh in ([payload['meshes'][region]] if region!='overview' else payload['meshes'].values()):
                p=np.array([[v['x'],v['y']] for v in mesh['points']]);
                for a,b in mesh['edges']:cv2.line(im,tuple(np.rint(p[a]).astype(int)),tuple(np.rint(p[b]).astype(int)),(0,180,220),1)
            image=Image.fromarray(im);d=ImageDraw.Draw(image);d.text((4,4),f'{prefix} {tag}{key} active grid={int(active.sum())}',fill='red');image.save(OUT/'product'/prefix/(tag+key.replace(':','-')+'-support.png'))
            maps.append(dict(key=key,activeMapGridCells=int(active.sum()),knownMapGridCells=int(known.sum()),activeOutsideValidMask=int((active&~known).sum()),activeOutsideSourceClosedCells=outside,activeOutsideTwoPixelRasterTolerance=far,origin=[layer['x'],layer['y']],step=layer['step'],sourcePhotoMatches=layer['photoId']==payload['photoId'],outsideAnnotation='unknown'))
    return maps
rows=[]
cases=[('f90e68f8',False),('40d781eb',False),('64b02ede',False),('99f82af5',False),('24031977',True)]
for prefix,attempt in cases:
    folder=OUT/'product'/prefix
    if attempt:folder=folder/'attempt-2'
    payload=json.loads((folder/(prefix+'-automatic-payload.json')).read_text('utf8'))
    old=json.loads((folder/(prefix+'-automatic-api.json')).read_text('utf8'));fresh=api(payload);same=scalar(old)==scalar(fresh);assert same,(prefix,'numerical behavior changed')
    (folder/(prefix+'-runtime-api.json')).write_text(json.dumps(fresh,ensure_ascii=False),'utf8')
    bgr=decode(payload['photo'])[:,:,:3];scale,origin,end=geometry(payload,bgr);observations=[];original=A.instant_proxy
    def tracked(*args,**kwargs):
        value,components,signal,lines,limitation=original(*args,**kwargs)
        if args[3] in ('rightCheek','leftCheek','chin'):
            samples=components.get('_samplingCenters',[]);observations.append(dict(region=args[3],value=value,reason=limitation,acceptedSourceCenters=[[float(x/scale+origin[0]),float(y/scale+origin[1]),float(v)] for x,y,v in samples],anatomicalEvidenceLines=lines))
        return value,components,signal,lines,limitation
    A.instant_proxy=tracked
    local=A.analyze_skin(payload);A.instant_proxy=original;assert scalar(local)==scalar(fresh)
    traced=bgr[:,:,::-1].copy()
    for obs in observations:
        for x,y,v in obs['acceptedSourceCenters']:cv2.circle(traced,(round(x),round(y)),2,(255,30,30) if v>0 else (220,170,0),-1)
    Image.fromarray(traced).save(OUT/'product'/prefix/'accepted-contour-centers.png')
    row=dict(sourcePrefix=prefix,photoId=payload['photoId'],normalAPIScalars=scalar(fresh),samePayloadNumericBehaviorPreserved=same,modelRuntime=fresh['modelRuntime'],anatomicalMaps=visual(payload,fresh,prefix),acceptedContourCenters=observations)
    if prefix=='24031977':
        model=json.loads((CONTROL/'staging-patch-tree.json').read_text('utf8'));native=candidate_field(cv2.cvtColor(bgr[origin[1]:end[1],origin[0]:end[0]],cv2.COLOR_BGR2GRAY),model)
        function=A.compute_dryness_signal
        def candidate(gray,*args,**kwargs):
            values=list(function(gray,*args,**kwargs));field=cv2.resize(native,(gray.shape[1],gray.shape[0]),interpolation=cv2.INTER_AREA);values[0]=field;values[1]=field;return tuple(values)
        A.compute_dryness_signal=candidate
        stage=A.analyze_skin(payload);A.compute_dryness_signal=function
        row['isolatedNativeCandidate']=dict(productionActivated=False,modelSHA256=hashlib.sha256((CONTROL/'staging-patch-tree.json').read_bytes()).hexdigest(),method='staging-native-optical-patch-tree-v1 with unchanged anatomical/exclusion/eligible-island support',values=scalar(stage),sameDryDenominators=all(v['evaluatedArea']==next(a for a in fresh['measurements'][region] if a['id']=='dry')['evaluatedArea'] for region,values in stage['measurements'].items() for v in values if v['id']=='dry'),mapSupport=visual(payload,stage,prefix,tag='candidate-'))
        # Local presence boxes fixed by visual source inspection, not full masks.
        roi_boxes=[[130,285,48,105],[265,280,62,125],[195,432,52,22]]
        row['reviewedPresenceROIs']=dict(boxes=roi_boxes,authority='engineering visible peeling-material presence, etiology unconfirmed',allPixelsLabeled=False,outside='unknown',pixelDice=None)
        (folder/'isolated-candidate-api.json').write_text(json.dumps(stage,ensure_ascii=False),'utf8')
    rows.append(row)
(OUT/'product-support-receipt.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),'utf8');print(json.dumps([dict(source=r['sourcePrefix'],preserved=r['samePayloadNumericBehaviorPreserved'],runtime=r['modelRuntime']['degrees']) for r in rows]))
