"""Bounded local optical patch classifier, isolated from production.

Presence labels never become pixel masks or clinical severity. The classifier
only gates an existing native proposal, without changing source RGB/support.
"""
import argparse,hashlib,json,time
from pathlib import Path
import cv2,numpy as np
from PIL import Image,ImageDraw
from skimage.feature import local_binary_pattern
import psutil
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/dry-sag-source-census-20261013/flake-controls'
cv2.setNumThreads(1)
FEATURES=['brightAreaFraction','backgroundMAD','candidateProminence','darkFocusFraction','brightDarkAdjacency','gradientAnisotropy','gradientMean','laplacianMean','componentLogAreaMean','componentLogAreaMax','componentElongationMean','componentFillMean',*[f'lbp{i}' for i in range(10)]]

def train_tree(X,y):
    """Small deterministic weighted CART using existing NumPy only."""
    X=np.asarray(X,float);y=np.asarray(y,int);weights=np.array([len(y)/(2*np.sum(y==v)) for v in y])
    tree=dict(childrenLeft=[],childrenRight=[],feature=[],threshold=[],value=[])
    def counts(ids):return np.bincount(y[ids],weights=weights[ids],minlength=2)
    def impurity(c):return (1.-np.sum((c/max(c.sum(),1e-8))**2))*c.sum()
    def node(ids,depth):
        index=len(tree['feature']);c=counts(ids)
        for key,value in [('childrenLeft',-1),('childrenRight',-1),('feature',-2),('threshold',-2.),('value',[c.tolist()])]:tree[key].append(value)
        if depth>=3 or len(ids)<6 or not np.all(c>0):return index
        best=None;best_loss=impurity(c)
        for feature in range(X.shape[1]):
            values=np.unique(X[ids,feature])
            for threshold in (values[:-1]+values[1:])/2:
                left=ids[X[ids,feature]<=threshold];right=ids[X[ids,feature]>threshold]
                if min(len(left),len(right))<3:continue
                loss=impurity(counts(left))+impurity(counts(right))
                if loss<best_loss-1e-12:best_loss=loss;best=(feature,float(threshold),left,right)
        if best is not None:
            feature,threshold,left,right=best;tree['feature'][index]=feature;tree['threshold'][index]=threshold
            tree['childrenLeft'][index]=node(left,depth+1);tree['childrenRight'][index]=node(right,depth+1)
        return index
    node(np.arange(len(y)),0);return tree

def proposal(gray8):
    g=gray8.astype('float32')/255;bg=cv2.medianBlur(gray8,11).astype('float32')/255
    mad=cv2.medianBlur(np.rint(np.abs(g-bg)*255).astype('uint8'),11).astype('float32')/255
    raw=np.clip((g-bg-.025)/.10,0,1)*(local_binary_pattern(gray8,8,1,'uniform')<8)
    raw*=g-bg>np.maximum(.025,3*1.4826*mad)
    return raw

def features(gray8):
    raw=proposal(gray8);active=raw>.04;g=gray8.astype('float32')/255;bg=g[~active]
    reference=float(np.median(bg)) if bg.size else float(np.median(g))
    mad=float(np.median(np.abs(bg-reference))) if bg.size else 0.
    prominence=float(np.mean(g[active])-reference) if active.any() else 0.
    dark=cv2.morphologyEx(gray8,cv2.MORPH_BLACKHAT,np.ones((7,7),np.uint8))>35
    adjacency=cv2.dilate(dark.astype('uint8'),np.ones((7,7),np.uint8))>0
    dx=cv2.Sobel(g,cv2.CV_32F,1,0,ksize=3);dy=cv2.Sobel(g,cv2.CV_32F,0,1,ksize=3)
    covariance=np.array([[np.mean(dx*dx),np.mean(dx*dy)],[np.mean(dx*dy),np.mean(dy*dy)]])
    eigen=np.linalg.eigvalsh(covariance);anisotropy=float((eigen[1]-eigen[0])/max(eigen.sum(),1e-8))
    n,_,stats,_=cv2.connectedComponentsWithStats(active.astype('uint8'));stats=stats[1:];stats=stats[stats[:,4]>=3]
    areas=stats[:,4]/gray8.size if len(stats) else np.zeros(1);elongations=np.maximum(stats[:,2],stats[:,3])/np.maximum(1,np.minimum(stats[:,2],stats[:,3])) if len(stats) else np.zeros(1)
    fill=stats[:,4]/np.maximum(1,stats[:,2]*stats[:,3]) if len(stats) else np.zeros(1)
    lbp=local_binary_pattern(gray8,8,1,'uniform');hist=np.bincount(lbp.astype('int32').ravel(),minlength=10)/gray8.size
    return np.asarray([active.mean(),mad,prominence,dark.mean(),adjacency[active].mean() if active.any() else 0.,anisotropy,np.mean(np.hypot(dx,dy)),np.mean(np.abs(cv2.Laplacian(g,cv2.CV_32F))),np.mean(np.log1p(areas*1000)),np.max(np.log1p(areas*1000)),elongations.mean(),fill.mean(),*hist],np.float64)

