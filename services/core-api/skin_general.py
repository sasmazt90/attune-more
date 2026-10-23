"""Front-photo overview, separate from side ROI scores and model confidence."""
import copy
import numpy as np
from skin_product_contract import PRODUCT_APPEARANCE_IDS, general_concern_contract, tone_separation_components

IDS=list(PRODUCT_APPEARANCE_IDS)
VERSION='front-appearance-union-v3-local-target-coverage'
OIL_REGIONS=('forehead','nose','rightCheek','leftCheek','chin')
OIL_SAMPLING='oil-regional-quality-unique-visible-union-v2'


def oil_region_support(response,masks,visible):
    """Only measured oil anatomy enters oil's union; missing is never normal."""
    measured=[];missing={}
    for name in OIL_REGIONS:
        row=next((r for r in response.get(name,[]) if r['id']=='oil'),None)
        if name in masks and row and row.get('quality')=='valid' and row.get('value') is not None:
            measured.append(masks[name])
        else:missing[name]=(row.get('limitationCode') if row else None) or 'REGION_NOT_VISIBLE'
    support=(np.logical_or.reduce(measured) if measured else np.zeros_like(visible))&visible
    return support,missing

def general_result(response,masks,valid,tone,redness,shine,flakes,area,conditions,quality_valid,learned_type=None,candidate_coverage=None,normalizations=None,dry_support=None,sag_support=None,analysis_scale=1.):
    required=['forehead','rightCheek','leftCheek','chin']
    coverage=all(name in masks and int((masks[name]&valid).sum())>=100 for name in required)
    if response:
        coverage=coverage and all(any(r['id']=='tone' and r['quality']=='valid' for r in response.get(name,[])) for name in required)
    result=[]
    oil_support,oil_missing=oil_region_support(response,masks,valid)
    for criterion in IDS:
        evaluated_area=area;source_normalization=(normalizations or {}).get(criterion)
        contract=general_concern_contract(criterion)
        value=None;limitation=contract['limitationCode'];components=contract['components']
        if criterion=='tone':components=tone_separation_components(components)
        # Eye-only source photos can have a fully visible anatomical eye ROI.
        # Cheek/chin coverage is required for whole-face criteria, not eyes.
        local_criterion=criterion in ['lines','dark','bags','sag','acne']
        criterion_coverage=coverage
        if criterion=='oil':
            criterion_coverage=not oil_missing
            limitation=('CAPTURE_QUALITY' if not quality_valid else
                'GLARE_OR_EXPOSURE' if 'GLARE_OR_EXPOSURE' in oil_missing.values() else
                'INSUFFICIENT_FRONT_COVERAGE')
            components={'samplingSupportVersion':OIL_SAMPLING,'sourceRegions':[n for n in OIL_REGIONS if n not in oil_missing],
                'missingRegions':oil_missing,'overlapCountedOnce':True,'temporalPhotometryMeasured':False}
            oil_anatomy=[masks[n] for n in OIL_REGIONS if n in masks]
            evaluated_area={**area,'scope':'unique-visible-measured-oil-regions',
                'analysisPixels':int(oil_support.sum()),'sourcePixels':float(oil_support.sum()/analysis_scale**2),
                'anatomicalSourcePixels':float(np.logical_or.reduce(oil_anatomy).sum()/analysis_scale**2) if oil_anatomy else 0.}
        if criterion=='dry' and dry_support is not None:
            criterion_coverage=all(any(r['id']=='dry' and r['quality']=='valid' for r in response.get(name,[])) for name in required)
        if quality_valid and (criterion_coverage or local_criterion):
            signal={'tone':tone,'redness':redness,'oil':shine,'dry':flakes}.get(criterion)
            signal_support=oil_support if criterion=='oil' else dry_support if criterion=='dry' and dry_support is not None else valid
            if signal is not None and signal_support.any():
                value=float(np.mean(signal[signal_support])) if criterion in ['tone','redness'] else float(np.mean(signal[signal_support]>(.12 if criterion=='oil' else .04))*100)
                limitation=None;components.update(uniqueAnalysisPixels=int(signal_support.sum()),overlapCountedOnce=True)
                if criterion=='dry' and dry_support is not None:
                    scale=sag_support[2] if sag_support is not None else 1.
                    evaluated_area=dict(scope='unique-visible-closed-cell-flake-support',analysisPixels=int(signal_support.sum()),sourcePixels=float(signal_support.sum()/scale**2))
                    components['samplingSupportVersion']='shared-luma-closed-cell-flakes-v3'
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
                    if sag_support is not None:
                        centers,support,scale=sag_support
                        if centers:
                            value=float(100*np.mean(list(centers.values())))
                            components.update(samplingSupportVersion='lower-chin-observed-fold-runs-unique-centers-v9',uniqueObservedCenters=len(centers),overlapCountedOnce=True,indexAggregation='mean of unique observed eligible centers; unmeasurable sides omitted')
                            evaluated_area.update(analysisPixels=int(support.sum()),sourcePixels=float(support.sum()/scale**2),overlapCountedOnce=True)
                        else:value=None;limitation='ANATOMICAL_BAND_NOT_VISIBLE'
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
        result.append(dict(id=criterion,type=contract['type'],value=value,unit=contract['unit'],
          methodVersion=contract['methodVersion'] or ('front-lower-face-unique-centers-v1' if criterion=='sag' and sag_support is not None else VERSION),modelVersion=None,modelHash=None,quality='valid' if value is not None else 'insufficient',
          uncertainty=['illumination','visible-surface-only','unvalidated-cosmetic-proxy'],region='overview',
          evaluatedArea=evaluated_area,captureConditions=conditions,limitationCode=limitation,referenceId=None,
          localMap=None,components=components,normalizationVersion=contract['normalizationVersion'] or source_normalization))
        if value is not None and source_model:
            result[-1].update(modelVersion=source_model['modelVersion'],modelHash=source_model['modelHash'])
    skin_type=learned_type or dict(value=None,quality='insufficient',confidence=None,methodVersion='type-not-accepted-v1',modelHash=None,limitationCode='MODEL_NOT_ACCEPTED')
    return dict(skinType=skin_type,measurements=result,normalizationVersion='appearance-fixed-scales-v1')
