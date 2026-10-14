"""Frozen ImageNet material-crop features; never a skin-type prediction head.

The proposal pixels are unchanged. Crop resizing is encoder input sampling,
not a claim of recovered source detail. This module is research-only until a
separate admission receipt authorizes a normal product selector.
"""
from pathlib import Path
import hashlib,json,time
import cv2,numpy as np

ENCODER_SHA='e50c812a76cb5003f426ae35a5b9aba4d8d8dd50a9f822d2a64046bac310143a'
GEOMETRY=['logReferenceArea','elongation','fill','circularity','solidity','ringContrast','gradientDirectionCoherence','darkAdjacentFraction','poreCoreFraction','poreCoreReferenceArea','ringChromaDelta','interiorLumaVariation']
MEAN=np.array([.485,.456,.406],np.float32)[None,None,:]
STD=np.array([.229,.224,.225],np.float32)[None,None,:]

def describe(image,field,metric,reference_support=None):
    """Scale-aware geometry and non-self ring statistics of unchanged proposals."""
    s=max(.125,float(metric));gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY);g=gray.astype(np.float32)/255;active=field>.04
    background_excluded=active if reference_support is None else np.asarray(reference_support,bool)
    if background_excluded.shape!=active.shape:raise ValueError('INVALID_REFERENCE_SUPPORT')
    n,labels,stats,centroids=cv2.connectedComponentsWithStats(active.astype(np.uint8),8)
    k=max(3,2*int(round(3*s))+1);dark=cv2.morphologyEx(gray,cv2.MORPH_BLACKHAT,np.ones((k,k),np.uint8))>35
    dn,di,ds,_=cv2.connectedComponentsWithStats(dark.astype(np.uint8),8);core_ids=[i for i in range(1,dn) if ds[i,4]<=20*s*s and max(ds[i,2],ds[i,3])/max(1,min(ds[i,2],ds[i,3]))<=3.3]
    core_lookup=np.zeros(dn,bool);core_lookup[core_ids]=True;cores=core_lookup[di];adjacent=cv2.dilate(dark.astype(np.uint8),np.ones((k,k),np.uint8))>0
    lab=cv2.cvtColor(image.astype(np.float32)/255,cv2.COLOR_BGR2LAB);gx=cv2.Sobel(g,cv2.CV_32F,1,0,3);gy=cv2.Sobel(g,cv2.CV_32F,0,1,3);rows=[]
    for i in range(1,n):
        x,y,w,h,area=map(int,stats[i]);pad=max(3,int(np.ceil(5*s)));a=max(0,x-pad);b=max(0,y-pad);c=min(image.shape[1],x+w+pad);d=min(image.shape[0],y+h+pad)
        if area<3:continue
        mask=labels[b:d,a:c]==i;ring=(cv2.dilate(mask.astype(np.uint8),np.ones((k,k),np.uint8))>0)&~background_excluded[b:d,a:c]
        if ring.sum()<3:
            if reference_support is not None:raise ValueError('INSUFFICIENT_COMPONENT_RING')
            continue
        contour=max(cv2.findContours(mask.astype(np.uint8),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)[0],key=cv2.contourArea);perimeter=cv2.arcLength(contour,True);ca=cv2.contourArea(contour);hull=cv2.contourArea(cv2.convexHull(contour))
        dx=gx[b:d,a:c][mask];dy=gy[b:d,a:c][mask];aa=np.mean(dx*dx);bb=np.mean(dy*dy);cc=np.mean(dx*dy);coherence=np.sqrt((aa-bb)**2+4*cc*cc)/max(aa+bb,1e-8)
        near=cv2.dilate(mask.astype(np.uint8),np.ones((k,k),np.uint8))>0;core_area=(cores[b:d,a:c]&near).sum();l=lab[b:d,a:c]
        values=[np.log1p(area/(s*s)),max(w,h)/max(1,min(w,h)),area/(w*h),4*np.pi*area/max(perimeter*perimeter,1),ca/max(hull,1),g[b:d,a:c][mask].mean()-np.median(g[b:d,a:c][ring]),coherence,adjacent[b:d,a:c][mask].mean(),core_area/max(1,near.sum()),core_area/(s*s),np.linalg.norm(l[:,:,1:][mask].mean(0)-np.median(l[:,:,1:][ring],axis=0))/100,g[b:d,a:c][mask].std()]
        rows.append(dict(componentId=i,rect=[x,y,w,h],area=area,centroid=centroids[i].tolist(),geometry=np.asarray(values,float).tolist()))
    return labels,rows

