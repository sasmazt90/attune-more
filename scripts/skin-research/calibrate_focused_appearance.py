"""Train-only isotonic appearance calibration; val selects, final test freezes.

Global graded labels are compared only to global photo features. No regional or
pixel severity truth is invented. Existing pixel support remains independent.
"""
import argparse,base64,hashlib,json,subprocess,sys,time
import cv2,numpy as np
from prepare_focused_data import ROOT,OUT,TARGETS,write,sha
sys.path.insert(0,str(ROOT/'services/core-api'))
import appearance_analysis as A

TARGET_IDS=['tone','oil','redness','acne','dry','lines','dark','bags']
def isotonic_knots(x,y):
    """Weighted pool-adjacent-violators fit, training labels only."""
    unique=np.unique(x);blocks=[]
    for i,value in enumerate(unique):
        truth=y[x==value];blocks.append([i,i,len(truth),float(truth.sum())])
        while len(blocks)>1 and blocks[-2][3]/blocks[-2][2]>blocks[-1][3]/blocks[-1][2]:
            last=blocks.pop();prev=blocks.pop();blocks.append([prev[0],last[1],prev[2]+last[2],prev[3]+last[3]])
    xs=[];ys=[]
    for start,end,n,total in blocks:
        xs.append(float(unique[start]));ys.append(total/n)
        if end!=start:xs.append(float(unique[end]));ys.append(total/n)
    return xs,ys
def measurements(rows,phase):
    target=OUT/('appearance-features-'+phase+'.json')
    if target.exists():return json.loads(target.read_text())
    meshes=json.loads(subprocess.check_output(['node','scripts/skin-research/focused_meshes.cjs'],input=json.dumps(rows).encode(),cwd=ROOT))
    data=[];started=time.monotonic()
    for i,(r,m) in enumerate(zip(rows,meshes)):
        bgr=cv2.imread(r['absolutePath']);ok,raw=cv2.imencode('.png',bgr);assert ok
        photo='data:image/png;base64,'+base64.b64encode(raw).decode();digest=hashlib.sha256(cv2.cvtColor(bgr,cv2.COLOR_BGR2RGBA).tobytes()).hexdigest()
        a,b,c,d=r['crop'];gray=cv2.cvtColor(bgr[b:d,a:c],cv2.COLOR_BGR2GRAY);lum=float(gray.mean())
        p=r['landmarks'];alignment=m['alignment'];conditions={k:alignment[k] for k in ('yaw','pitch','roll','scaleRatio')};conditions.update(avgLuminance=lum,blurScore=r['blur'])
        payload=dict(photo=photo,photoId=digest,pose='FRONT',landmarks=p,meshes=m['meshes'],exclusions=[],qualityValid=40<=lum<=220 and r['blur']>=4 and abs(alignment['yaw'])<.35,conditions=conditions)
        # No assertion of a successful physical capture: quality is derived from
        # this photo; ROI/mapping use actual production functions and landmarks.
        result=A.analyze_skin(payload,include_research_features=True);signals={v['id']:v['value'] for v in result['general']['measurements']};signals.update(result.get('researchFeatures',{}))
        data.append(dict(sha256=r['sha256'],path=r['path'],group=r['group'],split=r['split'],grades=r['grades'],signals=signals))
        if i%10==0:print('appearance',phase,i,len(rows),round(time.monotonic()-started),flush=True)
    write(target.name,data);return data

def mae(values,pred):
    mask=np.isfinite(values)&np.isfinite(pred);return dict(support=int(mask.sum()),MAE=float(np.abs(values[mask]-pred[mask]).mean()) if mask.any() else None)