def prepare():
    control=OUT/'controls-reviewed.json';c=json.loads(control.read_text('utf8'));assert c['reviewedBeforeFitting'] and not c['modelFitted']
    rows=[];pages=[]
    for r in c['controls']:
        data=Path(r['sourcePath']).read_bytes();assert hashlib.sha256(data).hexdigest()==r['sourceSHA256']
        source=cv2.imread(r['sourcePath']);x,y,w,h=r['roi'];size=min(96,w,h)
        positions=sorted({(x+xx,y+yy) for xx in [0,w-size] for yy in [0,h-size]})
        for k,(a,b) in enumerate(positions):
            patch=source[b:b+size,a:a+size];assert patch.shape[:2]==(size,size)
            gray=cv2.cvtColor(patch,cv2.COLOR_BGR2GRAY);f=features(gray)
            row=dict(patchIndex=len(rows),controlIndex=r['controlIndex'],withinControlIndex=k,sourceSHA256=r['sourceSHA256'],sourcePath=r['sourcePath'],group=r['group'],split=r['split'],kind=r['kind'],rect=[a,b,size,size],parentROIPresence=r['patchPresenceLabel'],label=None,features=f.tolist());rows.append(row)
            im=Image.fromarray(patch[:,:,::-1]);im=im.resize((192,192));d=ImageDraw.Draw(im);d.text((2,2),f"{row['patchIndex']:02d} C{r['controlIndex']} {r['split']}",fill='red');pages.append(im)
    for start in range(0,len(pages),32):
        sheet=Image.new('RGB',(4*192,8*200),'#111111')
        for j,im in enumerate(pages[start:start+32]):sheet.paste(im,(j%4*192,j//4*200))
        sheet.save(OUT/f'patch-review-{start//32}.png')
    file=OUT/'patches-unlabelled.json';assert not file.exists()
    file.write_text(json.dumps(dict(controlSHA256=hashlib.sha256(control.read_bytes()).hexdigest(),features=FEATURES,patches=rows,modelFitted=False),ensure_ascii=False,indent=2),'utf8');print(dict(patches=len(rows),features=len(FEATURES)))

def fit():
    start=time.monotonic();file=OUT/'patches-reviewed.json';c=json.loads(file.read_text('utf8'));rows=c['patches'];assert all(r['label'] in (None,0,1) for r in rows)
    train=[r for r in rows if r['split']=='train' and r['label'] is not None];validation=[r for r in rows if r['split']=='validation' and r['label'] is not None]
    assert not {r['group'] for r in train}&{r['group'] for r in validation}
    tree=train_tree([r['features'] for r in train],[r['label'] for r in train])
    model=dict(version='staging-native-optical-patch-tree-v1',accepted=False,features=FEATURES,parameters=dict(max_depth=3,min_samples_leaf=3,class_weight='balanced',deterministicTieOrder='feature-index then threshold'),classes=[0,1],**tree,controlSHA256=c['controlSHA256'],reviewedPatchesSHA256=hashlib.sha256(file.read_bytes()).hexdigest(),scope='local patch flake presence; gates proposal, never severity')
    predicted=[int(predict_features(r['features'],model)>=.5) for r in validation];matrix=np.zeros((2,2),int)
    for r,p in zip(validation,predicted):matrix[r['label'],p]+=1
    target=OUT/'staging-patch-tree.json';assert not target.exists(),'No repeated fitting or overwrite'
    target.write_text(json.dumps(model,indent=2),'utf8')
    observations=[dict(patchIndex=r['patchIndex'],controlIndex=r['controlIndex'],kind=r['kind'],group=r['group'],label=r['label'],prediction=int(p),probability=predict_features(r['features'],model)) for r,p in zip(validation,predicted)]
    receipt=dict(seconds=time.monotonic()-start,RSSBytes=psutil.Process().memory_info().rss,trainPatches=len(train),validationPatches=len(validation),trainGroups=len({r['group'] for r in train}),validationGroups=len({r['group'] for r in validation}),unknownPatches=sum(r['label'] is None for r in rows),confusionMatrix=matrix.tolist(),observations=observations,modelSHA256=hashlib.sha256(target.read_bytes()).hexdigest(),scope='explicitly visually reviewed optical patch presence; not pixel precision/Dice or application accuracy',sourcePersonIndependent=False,productionChanged=False)
    (OUT/'patch-tree-fit.json').write_text(json.dumps(receipt,indent=2),'utf8');print(json.dumps(receipt))

def predict_features(values,model):
    node=0
    while model['childrenLeft'][node]!=model['childrenRight'][node]:
        node=model['childrenLeft'][node] if values[model['feature'][node]]<=model['threshold'][node] else model['childrenRight'][node]
    weights=np.asarray(model['value'][node][0]);return float(weights[model['classes'].index(1)]/max(weights.sum(),1e-8))

def candidate_field(gray8,model):
    # Proposal is computed once on the full native field; overlapping contexts
    # add no duplicate pixels or altered denominator and create no tile seams.
    raw=proposal(gray8);allowed=np.zeros(gray8.shape,bool);size=96;stride=48
    xs=sorted(set([*range(0,max(1,gray8.shape[1]-size+1),stride),max(0,gray8.shape[1]-size)]));ys=sorted(set([*range(0,max(1,gray8.shape[0]-size+1),stride),max(0,gray8.shape[0]-size)]))
    for x in xs:
        for y in ys:
            patch=gray8[y:y+size,x:x+size]
            if predict_features(features(patch),model)>=.5:allowed[y:y+size,x:x+size]=True
    return raw*allowed

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','fit']);args=parser.parse_args()
    prepare() if args.action=='prepare' else fit()