def component_crop_boxes(row,metric,pixel_density=1.):
    x,y,w,h=row['rect'];cx=x+w/2;cy=y+h/2;s=max(.125,float(metric));density=max(.125,float(pixel_density));boxes=[]
    for span in [max(w,h)+max(8*density,16*s),max(3*max(w,h),64*s,48*density)]:
        span=int(np.ceil(span));boxes.append(dict(x=int(np.floor(cx-span/2)),y=int(np.floor(cy-span/2)),width=span,height=span,sourcePixelsNotAdded=True))
    return boxes

def material_crop(image,box):
    x0,y0,span=box['x'],box['y'],box['width'];x1=x0+span;y1=y0+span
    crop=np.full((span,span,3),114,np.uint8);a=max(0,x0);b=max(0,y0);c=min(image.shape[1],x1);d=min(image.shape[0],y1)
    if c>a and d>b:crop[b-y0:d-y0,a-x0:c-x0]=image[b:d,a:c]
    rgb=cv2.cvtColor(crop,cv2.COLOR_BGR2RGB);resized=cv2.resize(rgb,(224,224),interpolation=cv2.INTER_AREA if span>=224 else cv2.INTER_LINEAR)
    return ((resized.astype(np.float32)/255-MEAN)/STD).transpose(2,0,1).copy()

def component_crops(image,row,metric,pixel_density=1.):
    """Two square crops with real context, preserving aspect and source bounds."""
    result=[];boxes=component_crop_boxes(row,metric,pixel_density)
    # During a controlled source downsample, native minimum context and close
    # margins downsample as well. Otherwise a half-resolution crop silently
    # covers twice as much source background. Actual native callers use 1.
    for box in boxes:result.append(material_crop(image,box))
    return result,boxes

def support_conditioned_crop(image,labels,row,metric,pixel_density=1.,reference_support=None):
    """One source-scaled context crop, proposed component foreground only.

    The encoder background is its non-self, non-proposal ring median. This is
    a classifier representation, never a replacement photo or new pixel label.
    No source name, object annotation or predicted score enters the crop.
    """
    s=max(.125,float(metric));density=max(.125,float(pixel_density));x,y,w,h=row['rect'];cx=x+w/2;cy=y+h/2
    span=int(np.ceil(max(3*max(w,h),64*s,48*density)));x0=cx-span/2;y0=cy-span/2;pad=max(3,int(np.ceil(5*s)))
    a=max(0,x-pad);b=max(0,y-pad);c=min(image.shape[1],x+w+pad);d=min(image.shape[0],y+h+pad);mask=labels[b:d,a:c]==row['componentId']
    excluded=(labels>0) if reference_support is None else np.asarray(reference_support,bool)
    if excluded.shape!=labels.shape:raise ValueError('INVALID_REFERENCE_SUPPORT')
    ring=(cv2.dilate(mask.astype(np.uint8),np.ones((max(3,2*int(round(3*s))+1),)*2,np.uint8))>0)&~excluded[b:d,a:c]
    if ring.sum()<3:raise ValueError('INSUFFICIENT_COMPONENT_RING')
    reference=np.rint(np.median(image[b:d,a:c][ring],axis=0)).astype(np.uint8)
    # Integer flooring moved the half-source window by one original pixel for
    # odd component centers. Keep the continuous source-edge interval; only
    # the classifier raster is interpolated, never the original photo/map.
    left=int(np.floor(x0))-1;top=int(np.floor(y0))-1;window=np.empty((span+4,span+4,3),np.uint8);window[:]=reference
    a=max(0,left);b=max(0,top);c=min(image.shape[1],left+span+4);d=min(image.shape[0],top+span+4)
    local=labels[b:d,a:c]==row['componentId'];view=window[b-top:d-top,a-left:c-left];view[local]=image[b:d,a:c][local]
    crop=cv2.getRectSubPix(window,(span,span),(cx-left-.5,cy-top-.5))
    rgb=cv2.cvtColor(crop,cv2.COLOR_BGR2RGB);resized=cv2.resize(rgb,(224,224),interpolation=cv2.INTER_AREA if span>=224 else cv2.INTER_LINEAR)
    return ((resized.astype(np.float32)/255-MEAN)/STD).transpose(2,0,1).copy(),dict(x=x0,y=y0,width=span,height=span,ringBGR=reference.tolist(),backgroundIncludesCandidate=False,representation='proposal-component-on-non-self-ring-v1',cropSampling='continuous-source-edge-window-v3')

