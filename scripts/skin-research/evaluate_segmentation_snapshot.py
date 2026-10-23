"""Pinned COCO instance-mask evaluation, never bounding-box-as-mask scoring.

Thresholds are fitted on validation only and locked for the source test. Source
annotations may be incomplete: mask disagreement is not normal-skin evidence.
"""
import argparse,collections,contextlib,gzip,hashlib,io,json
from pathlib import Path
import numpy as np
from pycocotools import mask as M
from pycocotools.coco import COCO
from pycocotools.cocoeval import COCOeval
from audit_roadmap_archives import geometry
from evaluate_detector_snapshot import finite,point
import zipfile

VERSION='pinned-coco-instance-mask-evaluation-v1'
CLASSES=('Oily','Redness')


def polygon_rle(polygons,width,height,prediction=False):
    # Require actual polygon supervision. A box-only response must fail rather
    # than silently receiving a rectangle mask. Predicted mask bounds are not
    # reinterpreted as anatomical-region coverage.
    if prediction:
        if len(polygons)!=1 or not isinstance(polygons[0],list) or len(polygons[0])%2:
            raise ValueError('INVALID_PREDICTED_POLYGON')
        p=polygons[0]
        if any(not finite(v) for v in p) or any(not 0<=v<=(width if i%2==0 else height) for i,v in enumerate(p)):
            raise ValueError('INVALID_PREDICTED_POINT')
        # Hosted segmentation can emit an empty contour at low confidence.
        # Preserve it as an empty predicted mask (an unmatched prediction),
        # rather than dropping the detection or substituting its box.
        if len(p)<6:return M.encode(np.zeros((height,width),dtype=np.uint8,order='F'))
        # COCO rasterizes the model's unmodified contour, including self-touching
        # raster boundaries. No polygon repair, simplification or bbox fallback.
        return M.merge(M.frPyObjects(polygons,height,width))
    ann=dict(bbox=[0,0,width,height],segmentation=polygons)
    shape=geometry(ann,width,height)
    if shape['kind'] not in ('polygon','rectangle-polygon'):
        raise ValueError('INVALID_MASK_POLYGON')
    # Predicted rectangles can be legitimate model contours. Source truth must
    # separately pass genuine polygon admission below.
    return M.merge(M.frPyObjects(polygons,height,width))


def read_snapshot(archive,snapshots,split):
    if split not in ('valid','test'):raise ValueError('VALID_OR_TEST_ONLY')
    archive_sha=hashlib.sha256(Path(archive).read_bytes()).hexdigest()
    with zipfile.ZipFile(archive) as z:
        data=json.loads(z.read(split+'/_annotations.coco.json'))
        images={im['id']:im for im in data['images']};cats={c['id']:c['name'] for c in data['categories']}
        truth={i:[] for i in images}
        for a in data['annotations']:
            im=images[a['image_id']];label=cats[a['category_id']]
            if label not in CLASSES:raise ValueError('UNEXPECTED_TRUTH_CLASS')
            if not geometry(a,im['width'],im['height'])['validMask']:raise ValueError('GENUINE_SOURCE_POLYGON_REQUIRED')
            truth[im['id']].append(dict(label=label,rle=polygon_rle(a['segmentation'],im['width'],im['height'])))
        bundle=json.loads(gzip.decompress(Path(snapshots).read_bytes()))
        records=[r for r in bundle['records'] if r['split']==split]
        predictions={};identity=None;receipts=[];ids=set()
        for r in records:
            row=json.loads(r['rawJSON']);source=row['source'];i=source['cocoImageId']
            if i in predictions:raise ValueError('DUPLICATE_IMAGE_PREDICTIONS')
            if i not in images or row['split']!=split or row.get('status')!='ok':raise ValueError('SNAPSHOT_SPLIT_OR_STATUS_MISMATCH')
            im=images[i];payload=z.read(split+'/'+im['file_name'])
            if (source['archiveSHA256']!=archive_sha or source['imageSHA256']!=hashlib.sha256(payload).hexdigest()
                or source['filename']!=im['file_name']):raise ValueError('SOURCE_IDENTITY_MISMATCH')
            if row['image']!={'width':im['width'],'height':im['height']}:raise ValueError('IMAGE_DIMENSION_MISMATCH')
            resolved=row['resolvedModel'];key=(row['requestedModel'],resolved['model_package_id'])
            if row['requestedModel']!=resolved['model_id'] or not key[1]:raise ValueError('RESOLVED_MODEL_MISMATCH')
            if identity is not None and key!=identity:raise ValueError('MIXED_MODEL_IDENTITY')
            identity=key
            if row['confidenceFloor']!=.05:raise ValueError('CONFIDENCE_FLOOR_MISMATCH')
            if not row['inferenceId'] or row['inferenceId'] in ids:raise ValueError('INVALID_INFERENCE_RECEIPT')
            ids.add(row['inferenceId']);ps=[]
            for p in row['predictions']:
                if p.get('class') not in CLASSES or not finite(p.get('confidence')) or not .05<=p['confidence']<=1:raise ValueError('INVALID_PREDICTION')
                points=p.get('points')
                if not isinstance(points,list):raise ValueError('PREDICTED_POLYGON_REQUIRED')
                if any(not isinstance(v,dict) or not finite(v.get('x')) or not finite(v.get('y')) for v in points):raise ValueError('INVALID_PREDICTED_POINT')
                poly=[v[k] for v in points for k in ('x','y')]
                mask=polygon_rle([poly],im['width'],im['height'],prediction=True)
                ps.append(dict(label=p['class'],score=p['confidence'],rle=mask,emptyMask=not bool(M.area(mask))))
            predictions[i]=ps
            receipts.append(dict(imageId=i,inferenceId=row['inferenceId'],predictionCount=len(ps),emptyPredictedMasks=sum(p['emptyMask'] for p in ps),imageSHA256=source['imageSHA256'],rawJSONSHA256=hashlib.sha256(r['rawJSON'].encode()).hexdigest()))
    if set(predictions)!=set(images) or identity is None:raise ValueError('INCOMPLETE_SPLIT_PREDICTIONS')
    return data,truth,predictions,dict(modelId=identity[0],modelPackageId=identity[1]),receipts,archive_sha


