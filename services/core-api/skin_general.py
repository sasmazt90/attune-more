"""Front-photo overview, separate from side ROI scores and model confidence."""
import copy
import numpy as np

IDS=['tone','oil','redness','acne','sag','dry','lines','dark','bags']
VERSION='front-appearance-union-v3-local-target-coverage'

def general_result(response,masks,valid,tone,redness,shine,flakes,area,conditions,quality_valid,learned_type=None,candidate_coverage=None,normalizations=None):
    required=['forehead','rightCheek','leftCheek','chin']
    coverage=all(name in masks and int((masks[name]&valid).sum())>=100 for name in required)
    if response:
        coverage=coverage and all(any(r['id']=='tone' and r['quality']=='valid' for r in response.get(name,[])) for name in required)
    result=[]
    for criterion in IDS:
        evaluated_area=area;source_normalization=(normalizations or {}).get(criterion)
        value=None;limitation='INSUFFICIENT_FRONT_COVERAGE';components={}
        # Eye-only source photos can have a fully visible anatomical eye ROI.
        # Cheek/chin coverage is required for whole-face criteria, not eyes.
        local_criterion=criterion in ['lines','dark','bags','sag','acne']
        if quality_valid and (coverage or local_criterion):
            signal={'tone':tone,'redness':redness,'oil':shine,'dry':flakes}.get(criterion)
            if signal is not None and valid.any():
                value=float(np.mean(signal[valid])) if criterion in ['tone','redness'] else float(np.mean(signal[valid]>(.12 if criterion=='oil' else .04))*100)
                limitation=None;components={'uniqueAnalysisPixels':int(valid.sum()),'overlapCountedOnce':True}
            elif criterion in ['lines','dark','bags']:
                row=next((r for r in response.get('periorbital',[]) if r['id']==criterion),None)
                if row and row['quality']=='valid':
                    value=row['value'];limitation=None;components={'sourceRegion':'periorbital','sourceMethod':row['methodVersion'],'sourceComponents':copy.deepcopy(row['components'])}
                    evaluated_area=copy.deepcopy(row.get('evaluatedArea',area));source_normalization=row.get('normalizationVersion',source_normalization)
                elif row:limitation=row.get('limitationCode',limitation)
            elif criterion=='sag':
                regions=['rightCheek','leftCheek','chin']
                rows={region:next((r for r in response.get(region,[]) if r['id']=='sag'),None) for region in regions}
                measured={region:r for region,r in rows.items() if r and r['quality']=='valid' and r['value'] is not None}
                if measured:
                    # The chin and cheek measurements can reuse a fold path.
                    # Deduplicate actual supported sides instead of weighting it twice.
                    sides={};missing_sides={}
                    for r in measured.values():
                        for side in r.get('components',{}).get('sides',[]):
                            if side.get('value') is not None:sides.setdefault(side['side'],side['value'])
                            else:missing_sides.setdefault(side['side'],side.get('limitationCode','ANATOMICAL_BAND_NOT_VISIBLE'))
                    value=float(np.mean(list(sides.values()) if sides else [r['value'] for r in measured.values()]));limitation=None
                    missing={region:r.get('limitationCode') if r else 'REGION_NOT_VISIBLE' for region,r in rows.items() if region not in measured}
                    components={'sourceRegions':list(measured),'missingRegions':missing,'partialCoverage':bool(missing or {k:v for k,v in missing_sides.items() if k not in sides}),'missingSides':{k:v for k,v in missing_sides.items() if k not in sides},'measuredSides':sides,'wholeFaceInference':False,'meaning':'current observed lower-face contour/fold appearance; not elasticity','sourceMethods':[r['methodVersion'] for r in measured.values()]}
                    evaluated_area={'scope':'measured-local-lower-face','regions':{region:copy.deepcopy(r.get('evaluatedArea',{})) for region,r in measured.items()}}
                else:
                    limitation=next((r.get('limitationCode') for r in rows.values() if r and r.get('limitationCode')),'LOWER_FACE_NOT_MEASURABLE')
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
          localMap=None,components=components,normalizationVersion=source_normalization))
        if value is not None and source_model:
            result[-1].update(modelVersion=source_model['modelVersion'],modelHash=source_model['modelHash'])
    skin_type=learned_type or dict(value=None,quality='insufficient',confidence=None,methodVersion='type-not-accepted-v1',modelHash=None,limitationCode='MODEL_NOT_ACCEPTED')
    return dict(skinType=skin_type,measurements=result,normalizationVersion='appearance-fixed-scales-v1')
