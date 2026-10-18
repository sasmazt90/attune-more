"""Frozen-output source-group bootstrap, never selection or new inference."""
import json
import numpy as np
from prepare_focused_data import OUT,CLASSES,TARGETS,write
SEED=20261010;REPLICATES=500

def intervals(groups,statistics):
    names=sorted(set(groups));rng=np.random.default_rng(SEED);indices={g:np.flatnonzero(np.array(groups)==g) for g in names};values=[]
    for _ in range(REPLICATES):
        chosen=np.concatenate([indices[g] for g in rng.choice(names,len(names),replace=True)]);values.append(statistics(chosen))
    v=np.array(values,float)
    return dict(sourceGroups=len(names),bootstrapReplicates=REPLICATES,seed=SEED,percentile95=np.nanpercentile(v,[2.5,97.5],axis=0).tolist(),personIndependent=False,scope='source-family uncertainty; unknown person links and label bias not estimated')

def main():
    report={}
    if (OUT/'type-final-test.json').exists():
        result=json.loads((OUT/'type-final-test.json').read_text());rows=result['rows'];truth=np.array([CLASSES.index(r['className']) for r in rows]);pred=np.array([CLASSES.index(r['prediction']) for r in rows])
        def score(ids):
            matrix=np.zeros((4,4),int)
            for t,p in zip(truth[ids],pred[ids]):matrix[t,p]+=1
            f=[];rec=[]
            for k in range(4):
                precision=matrix[k,k]/max(1,matrix[:,k].sum());recall=matrix[k,k]/max(1,matrix[k,:].sum());f.append(2*precision*recall/max(1e-9,precision+recall));rec.append(recall)
            return [np.mean(f),np.mean(rec),*f]
        report['type']={**intervals([r['group'] for r in rows],score),'order':['macroF1','balancedAccuracy',*CLASSES],'modelHash':json.loads((OUT/'type-frozen-selection.json').read_text())['weightsSHA256']}
    if (OUT/'degrees-final-test.json').exists():
        result=json.loads((OUT/'degrees-final-test.json').read_text());rows=result['rows'];truth=np.array([[np.nan if v is None else v for v in r['truth']] for r in rows],float);pred=np.array([r['predictions'] for r in rows]);error=np.abs(truth-pred)
        report['degrees']={**intervals([r['group'] for r in rows],lambda ids:np.nanmean(error[ids],axis=0)),'order':TARGETS,'wholeFaceOnly':True,'confidenceIsNotSeverity':True}
    manifest=json.loads((OUT/'learning-manifest.json').read_text());by_path={r['path']:r for r in manifest['rows']}
    for task in ['yolox','fasterrcnn']:
        path=OUT/task/'final-test.json'
        if not path.exists():continue
        from train_focused_local import detection_metrics
        result=json.loads(path.read_text());rows=result['rows'];threshold=result['metrics']['threshold'];counts=[]
        for row in rows:
            one=detection_metrics([by_path[row['path']]],[row['predictions']],threshold)
            counts.append([one['truePositive'],one['falsePositive'],one['falseNegative']])
        counts=np.array(counts,float)
        def detector_statistics(ids):
            tp,fp,fn=counts[ids].sum(0);p=tp/max(1,tp+fp);r=tp/max(1,tp+fn)
            return [p,r,2*p*r/max(1e-9,p+r),fp/max(1,len(ids))]
        report[task]={**intervals([by_path[r['path']]['group'] for r in rows],detector_statistics),'order':['precision','recall','F1','unmatchedCandidatesPerPhoto'],'thresholdFrozen':threshold,'unknownUnannotatedSkinNotClinicalNegative':True}
    if (OUT/'bags/final-test.json').exists():
        result=json.loads((OUT/'bags/final-test.json').read_text());rows=result['rows'];values=np.array([[r['Dice'],r['IoU']] for r in rows]);report['bags']={**intervals([by_path[r['path']]['group'] for r in rows],lambda ids:values[ids].mean(0)),'order':['Dice','IoU'],'scopeLimit':'polygon and two-source-pixel boundary support only; not whole ROI specificity'}
    write('frozen-group-uncertainty.json',report);print(json.dumps(report,indent=2),flush=True)
if __name__=='__main__':main()