def matching_events(truth,predictions,label):
    events=[];total=0
    for i,rows in truth.items():
        ts=[r['rle'] for r in rows if r['label']==label];total+=len(ts);used=set()
        ps=sorted((p for p in predictions[i] if p['label']==label),key=lambda p:-p['score'])
        overlaps=M.iou([p['rle'] for p in ps],ts,[0]*len(ts)) if ps and ts else np.zeros((len(ps),len(ts)))
        for n,p in enumerate(ps):
            score,k=max(((float(overlaps[n,k]),k) for k in range(len(ts)) if k not in used),default=(0.,-1))
            matched=score>=.5
            if matched:used.add(k)
            events.append((p['score'],matched))
    return events,total


def operating_points(truth,predictions,split,locked=None):
    if split=='test' and locked is None:raise ValueError('TEST_REQUIRES_VALIDATION_LOCK')
    result={}
    for label in CLASSES:
        events,total=matching_events(truth,predictions,label)
        if split=='valid':
            p=max((point(events,total,k/20) for k in range(1,20)),key=lambda p:(p['f1'] or 0.,p['threshold']))
        elif split=='test':
            t=locked.get(label)
            if not finite(t) or not .05<=t<=.95:raise ValueError('INVALID_VALIDATION_THRESHOLD')
            p=point(events,total,t)
        else:raise ValueError('VALID_OR_TEST_ONLY')
        result[label]=dict(**p,groundTruthCount=total)
    return result


def coco_metrics(data,predictions,max_detections=100):
    cats={c['name']:c['id'] for c in data['categories'] if c['name'] in CLASSES}
    # COCO source area metadata can encode enclosing-box area. Derive mask area
    # for mask evaluation, record the policy, and leave the source archive intact.
    evaluation_data=dict(data,info=data.get('info',{}),annotations=[dict(a,area=float(M.area(polygon_rle(a['segmentation'],next(im['width'] for im in data['images'] if im['id']==a['image_id']),next(im['height'] for im in data['images'] if im['id']==a['image_id']))))) for a in data['annotations']])
    rows=[dict(image_id=i,category_id=cats[p['label']],segmentation=p['rle'],score=p['score']) for i,ps in predictions.items() for p in ps]
    with contextlib.redirect_stdout(io.StringIO()):
        gt=COCO();gt.dataset=evaluation_data;gt.createIndex()
        if rows:guess=gt.loadRes(rows)
        else:guess=COCO();guess.dataset=dict(images=data['images'],categories=data['categories'],annotations=[]);guess.createIndex()
        e=COCOeval(gt,guess,'segm');e.params.imgIds=sorted(predictions);e.params.catIds=sorted(cats.values());e.params.maxDets=[1,10,max_detections]
        e.evaluate();e.accumulate()
    precision=e.eval['precision'];mean=lambda a:float(a[a>=0].mean()) if (a>=0).any() else None
    names={v:k for k,v in cats.items()}
    return dict(maxDetectionsPerImage=max_detections,map50=mean(precision[0,:,:,0,-1]),map50_95=mean(precision[:,:,:,0,-1]),perClass={names[c]:dict(map50=mean(precision[0,:,n,0,-1]),map50_95=mean(precision[:,:,n,0,-1])) for n,c in enumerate(e.params.catIds)})