def main():
    cv2.setNumThreads(1)
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['selection','final']);args=parser.parse_args();m=json.loads((OUT/'learning-manifest.json').read_text());rows=[r for r in m['rows'] if r['degreeEligible']]
    if args.phase=='selection':
        assert not (OUT/'appearance-frozen-calibration.json').exists(),'Completed calibration preserved'
        data=measurements([r for r in rows if r['split']!='test'],'selection');train=[r for r in data if r['split']=='train'];val=[r for r in data if r['split']=='validation'];heads=[]
        for id in TARGET_IDS:
            index=TARGETS.index(id);paired=[(r['signals'].get(id),r['grades'][index]) for r in train if r['signals'].get(id) is not None and r['grades'][index] is not None];vpaired=[(r['signals'].get(id),r['grades'][index]) for r in val if r['signals'].get(id) is not None and r['grades'][index] is not None]
            if len(paired)<10 or len(vpaired)<10:heads.append(dict(id=id,available=False,reason='INSUFFICIENT_VALID_GLOBAL_TARGETS',train=len(paired),validation=len(vpaired)));continue
            x,y=np.array(paired).T;vx,vy=np.array(vpaired).T;constant=float(np.median(y));base=mae(vy,np.full(len(vy),constant));existing=mae(vy,vx/20);choices=[]
            for feature in ([id,'oil-baseline'] if id=='oil' else [id]):
                trainpairs=[(r['signals'].get(feature),r['grades'][index]) for r in train if r['signals'].get(feature) is not None and r['grades'][index] is not None];vpairs=[(r['signals'].get(feature),r['grades'][index]) for r in val if r['signals'].get(feature) is not None and r['grades'][index] is not None]
                if len(trainpairs)<10 or len(vpairs)<10:continue
                tx,ty=np.array(trainpairs).T;qx,qy=np.array(vpairs).T;knots=isotonic_knots(tx,ty);metrics=mae(qy,np.interp(qx,*knots));choices.append((metrics['MAE'],feature,knots,metrics))
            _,feature,knots,metrics=min(choices,key=lambda v:v[0]);heads.append(dict(id=id,feature=feature,available=True,x=knots[0],y=knots[1],trainMedian=constant,validation=metrics,constantBaseline=base,uncalibratedMethodBaseline=existing,validationAccepted=metrics['MAE']<min(base['MAE'],existing['MAE']),normalization='fixed training isotonic knots, 0..5 -> x20; not per-image min/max'))
        write('appearance-frozen-calibration.json',dict(heads=heads,testOpened=False,sourceManifestSHA256=sha(OUT/'dataset-manifest.json'),globalOnly=True,localMapsUnchanged=True,regionalScoresNotLearnedFromGlobalTargets=True,sourceMethod=A.VERSION))
    else:
        assert not (OUT/'appearance-final-test.json').exists(),'Final protected test preserved'
        frozen=json.loads((OUT/'appearance-frozen-calibration.json').read_text());data=measurements([r for r in rows if r['split']=='test'],'final');heads=frozen['heads']
        for h in heads:
            if not h['available']:h['accepted']=False;continue
            index=TARGETS.index(h['id']);feature=h.get('feature',h['id']);pairs=[(r['signals'].get(feature),r['grades'][index]) for r in data if r['signals'].get(feature) is not None and r['grades'][index] is not None]
            if not pairs:h.update(accepted=False,test={'support':0,'MAE':None});continue
            x,y=np.array(pairs).T;pred=np.interp(x,h['x'],h['y']);h['test']=mae(y,pred);h['testConstantBaseline']=mae(y,np.full(len(y),h['trainMedian']));h['testUncalibratedBaseline']=mae(y,x/20);h['accepted']=h['validationAccepted'] and len(y)>=10 and h['test']['MAE']<=1 and h['test']['MAE']<min(h['testConstantBaseline']['MAE'],h['testUncalibratedBaseline']['MAE'])
        write('appearance-final-test.json',dict(**{k:v for k,v in frozen.items() if k!='heads'},heads=heads,cameraDomainAccepted=False));print(json.dumps(heads,indent=2),flush=True)
if __name__=='__main__':main()
