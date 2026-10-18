"""Describe fixed validation temperature calibration; never select on test."""
import json,numpy as np
from prepare_focused_data import OUT,CLASSES,write

def metrics(logits,truth,t):
    z=logits/t;z-=z.max(1,keepdims=True);p=np.exp(z);p/=p.sum(1,keepdims=True);conf=p.max(1);correct=p.argmax(1)==truth;ece=0.;bins=[]
    for lo in np.arange(0,1,.1):
        valid=(conf>=lo)&(conf<(lo+.1) if lo<.9 else conf<=1);n=int(valid.sum())
        if n:
            accuracy=float(correct[valid].mean());confidence=float(conf[valid].mean());ece+=n/len(truth)*abs(accuracy-confidence);bins.append(dict(lower=float(lo),support=n,accuracy=accuracy,confidence=confidence))
    return dict(NLL=float(-np.log(p[np.arange(len(truth)),truth]+1e-12).mean()),multiclassBrier=float(((p-np.eye(4)[truth])**2).sum(1).mean()),tenBinECE=float(ece),bins=bins)

def main():
    manifest=json.loads((OUT/'learning-manifest.json').read_text());rows=[r for r in manifest['rows'] if r['typeEligible'] and r['split']=='validation'];truth=np.array([CLASSES.index(r['class']) for r in rows]);result=[]
    for name in ['resnet18','efficientnet_b0']:
        s=json.loads((OUT/name/'selection.json').read_text());logits=np.load(OUT/name/'validation-logits.npy',allow_pickle=False);result.append(dict(model=name,weightsSHA256=s['weightsSHA256'],temperature=s['temperature'],uncalibrated=metrics(logits,truth,1.),fixedCalibrated=metrics(logits,truth,s['temperature']),scope='validation-only fitted temperature; not independent camera calibration',noTestRead=True,confidenceIsNotSeverity=True))
    write('type-validation-calibration.json',result);print([(r['model'],r['fixedCalibrated']['NLL'],r['fixedCalibrated']['tenBinECE']) for r in result],flush=True)

if __name__=='__main__':main()