def filter_conditioned_material_support(image,field,metric,encoder,head,check=None,details=None,reference_support=None):
    """Research single-crop head: half the encoder work, same source support."""
    check=check or (lambda:None);check();start=time.monotonic();labels,rows=describe(image,field,metric,reference_support);timings={'describe':time.monotonic()-start,'crop':0.,'encoder':0.,'classifier':0.};allowed=np.zeros(int(labels.max())+1,bool)
    for offset in range(0,len(rows),16):
        check();current=rows[offset:offset+16];start=time.monotonic();crops=[support_conditioned_crop(image,labels,r,metric,reference_support=reference_support)[0] for r in current];timings['crop']+=time.monotonic()-start
        start=time.monotonic();visual=encoder.extract(crops,16);timings['encoder']+=time.monotonic()-start;check();start=time.monotonic();p=predict(np.c_[visual,np.array([r['geometry'] for r in current])],head);timings['classifier']+=time.monotonic()-start
        for row,probability in zip(current,p):
            allowed[row['componentId']]=probability>=head['threshold']
            if details is not None:details.append({**row,'probability':float(probability),'accepted':bool(allowed[row['componentId']])})
    check();return field*allowed[labels],dict(classifierVersion='frozen-imagenet-ring-conditioned-single-crop-v3-staging',encoderSHA256=ENCODER_SHA,candidateComponents=len(rows),acceptedComponents=int(allowed.sum()),uniqueEncodedCrops=len(rows),maximumResidentCropTensors=16,persistentPhotoCache=False,confidenceNotSeverity=True,sourceLabelsAsInferenceInput=False,timings=timings)

class FrozenMaterialEncoder:
    def __init__(self,path):
        path=Path(path);assert hashlib.sha256(path.read_bytes()).hexdigest()==ENCODER_SHA,'Original ImageNet encoder identity mismatch'
        import torch
        from torchvision.models import efficientnet_b0
        from safetensors.torch import load_file
        torch.set_num_threads(1);self.torch=torch
        self.net=efficientnet_b0(weights=None);self.net.load_state_dict(load_file(str(path)),strict=True)
        self.net.classifier=torch.nn.Identity();self.net.eval()
        for p in self.net.parameters():p.requires_grad_(False)
    def extract(self,crops,batch=4):
        result=[]
        with self.torch.inference_mode():
            for start in range(0,len(crops),batch):
                t=self.torch.from_numpy(np.stack(crops[start:start+batch]));result.append(self.net(t).cpu().numpy().copy())
        return np.concatenate(result) if result else np.empty((0,1280),np.float32)

