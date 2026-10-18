"""Finite source-coordinate fold/contour diagnosis. No production changes."""
import base64,hashlib,inspect,json,sys,urllib.request
from pathlib import Path
import cv2,numpy as np
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/native-dry-scale-20261013';OUT.mkdir(exist_ok=True)
sys.path.insert(0,str(ROOT/'services/core-api'))
import appearance_analysis as A
import instant_appearance as I
cv2.setNumThreads(1)
original=I.curve_profile;captured=[];source=None

def scalar(q):
    return {k:q[k] for k in ['strength','edge','continuity','coverage','trackingResidual','trackingStatus','rawFoldSamples','trackedFoldSamples','trackingSegments'] if k in q}

def capture(gray,eligible,guide,normal,offsets,width,center_support=None,observed_fold_runs=False):
    q=original(gray,eligible,guide,normal,offsets,width,center_support,observed_fold_runs)
    caller=inspect.currentframe().f_back;region=caller.f_locals.get('region')
    if q is None or region not in ['chin','rightCheek','leftCheek']:return q
    scale=caller.f_locals['scale'];origin=np.asarray(caller.f_locals['origin']);x,y=map(int,origin)
    # These inherited support grids deliberately isolate photometric resizing.
    # Exact native anatomy is tested by the separate native dryness path.
    face=width/scale;points=np.asarray([[p['x'],p['y']] for m in payload['meshes'].values() for p in m['points']]);pad=max(20,abs(payload['landmarks'][454]['x']-payload['landmarks'][234]['x'])*source.shape[1]*.1)
    x1=min(source.shape[1],int(points[:,0].max()+pad+1));y1=min(source.shape[0],int(points[:,1].max()+pad+1));crop=source[y:y1,x:x1]
    native_gray=cv2.cvtColor(crop,cv2.COLOR_BGR2GRAY).astype(np.float32)/255
    mask=cv2.resize(eligible.astype(np.uint8),(crop.shape[1],crop.shape[0]),interpolation=cv2.INTER_NEAREST)>0
    centers=cv2.resize(center_support.astype(np.uint8),(crop.shape[1],crop.shape[0]),interpolation=cv2.INTER_NEAREST)>0
    runs=[]
    for factor in [1.,.5]:
        ng=native_gray if factor==1 else cv2.resize(native_gray,None,fx=factor,fy=factor,interpolation=cv2.INTER_AREA)
        em=mask if factor==1 else cv2.resize(mask.astype(np.uint8),(ng.shape[1],ng.shape[0]),interpolation=cv2.INTER_NEAREST)>0
        cm=centers if factor==1 else cv2.resize(centers.astype(np.uint8),(ng.shape[1],ng.shape[0]),interpolation=cv2.INTER_NEAREST)>0
        nq=original(ng,em,np.asarray(guide)/scale*factor,normal,offsets,face*factor,cm,observed_fold_runs)
        runs.append(dict(factor=factor,profile=scalar(nq) if nq else None))
    # Actual rows and paired-brightness response, including observed below-floor
    # rows. Nothing below the floor is treated as detected support.
    g=np.asarray(guide);distance=np.r_[0,np.cumsum(np.linalg.norm(np.diff(g,axis=0),axis=1))];t=np.linspace(0,distance[-1],64);line=np.column_stack([np.interp(t,distance,g[:,j]) for j in [0,1]])
    coords=line[:,None,:]+np.asarray(offsets)[None,:,None]*width/320*normal
    sample=cv2.remap(gray,coords[:,:,0].astype(np.float32),coords[:,:,1].astype(np.float32),cv2.INTER_LINEAR);sample=cv2.GaussianBlur(sample,(1,3),0)
    validity=cv2.remap(eligible.astype(np.uint8),coords[:,:,0].astype(np.float32),coords[:,:,1].astype(np.float32),cv2.INTER_NEAREST)>0
    cvalid=cv2.remap(center_support.astype(np.uint8),coords[:,:,0].astype(np.float32),coords[:,:,1].astype(np.float32),cv2.INTER_NEAREST)>0
    usable=validity[:,:-4]&validity[:,2:-2]&validity[:,4:]&cvalid[:,2:-2]
    valley=np.minimum(sample[:,:-4]-sample[:,2:-2],sample[:,4:]-sample[:,2:-2]);valley=np.where(usable,np.maximum(valley,0),-1);best=valley.argmax(1);contrast=np.maximum(valley[np.arange(64),best],0)
    captured.append(dict(region=region,side=caller.f_locals['side'],analysisScale=scale,sourceOrigin=origin.tolist(),sourceFaceWidth=face,product=scalar(q),nativeSampling=runs,
        scaleDiagnostic='same inherited eligible/context support; only photometric source grid changes',sourceGuide=(np.asarray(guide)/scale+origin).tolist(),sourceSelected=[p.tolist() if np.isfinite(p).all() else None for p in q['tracked']/scale+origin],
        observed=q['observedSamples'].tolist(),accepted=q['support'].tolist(),pairedContrast=contrast.tolist(),pairedFloor=I.CONSTANTS['foldFloor'],nativeBandMask=centers))
    return q

