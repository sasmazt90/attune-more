"""Front-photo overview, separate from side ROI scores and model confidence."""
import copy
import numpy as np

IDS=['tone','oil','redness','acne','sag','dry','lines','dark','bags']
VERSION='front-appearance-union-v1'

def general_result(response,masks,valid,tone,redness,shine,flakes,area,conditions,quality_valid,learned_type=None,candidate_coverage=None):
    required=['forehead','rightCheek','leftCheek','chin']
    coverage=all(name in masks and int((masks[name]&valid).sum())>=100 for name in required)
    if response:
        coverage=coverage and all(any(r['id']=='tone' and r['quality']=='valid' for r in response.get(name,[])) for name in required)
    result=[]
    for criterion in IDS:
        evaluated_area=area
        value=None;limitation='INSUFFICIENT_FRONT_COVERAGE';components={}
        if quality_valid and coverage:
            signal={'tone':tone,'redness':redness,'oil':shine,'dry':flakes}.get(criterion)
            if signal is not None and valid.any():
                value=float(np.mean(signal[valid])) if criterion in ['tone','redness'] else float(np.mean(signal[valid]>(.12 if criterion=='oil' else .04))*100)
                limitation=None;components={'uniqueAnalysisPixels':int(valid.sum()),'overlapCountedOnce':True}
            elif criterion in ['lines','dark','bags']:
                row=next((r for r in response.get('periorbital',[]) if r['id']==criterion),None)
                if row and row['quality']=='valid':
                    value=row['value'];limitation=None;components={'sourceRegion':'periorbital','sourceMethod':row['methodVersion'],'sourceComponents':copy.deepcopy(row['components'])}
                    evaluated_area=copy.deepcopy(row.get('evaluatedArea',area))
            elif criterion=='sag':
                rows=[next((r for r in response.get(region,[]) if r['id']=='sag' and r['quality']=='valid'),None) for region in ['rightCheek','leftCheek','chin']]
                if all(rows):
                    value=float(np.mean([r['value'] for r in rows]));limitation=None
                    components={'sourceRegions':['rightCheek','leftCheek','chin'],'meaning':'current lower-face contour/fold appearance; not elasticity','sourceMethods':[r['methodVersion'] for r in rows]}
            elif criterion=='acne':
                rows=[r for values in response.values() for r in values if r['id']=='acne' and r['quality']=='valid']
                if rows:
                    candidates=list({b.get('candidateId',str((b['x'],b['y'],b['width'],b['height']))):b for r in rows for b in r['components'].get('bounds',[])}.values())
                    value=candidate_coverage if candidate_coverage is not None else min(100.,100*sum(b.get('areaPixels',0) for b in candidates)/max(area['sourcePixels'],1));limitation=None
                    components={'bounds':candidates,'candidateCount':len(candidates),'visibleCandidateAreaPercent':value,'samePoseOnly':True,'ownershipDeduplicated':True}
        model_rows=[r for values in response.values() for r in values if r['id']==criterion and r['quality']=='valid' and r.get('modelHash')]
        hashes={r['modelHash'] for r in model_rows}
        source_model=model_rows[0] if len(hashes)==1 else None
        result.append(dict(id=criterion,type='appearance_proxy',value=value,unit='appearance-score-0-100',
          methodVersion=VERSION,modelVersion=None,modelHash=None,quality='valid' if value is not None else 'insufficient',
          uncertainty=['illumination','visible-surface-only','unvalidated-cosmetic-proxy'],region='overview',
          evaluatedArea=evaluated_area,captureConditions=conditions,limitationCode=limitation,referenceId=None,
          localMap=None,components=components))
        if value is not None and source_model:
            result[-1].update(modelVersion=source_model['modelVersion'],modelHash=source_model['modelHash'])
    skin_type=learned_type or dict(value=None,quality='insufficient',confidence=None,methodVersion='type-not-accepted-v1',modelHash=None,limitationCode='MODEL_NOT_ACCEPTED')
    return dict(skinType=skin_type,measurements=result,normalizationVersion='appearance-fixed-scales-v1')