def fit_classifier(features,labels,groups,regularization=1.,feature_group_sizes=None,group_balanced_loss=False):
    """Call with TRAIN rows only. No PCA or validation-fitted normalization."""
    from scipy.optimize import minimize
    from scipy.special import expit
    X=np.asarray(features,float);y=np.asarray(labels,int);mean=X.mean(0);std=np.maximum(X.std(0),1e-6)
    if feature_group_sizes is not None:
        if sum(feature_group_sizes)!=X.shape[1] or any(v<=0 for v in feature_group_sizes):raise ValueError('INVALID_FEATURE_GROUPS')
        std*=np.concatenate([np.full(n,np.sqrt(n)) for n in feature_group_sizes])
    z=(X-mean)/std;weights=np.array([len(y)/(2*np.sum(y==v)) for v in y]);penalty=1/regularization
    if group_balanced_loss:
        g=np.asarray(groups);weights=np.array([len(y)/(2*len(set(g[y==v]))*np.sum((g==group)&(y==v))) for group,v in zip(g,y)],float)
    def objective(beta):
        logits=z@beta[:-1]+beta[-1];p=expit(logits);error=weights*(p-y)
        loss=np.sum(weights*(np.logaddexp(0,logits)-y*logits))+.5*penalty*np.sum(beta[:-1]**2)
        return float(loss),np.r_[z.T@error+penalty*beta[:-1],error.sum()]
    result=minimize(objective,np.zeros(z.shape[1]+1),jac=True,method='L-BFGS-B',options=dict(maxiter=300,ftol=1e-10,gtol=1e-6))
    if not result.success:raise RuntimeError('Frozen L2 fit did not converge: '+result.message)
    return dict(mean=mean.tolist(),std=std.tolist(),coefficients=result.x[:-1].tolist(),intercept=float(result.x[-1]),threshold=.5,trainGroups=sorted(set(groups)),trainRows=len(y),regularizationC=regularization,solver='scipy-L-BFGS-B',iterations=int(result.nit))

def predict(X,model):
    z=(np.asarray(X)-model['mean'])/model['std'];return 1/(1+np.exp(-np.clip(z@np.asarray(model['coefficients'])+model['intercept'],-40,40)))

def filter_material_support(image,field,metric,encoder,head):
    """Label-blind full-image acceptance of existing proposal pixels.

    No source name, annotation or confidence value enters the score. At most
    sixteen components' crop tensors are resident; encoder batches stay four.
    """
    labels,rows=describe(image,field,metric);allowed=np.zeros(int(labels.max())+1,bool)
    for start in range(0,len(rows),16):
        current=rows[start:start+16];crops=[]
        for row in current:views,_=component_crops(image,row,metric);crops.extend(views)
        visual=encoder.extract(crops,4).reshape(len(current),2560);features=np.c_[visual,np.array([r['geometry'] for r in current])]
        probability=predict(features,head)
        for row,p in zip(current,probability):allowed[row['componentId']]=p>=head['threshold']
    return field*allowed[labels],dict(classifierVersion='frozen-imagenet-two-crop-material-v1-staging',encoderSHA256=ENCODER_SHA,candidateComponents=len(rows),acceptedComponents=int(allowed.sum()),threshold=head['threshold'],confidenceNotSeverity=True,sourceLabelsAsInferenceInput=False)

class OnnxMaterialEncoder:
    """Locally exported frozen encoder, admitted only by its parity receipt."""
    def __init__(self,path,receipt,intra_op_threads=1,batch_limit=16,cpu_mem_arena=True):
        import onnxruntime as ort
        path=Path(path);verified=json.loads(Path(receipt).read_text('utf8'))
        if (verified['sourceEncoderSHA256']!=ENCODER_SHA or not verified['featureParity'] or
            hashlib.sha256(path.read_bytes()).hexdigest()!=verified['onnxSHA256']):
            raise ValueError('UNVERIFIED_MATERIAL_ENCODER')
        if intra_op_threads not in [1,2,4] or batch_limit not in [1,4,8,16]:raise ValueError('UNBOUNDED_ENCODER_EXECUTION')
        options=ort.SessionOptions();options.intra_op_num_threads=intra_op_threads;options.inter_op_num_threads=1;options.enable_cpu_mem_arena=cpu_mem_arena
        self.session=ort.InferenceSession(str(path),options,providers=['CPUExecutionProvider'])
        self.hash=verified['onnxSHA256'];self.batch_limit=batch_limit;self.execution=dict(intraOpThreads=intra_op_threads,batchLimit=batch_limit,cpuMemoryArena=cpu_mem_arena);self.calls=0;self.encoded_crops=0
    def extract(self,crops,batch=16,check=None):
        check=check or (lambda:None);parts=[]
        batch=min(batch,self.batch_limit)
        for start in range(0,len(crops),batch):
            check()
            parts.append(self.session.run(['features'],{'crops':np.stack(crops[start:start+batch])})[0]);self.calls+=1;self.encoded_crops+=min(batch,len(crops)-start)
        check()
        return np.concatenate(parts) if parts else np.empty((0,1280),np.float32)