def main():
    global payload,captured,source
    cases=[];selection=json.loads((OUT/'targeted-sag-selection.json').read_text('utf8'))
    inputs=[]
    for prefix in ['f90e68f8','64b02ede']:
        path=ROOT/'audit-results/dry-sag-source-census-20261013/product'/prefix/(prefix+'-automatic-payload.json');inputs.append((prefix,json.loads(path.read_text('utf8')),path,'previous actual automatic product input'))
    for row in selection:
        prefix=row['sha256'][:8];probe=json.loads((OUT/'sag-targeted'/(prefix+'-probe.json')).read_text('utf8'));s=probe['snapshot']
        p=dict(processingConsent=True,hostedProcessingConsent=False,photo=s['dataUrl'],photoId=s['photoId'],pose=s['angle'],meshes=s['meshes'],exclusions=s['exclusions'],landmarks=s['landmarks'],qualityValid=probe['quality']['isValid'],conditions=probe['conditions'],temporal=[s['landmarks']]*3)
        path=OUT/'sag-targeted'/(prefix+'-payload.json');path.write_text(json.dumps(p),'utf8');inputs.append((prefix,p,path,'bounded previously reviewed selection; fresh real browser MP/snapshot'))
    I.curve_profile=capture
    try:
        for prefix,p,path,provenance in inputs:
            payload=p;source,_=A.decode_photo(p['photo']);captured=[];result=A.analyze_skin(p)
            if prefix not in ['f90e68f8','64b02ede']:
                api_path=OUT/'sag-targeted'/(prefix+'-api.json')
                if api_path.exists():actual=json.loads(api_path.read_text('utf8'))
                else:
                    request=urllib.request.Request('http://127.0.0.1:8000/api/local-health/skin',json.dumps(p).encode(),{'Content-Type':'application/json'})
                    actual=json.loads(urllib.request.urlopen(request,timeout=45).read())
                assert all(actual[k]==result[k] for k in ['measurements','maps','contours']),'Normal API/source mismatch'
                assert actual.get('general',{}).get('measurements')==result.get('general',{}).get('measurements'),'Normal API/general mismatch'
                api_path.write_text(json.dumps(actual),'utf8')
            image=source.copy();profile_rows=[];target=None
            if prefix=='dedbb492':
                # Engineering visible pleat on the submental/neck skin. This is
                # NOT a clinical sag label or a normal mentolabial crease.
                polygon=[[286,367],[305,362],[330,365],[353,381],[352,410],[329,420],[310,414],[292,395]]
                target=np.zeros(source.shape[:2],np.uint8);cv2.fillPoly(target,[np.asarray(polygon,np.int32)],1);cv2.polylines(image,[np.asarray(polygon,np.int32)],True,(255,0,255),2)
            for profile in captured:
                mask=profile.pop('nativeBandMask');x,y=map(int,profile['sourceOrigin']);boundary=cv2.findContours(mask.astype(np.uint8),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)[0]
                for contour in boundary:cv2.drawContours(image,[contour+np.array([[[x,y]]])],-1,(255,180,0),1)
                for xy,seen,accepted in zip(profile['sourceSelected'],profile['observed'],profile['accepted']):
                    if xy is not None:cv2.circle(image,tuple(np.rint(xy).astype(int)),2,(0,255,0) if accepted else (0,190,255) if seen else (0,0,255),-1)
                if target is not None:profile['engineeringTargetBandOverlapPixels']=int((mask&(target[y:y+mask.shape[0],x:x+mask.shape[1]]>0)).sum())
                profile_rows.append(profile)
            if target is not None:
                mesh=A.closed_surface_mask(source.shape[:2],p['meshes']['chin'],1,(0,0));points=np.asarray([[v['x']*source.shape[1],v['y']*source.shape[0]] for v in p['landmarks']]);axis=points[263]-points[33];axis/=np.linalg.norm(axis);face=abs((points[454]-points[234])@axis)
                corridor=np.zeros(source.shape[:2],np.uint8)
                for indices in [[170,208,199,428,395],[172,136,150,152,379,365,397]]:cv2.polylines(corridor,[np.rint(points[indices]).astype(np.int32)],False,1,max(1,int(np.ceil(21*face/320))))
                band=mesh&(corridor>0);cv2.drawContours(image,cv2.findContours(band.astype(np.uint8),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)[0],-1,(255,180,0),1)
                target_info=dict(polygon=polygon,label='visible-submental-neck-pleat',engineeringNotClinical=True,area=int(target.sum()),chinMeshOverlapPixels=int((mesh&(target>0)).sum()),chinTargetBandOverlapPixels=int((band&(target>0)).sum()),unknownOutsideTarget=True)
            else:target_info=None
            cv2.imwrite(str(OUT/(prefix+'-sag-source-scope.png')),image)
            rows=[dict(region=region,value=v['value'],reason=v['limitationCode'],boundary=v['components'].get('boundary'),sides=v['components'].get('sides')) for region,values in result['measurements'].items() for v in values if v['id']=='sag']
            cases.append(dict(source=prefix,payloadSHA256=hashlib.sha256(path.read_bytes()).hexdigest(),photoId=p['photoId'],provenance=provenance,qualityValid=p['qualityValid'],conditions=p['conditions'],results=rows,profiles=profile_rows,engineeringTarget=target_info))
            print(json.dumps(dict(source=prefix,results=[{k:v for k,v in r.items() if k in ['region','value','reason']} for r in rows],chin=[dict(product=r['product'],nativeSampling=r['nativeSampling']) for r in profile_rows if r['region']=='chin'],target=target_info)),flush=True)
    finally:I.curve_profile=original
    (OUT/'sag-source-scope.json').write_text(json.dumps(dict(cases=cases,productionChanged=False,contourOnlyExcludedByFormula=True,formulaEvidence='fold values multiplied by paired-edge and nearest independent boundary support; boundary alone cannot create signal',selectionWasNotByScore=True),indent=2),'utf8')

if __name__=='__main__':main()
