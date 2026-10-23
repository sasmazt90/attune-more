"""Validation-only localization/taxonomy diagnosis from pinned detections.

A class-agnostic confidence-ordered matrix uses one-to-one IoU matching. Loose
best-overlap counts are diagnostic opportunities (reuse allowed), NOT recall.
Source-coordinate size buckets never claim a model's input resolution.
"""
import argparse,collections,json,math
from pathlib import Path
from evaluate_detector_snapshot import CLASSES,finite,iou,read_snapshot

BACKGROUND='background'


def confusion(truth,predictions,thresholds,minimum_iou=.5):
    matrix={label:{other:0 for other in (*CLASSES,BACKGROUND)} for label in (*CLASSES,BACKGROUND)}
    errors=[]
    for image_id,boxes in truth.items():
        used=set()
        for p in sorted((p for p in predictions[image_id] if p['confidence']>=thresholds[p['class']]),key=lambda p:-p['confidence']):
            score,k=max(((iou(p['bbox'],t['bbox']),k) for k,t in enumerate(boxes) if k not in used),default=(0.,-1))
            if score>=minimum_iou:
                used.add(k);label=boxes[k]['class'];matrix[label][p['class']]+=1
                if label!=p['class']:errors.append(dict(imageId=image_id,truth=label,predicted=p['class'],iou=score,truthBox=boxes[k]['bbox'],predictedBox=p['bbox'],confidence=p['confidence']))
            else:matrix[BACKGROUND][p['class']]+=1
        for k,t in enumerate(boxes):
            if k not in used:matrix[t['class']][BACKGROUND]+=1
    return matrix,errors


def analyze(truth,predictions,thresholds):
    if any(not finite(thresholds.get(k)) or not .05<=thresholds[k]<=.95 for k in CLASSES):raise ValueError('INVALID_THRESHOLDS')
    matrix,errors=confusion(truth,predictions,thresholds)
    sizes={label:collections.Counter() for label in CLASSES}
    opportunities={label:collections.Counter() for label in CLASSES}
    cross=collections.Counter();overlap_examples=[]
    for image_id,boxes in truth.items():
        for t in boxes:
            label=t['class'];w,h=t['bbox'][2:];sizes[label]['instances']+=1
            sizes[label]['minEdgeAtMost8px']+=min(w,h)<=8
            sizes[label]['minEdgeAtMost16px']+=min(w,h)<=16
            sizes[label]['cocoSmallSourceArea']+=w*h<32**2
            same=[p for p in predictions[image_id] if p['class']==label]
            for name,ps in [('atFloor',same),('atLockedThreshold',[p for p in same if p['confidence']>=thresholds[label]])]:
                best=max((iou(t['bbox'],p['bbox']) for p in ps),default=0.)
                for level in [.1,.3,.5,.75]:opportunities[label][name+'BestIoUAtLeast'+str(level)]+=best>=level
        for a,t in enumerate(boxes):
            for other in boxes[a+1:]:
                if t['class']==other['class']:continue
                score=iou(t['bbox'],other['bbox'])
                if score>=.5:
                    pair=' / '.join(sorted([t['class'],other['class']]));cross[pair]+=1
                    if len(overlap_examples)<20:overlap_examples.append(dict(imageId=image_id,pair=pair,iou=score,boxes=[t['bbox'],other['bbox']]))
    return dict(classAgnosticMatrix=matrix,crossClassMatches=errors,
                sourcePixelSizeCounts={k:dict(v) for k,v in sizes.items()},
                sameClassBestOverlapOpportunities={k:dict(v) for k,v in opportunities.items()},
                crossClassTruthOverlaps=dict(cross),truthOverlapExamples=overlap_examples)


def diagnose(archive,snapshots,validation):
    if validation.get('split')!='valid' or validation.get('thresholdSelectionSplit')!='valid':raise ValueError('VALIDATION_ONLY')
    _,truth,predictions,receipts,identity,sha=read_snapshot(archive,snapshots,'valid')
    if validation['modelIdentity']!=identity:raise ValueError('MODEL_IDENTITY_MISMATCH')
    return dict(schemaVersion=1,methodVersion='validation-localization-taxonomy-v1',split='valid',
        modelIdentity=identity,thresholds=validation['lockedThresholds'],thresholdsRefitted=False,
        images=len(truth),imagesAtPredictionCap=sum(len(p)==300 for p in predictions.values()),
        snapshotSHA256=sha,**analyze(truth,predictions,validation['lockedThresholds']),
        testSplitTouched=False,modelAccepted=False,expertReviewed=False,
        limitations=['Class-agnostic matrix uses confidence-ordered one-to-one matching atIoU0.5; it differs from class-aware operating metrics.',
          'Best-overlap opportunities allow reused predictions and are not recall or proof of a cause.',
          'Cross-class truth overlap is a review cue, never evidence that a publisher label is wrong.',
          'Source pixel size is not model input size; no unsupported training-resolution claim.',
          'Existing prediction floor/cap and provisional source labels/splits still apply.'])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['archive','snapshots','validation','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();r=diagnose(a.archive,a.snapshots,json.loads(a.validation.read_text()))
    with a.output.open('x') as f:json.dump(r,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({k:r[k] for k in ['classAgnosticMatrix','sourcePixelSizeCounts','sameClassBestOverlapOpportunities','crossClassTruthOverlaps']}))