def filter_material_support_streamed(image,field,metric,encoder,head,check=None,details=None):
    """Exact crop reuse within one request; no persistent photo feature cache.

    Features are reusable only for identical source crop boxes, never merely
    overlapping boxes. Interpolation, padding and RGB contract stay unchanged.
    A stop check runs before each bounded encoder batch; no worker is orphaned.
    """
    check=check or (lambda:None);check();start=time.monotonic();labels,rows=describe(image,field,metric)
    times={'describe':time.monotonic()-start,'crop':0.,'encoder':0.,'classifier':0.};features={};allowed=np.zeros(int(labels.max())+1,bool);encoded=0;reused=0;transforms=0;calls_before=getattr(encoder,'calls',0)
    for offset in range(0,len(rows),16):
        check();current=rows[offset:offset+16];pending={};keys=[];t=time.monotonic()
        for row in current:
            boxes=component_crop_boxes(row,metric);pair=[]
            for box in boxes:
                key=tuple(box[k] for k in ('x','y','width','height'));pair.append(key)
                if key not in features and key not in pending:pending[key]=material_crop(image,box);transforms+=1
                else:reused+=1
            keys.append(pair)
        times['crop']+=time.monotonic()-t
        pending_keys=list(pending)
        for batch_start in range(0,len(pending_keys),16):
            check();batch_keys=pending_keys[batch_start:batch_start+16];t=time.monotonic()
            output=encoder.extract([pending[k] for k in batch_keys],16,check=check) if isinstance(encoder,OnnxMaterialEncoder) else encoder.extract([pending[k] for k in batch_keys],16);times['encoder']+=time.monotonic()-t
            features.update(zip(batch_keys,output));encoded+=len(batch_keys)
        check();visual=np.asarray([np.r_[features[a],features[b]] for a,b in keys]);t=time.monotonic()
        probability=predict(np.c_[visual,np.array([r['geometry'] for r in current])],head);times['classifier']+=time.monotonic()-t
        for row,p in zip(current,probability):
            allowed[row['componentId']]=p>=head['threshold']
            if details is not None:details.append({**row,'probability':float(p),'accepted':bool(p>=head['threshold'])})
    check()
    version='frozen-imagenet-two-crop-material-calibrated-v3' if head.get('lossVersion')=='source-group-balanced-calibrated-v3-c04-clean' else 'frozen-imagenet-two-crop-material-source-group-balanced-v3-staging' if head.get('lossVersion')=='source-group-balanced-v1' else 'frozen-imagenet-two-crop-material-block-balanced-v2-staging' if head.get('featureGroupSizes') else 'frozen-imagenet-two-crop-material-v1-staging'
    return field*allowed[labels],dict(classifierVersion=version,encoderSHA256=ENCODER_SHA,candidateComponents=len(rows),acceptedComponents=int(allowed.sum()),threshold=head['threshold'],confidenceNotSeverity=True,sourceLabelsAsInferenceInput=False,timings=times,uniqueEncodedCrops=encoded,uniqueCropTransforms=transforms,identicalCropsReused=reused,encoderCalls=getattr(encoder,'calls',0)-calls_before,encoderExecution=getattr(encoder,'execution',None),maximumResidentCropTensors=32,persistentPhotoCache=False,transport='onnx-cpu' if isinstance(encoder,OnnxMaterialEncoder) else 'torch')
