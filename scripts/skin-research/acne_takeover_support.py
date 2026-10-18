"""Research-only source-space acne contract; no production activation.

Partial annotation outside explicitly reviewed clean skin is UNKNOWN. Generated
outer contours and photometric pseudo labels do not establish clean ground truth.
"""
import ast, base64, hashlib, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
AG=ROOT.parent/'attune-antigravity-skin'
OUT=ROOT/'audit-results/acne-takeover-20261015'
sys.path.insert(0,str(ROOT/'services/core-api'))
sys.path.insert(0,str(ROOT/'audit-results/combined-health-20261008/yolox/extracted/YOLOX-6ddff4824372906469a7fae2dc3206c7aa4bbaee'))

def read(p):return json.loads(p.read_text('utf8'))
def digest(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def strict_clean_mask(row,image,all_holes=(),reviewed_support=None):
    import cv2,numpy as np
    from source_skin_support import known_skin_scope
    mask=np.zeros(image.shape[:2],np.uint8)
    # The existing criterion-specific whole-visible-face review is explicit.
    # A generated negativeROIs polygon on partially annotated acne is not.
    if row.get('split')!='train':raise ValueError('TRAIN_ONLY_MASK')
    if row.get('negativeROI') and not row.get('annotations') and len(row.get('landmarks',[]))>=468 and reviewed_support is not None:
        if reviewed_support.shape!=mask.shape:raise ValueError('REVIEWED_SUPPORT_COORDINATES')
        mask=known_skin_scope(row,image)&(reviewed_support>0).astype(np.uint8)
    for box in [a['box'] for a in row.get('annotations',[])]+list(all_holes):
        x,y,ex,ey=box;x=max(0,int(x)-16);y=max(0,int(y)-16);ex=min(mask.shape[1],int(ex+17));ey=min(mask.shape[0],int(ey+17));mask[y:ey,x:ex]=0
    dist=cv2.distanceTransform(mask,cv2.DIST_L2,5)
    return mask,np.clip(dist/16,.2,1).astype('float32')*(mask>0)

def known_cells(mask,weight,rect):
    import torch,numpy as np
    a,b,c,d=rect;h,w=mask.shape;known=[];weights=[]
    for stride in (4,8,16,32):
        xx,yy=np.meshgrid((np.arange(384//stride)+.5)*stride+a,(np.arange(384//stride)+.5)*stride+b);xx=xx.astype(int);yy=yy.astype(int)
        inside=(xx<c)&(yy<d)&(xx>=0)&(yy>=0)&(xx<w)&(yy<h);sx=xx.clip(0,w-1);sy=yy.clip(0,h-1);k=inside&(mask[sy,sx]>0)
        known.append(k.ravel());weights.append((weight[sy,sx]*k).ravel())
    return torch.from_numpy(np.concatenate(known)[:,None]),torch.from_numpy(np.concatenate(weights)[:,None])

def current_product_masks(payload):
    """Execute the current production prelude verbatim until acne_skin exists.

    AST extraction avoids a copied approximation of origin, scale, holes, hair,
    exposure or automatic exclusions. No globals are changed and no detector
    weights are injected. The production manifest keeps acne disabled.
    """
    import appearance_analysis as production
    source=Path(production.__file__).read_text('utf8');tree=ast.parse(source)
    function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='analyze_skin')
    body=[]
    for statement in function.body:
        body.append(statement)
        if isinstance(statement,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='acne_skin' for t in statement.targets):break
    else:raise ValueError('PRODUCTION_ACNE_PRELUDE_CHANGED')
    # Production infer_acne sees accepted:false/file:null. No hosted call occurs
    # in this prelude (type inference is a different endpoint stage).
    body.append(ast.Return(value=ast.Call(func=ast.Name(id='locals',ctx=ast.Load()),args=[],keywords=[])))
    function.body=body;module=ast.fix_missing_locations(ast.Module(body=[function],type_ignores=[]));namespace=dict(vars(production));exec(compile(module,str(Path(production.__file__)), 'exec'),namespace)
    result=namespace['analyze_skin'](payload)
    return {k:result[k] for k in ['acne_envelopes','acne_skin','hair','acne_exclusion','scale','origin','face_pixels','face_support']}

def tile_rectangles(bgr,points,fallback=None):
    from skin_models import photo_input
    h,w=bgr.shape[:2]
    if points and len(points)>=468:
        _,transform=photo_input(bgr,points);x=transform['x'];y=transform['y'];ex=x+transform['width'];ey=y+transform['height']
    else:x,y,ex,ey=fallback or (0,0,w,h)
    xs=sorted(set([*range(x,max(x+1,ex-384+1),288),max(x,ex-384)]));ys=sorted(set([*range(y,max(y+1,ey-384+1),288),max(y,ey-384)]))
    if len(xs)*len(ys)>64:raise ValueError('NATIVE_TILE_BUDGET_EXCEEDED')
    return [[int(a),int(b),int(min(ex,a+384)),int(min(ey,b+384))] for a in xs for b in ys]

def infer_tiles(net,bgr,rects,check=lambda:None):
    import numpy as np,torch
    from skin_models import _nms
    boxes=[];scores=[];metadata=[]
    with torch.inference_mode():
        for tile_id,(a,b,c,d) in enumerate(rects):
            check();tile=np.full((384,384,3),114,np.uint8);patch=bgr[b:d,a:c];tile[:patch.shape[0],:patch.shape[1]]=patch
            out=net(torch.from_numpy(tile.transpose(2,0,1).copy()).float()[None])[0];score=out[:,4]*out[:,5];indices=torch.where(score>=.30)[0];pred=out[indices];score=score[indices]
            for index,p,s in zip(indices.tolist(),pred.tolist(),score.tolist()):
                cx,cy,bw,bh=p[:4];box=[max(a,cx+a-bw/2),max(b,cy+b-bh/2),min(c,cx+a+bw/2),min(d,cy+b+bh/2)]
                if box[2]<=box[0] or box[3]<=box[1]:continue
                box=[float(v) for v in box];boxes.append(box);scores.append(s);metadata.append(dict(tile=tile_id,rect=[a,b,c,d],anchor=index,objectness=p[4],classProbability=p[5],confidence=s,box=box))
    if not boxes:return [],dict(tiles=len(rects),confidenceCandidates=[],nmsCandidates=[])
    selected=_nms([b+[s] for b,s in zip(boxes,scores)],threshold=.30)
    lookup={tuple(v['box']+[v['confidence']]):v for v in metadata}
    return selected,dict(tilingContract='current-skin-models-photo-input-camera-crop-v1',tiles=len(rects),confidenceCandidates=metadata,nmsCandidates=[lookup[tuple(v)] for v in selected])

def one_to_one(truth,pred):
    import torch
    from torchvision.ops import box_iou
    if not truth or not pred:return []
    matrix=box_iou(torch.tensor(truth,dtype=torch.float32),torch.tensor(pred,dtype=torch.float32));pairs=[]
    while matrix.numel():
        value,index=matrix.flatten().max(0)
        if value<.5:break
        t=int(index)//matrix.shape[1];p=int(index)%matrix.shape[1];pairs.append([t,p,float(value)]);matrix[t,:]=-1;matrix[:,p]=-1
    return pairs