def union_diagnostics(data,truth,predictions,thresholds):
    """Class-union disagreement, separate from instance-count granularity.

    Absent publisher masks remain unknown rather than normal/negative skin.
    No face clipping, area fitting or threshold selection is performed here.
    """
    if any(not finite(thresholds.get(k)) or not .05<=thresholds[k]<=.95 for k in CLASSES):
        raise ValueError('INVALID_VALIDATION_THRESHOLD')
    images={im['id']:im for im in data['images']};result={}
    for label in CLASSES:
        rows=[]
        for i,ts in truth.items():
            im=images[i];empty=lambda:M.encode(np.zeros((im['height'],im['width']),dtype=np.uint8,order='F'))
            a=[t['rle'] for t in ts if t['label']==label]
            b=[p['rle'] for p in predictions[i] if p['label']==label and p['score']>=thresholds[label]]
            gt=M.merge(a) if a else empty();ps=M.merge(b) if b else empty()
            ga,pa=int(M.area(gt)),int(M.area(ps));intersection=int(M.area(M.merge([gt,ps],intersect=True)));union=ga+pa-intersection
            rows.append(dict(imageId=i,sourceInstances=len(a),predictedInstances=len(b),annotatedPixels=ga,predictedPixels=pa,
                intersectionPixels=intersection,unionPixels=union,iou=intersection/union if union else None,
                annotationCoverageFraction=intersection/ga if ga else None))
        intersection=sum(r['intersectionPixels'] for r in rows);union=sum(r['unionPixels'] for r in rows)
        ga=sum(r['annotatedPixels'] for r in rows);pa=sum(r['predictedPixels'] for r in rows)
        positive=[r for r in rows if r['annotatedPixels']]
        result[label]=dict(annotatedPixels=ga,predictedPixels=pa,intersectionPixels=intersection,unionPixels=union,
            microIoU=intersection/union if union else None,annotationCoverageFraction=intersection/ga if ga else None,
            predictedFractionOverlappingAnnotations=intersection/pa if pa else None,
            meanIoUOnAnnotatedImages=sum(r['iou'] for r in positive)/len(positive) if positive else None,
            annotatedImages=len(positive),imagesWithoutSourceAnnotations=len(rows)-len(positive),rows=rows)
    return dict(thresholds=thresholds,perClass=result,normalRegionsInferred=False,
                scope='Full source frames, fixed validation thresholds. Class unions ignore publisher instance subdivision; incomplete annotations limit interpretation.')


def evaluate(archive,snapshots,split,validation=None):
    data,truth,predictions,identity,receipts,sha=read_snapshot(archive,snapshots,split)
    if split=='test' and (not validation or validation.get('split')!='valid' or validation.get('methodVersion')!=VERSION or validation.get('modelIdentity')!=identity or validation.get('sourceArchiveSHA256')!=sha):raise ValueError('MATCHING_VALIDATION_MASK_LOCK_REQUIRED')
    ps=operating_points(truth,predictions,split,validation.get('lockedThresholds') if validation else None)
    return dict(schemaVersion=1,methodVersion=VERSION,split=split,modelIdentity=identity,sourceArchiveSHA256=sha,
        snapshotSHA256=hashlib.sha256(Path(snapshots).read_bytes()).hexdigest(),images=len(truth),
        operatingPoints=ps,thresholdSelectionSplit='valid',lockedThresholds={k:p['threshold'] for k,p in ps.items()},
        coco=[coco_metrics(data,predictions,cap) for cap in (100,300)],imageReceipts=receipts,
        evaluationGeometry='instance-polygons-not-boxes',evaluationAreaPolicy='Derived from polygon raster only; source archive unchanged',
        emptyPredictedMasks=sum(r['emptyPredictedMasks'] for r in receipts),
        predictionRasterPolicy='Unmodified finite in-frame model contours rasterized by COCO. Empty masks count as unmatched predictions; no box fallback or contour repair.',
        modelAccepted=False,cameraAccepted=False,normalRegionsInferred=False,
        limitations=['Incomplete publisher annotations can count unlabelled real appearance as false positives.',
          'Mask matching does not establish normal/dry/sensitivity truth or anatomical regional coverage.',
          'Existing source split and subject-independence limitations remain; synthetic tests validate tooling only.'])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for n in ['archive','snapshots','output']:parser.add_argument('--'+n,type=Path,required=True)
    parser.add_argument('--split',choices=['valid','test'],required=True);parser.add_argument('--locked-validation',type=Path)
    args=parser.parse_args();v=json.loads(args.locked_validation.read_text()) if args.locked_validation else None
    r=evaluate(args.archive,args.snapshots,args.split,v)
    with args.output.open('x') as f:json.dump(r,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({k:r[k] for k in ['images','split','operatingPoints','coco']}))
