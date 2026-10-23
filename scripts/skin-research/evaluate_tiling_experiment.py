"""Replay a bounded validation-only tiling diagnosis with pinned raw responses.

Three preselected failures plus three deterministic filename-hash controls are
reported separately. This is not an unbiased estimate or a threshold fit.
"""
import argparse
import collections
import gzip
import hashlib
import json
from pathlib import Path
import zipfile
from detector_tiling import corner_tiles, map_predictions, suppress_duplicates
from evaluate_detector_snapshot import CLASSES, finite, read_snapshot, match_events, point, coco_metrics


def evaluate(archive, baseline, tiles, locked_validation):
    data, truth, full, _, identity, _ = read_snapshot(archive, baseline, 'valid')
    if locked_validation.get('modelIdentity') != identity:
        raise ValueError('BASELINE_IDENTITY_MISMATCH')
    if (locked_validation.get('thresholdSelectionSplit') != 'valid' or any(
        not finite(locked_validation.get('lockedThresholds',{}).get(k)) or
        not .05 <= locked_validation['lockedThresholds'][k] <= .95 for k in CLASSES)):
        raise ValueError('INVALID_VALIDATION_THRESHOLDS')
    rows=json.loads(gzip.decompress(Path(tiles).read_bytes()))['records']
    by_image=collections.defaultdict(list)
    for row in rows:by_image[row['imageId']].append(row)
    failures=[26,144,19]
    # Selection rule fixed before requesting new inferences.
    bundle=json.loads(gzip.decompress(Path(baseline).read_bytes()))
    names={json.loads(r['rawJSON'])['source']['cocoImageId']:json.loads(r['rawJSON'])['source']['filename'] for r in bundle['records'] if r['split']=='valid'}
    controls=sorted((i for i in names if i not in failures),key=lambda i:hashlib.sha256(names[i].encode()).hexdigest())[:3]
    selected=failures+controls
    if set(by_image)!=set(selected):raise ValueError('EXPERIMENT_SELECTION_MISMATCH')
    images={im['id']:im for im in data['images']}; tiled={}; receipts=[]
    for image_id, rs in by_image.items():
        im=images[image_id]; expected=corner_tiles(im['width'],im['height'])
        if sorted(tuple(r['tile']) for r in rs)!=sorted(expected):raise ValueError('INCOMPLETE_TILES')
        ps=[]
        for r in rs:
            res=r['response']['result'];model=res['resolved_model']
            if (r['model']!=identity['modelId'] or model['model_id']!=identity['modelId'] or
                r['package']!=identity['modelPackageId'] or model['model_package_id']!=identity['modelPackageId']):
                raise ValueError('TILE_MODEL_IDENTITY_MISMATCH')
            if res['image']!={'width':r['tile'][2],'height':r['tile'][3]}:raise ValueError('TILE_DIMENSION_MISMATCH')
            ps.extend(map_predictions(res['predictions'],r['tile']))
            receipts.append(dict(imageId=image_id,tile=r['tile'],inferenceId=res['inference_id'],
                payloadSHA256=r['sha256'],sourceSHA256=r['sourceSHA256'],predictions=len(res['predictions'])))
        tiled[image_id]=suppress_duplicates(ps,.5)
    def metrics(ids,ps):
        ds=dict(data,images=[images[i] for i in ids],annotations=[a for a in data['annotations'] if a['image_id'] in ids])
        ts={i:truth[i] for i in ids};pred={i:ps[i] for i in ids}
        points={}
        for label in CLASSES:
            events,total=match_events(ts,pred,label)
            points[label]=dict(**point(events,total,locked_validation['lockedThresholds'][label]),groundTruthCount=total)
        return dict(operatingPoints=points,coco=coco_metrics(ds,pred,300),predictions=sum(map(len,pred.values())))
    groups={key:dict(imageIds=ids,full=metrics(ids,full),tiled=metrics(ids,tiled)) for key,ids in
            [('diagnosticFailures',failures),('hashControls',controls),('all',selected)]}
    return dict(schemaVersion=1,methodVersion='validation-four-corner-tiling-v1',split='valid',
        modelIdentity=identity,tileFraction=.6,nmsIoU=.5,confidenceFloor=.05,
        thresholds=locked_validation['lockedThresholds'],thresholdsRefitted=False,
        selection='Three prior worst-case examples plus first three SHA256(filename) controls excluding failures',
        groups=groups,receipts=receipts,images=len(selected),inferences=len(receipts),
        tilesAtPredictionCap=sum(r['predictions']==300 for r in receipts),
        snapshotSHA256=hashlib.sha256(Path(tiles).read_bytes()).hexdigest(),
        modelAccepted=False,testSplitTouched=False,
        limitations=['Small diagnostic sample; selected failures are deliberately biased; report controls separately.',
         'Tiling changes image context, input scale, JPEG encoding and per-frame prediction budget together; no isolated causal claim.',
         'Original publisher truth remains unchanged, with unverified semantic/negative coverage and subject independence.',
         'Whole validation and independent camera evaluation are still required before acceptance.'])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['archive','baseline','tiles','locked-validation','output']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();r=evaluate(a.archive,a.baseline,a.tiles,json.loads(a.locked_validation.read_text()))
    with a.output.open('x') as f:json.dump(r,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({'images':r['images'],'inferences':r['inferences'],'groups':r['groups']}))
