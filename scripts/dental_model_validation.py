"""Additional frozen held-out diagnostics; never tunes the chosen model."""
import hashlib, json, sys, time
from collections import defaultdict
from importlib.metadata import version
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'audit-results/combined-health-20261008/dental-training'


def overlap(a, b):
    intersection = max(0, min(a[2], b[2])-max(a[0], b[0])) * max(0, min(a[3], b[3])-max(a[1], b[1]))
    union = (a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-intersection
    return intersection/max(union, 1e-9)


def retained_detection_calibration(items, predictions, threshold, classes):
    """Correct localization/class at IoU .5, among retained predictions only."""
    records = defaultdict(list)
    for item, candidates in zip(items, predictions, strict=True):
        for category in range(len(classes)):
            truth = [[x, y, x+w, y+h] for cls, x, y, w, h in item['boxes'] if cls == category]
            matched = set()
            selected = sorted((p for p in candidates if int(p[6]) == category and p[4]*p[5] >= threshold), key=lambda p:p[4]*p[5], reverse=True)
            for candidate in selected:
                best = max(((overlap(candidate[:4], box), i) for i, box in enumerate(truth) if i not in matched), default=(0, -1))
                correct = best[0] >= .5
                if correct:matched.add(best[1])
                records[category].append((float(candidate[4]*candidate[5]), int(correct)))
    result = []
    for category, code in enumerate(classes):
        rows = records[category]
        bins = []
        for index in range(10):
            members = [(score, target) for score, target in rows if min(9, int(score*10)) == index]
            if members:
                bins.append(dict(lower=index/10, upper=(index+1)/10, count=len(members), meanConfidence=float(np.mean([r[0] for r in members])), localizedPrecision=float(np.mean([r[1] for r in members]))))
        result.append(dict(classCode=code, retainedPredictions=len(rows),
            Brier=float(np.mean([(s-y)**2 for s,y in rows])) if rows else None,
            ECE=sum(b['count']*abs(b['meanConfidence']-b['localizedPrecision']) for b in bins)/len(rows) if rows else None,
            bins=bins))
    return dict(scope='Retained detections at frozen threshold; correctness is same-class IoU>=0.5. Not disease probability, not full-population calibration; omitted detections are excluded.', classes=result)


def group_f1_intervals(items,predictions,threshold,classes,draws=200):
    """Same group-count bootstrap as the frozen trainer, with class intervals."""
    groups=defaultdict(list)
    for index,item in enumerate(items):groups[item['group']].append(index)
    counts=[]
    for indices in groups.values():
        rows=[items[i] for i in indices]
        diagnostic=retained_detection_calibration(rows,[predictions[i] for i in indices],threshold,classes)
        group=[]
        for category,entry in enumerate(diagnostic['classes']):
            tp=round(sum(b['count']*b['localizedPrecision'] for b in entry['bins']))
            truth=sum(cls==category for row in rows for cls,*_ in row['boxes'])
            assert 0<=tp<=truth
            group.append([tp,entry['retainedPredictions']-tp,truth-tp])
        counts.append(group)
    counts=np.asarray(counts,dtype=np.int64);rng=np.random.default_rng(8102026);samples=[]
    for _ in range(draws):
        value=counts[rng.integers(0,len(counts),len(counts))].sum(axis=0)
        samples.append(2*value[:,0]/np.maximum(2*value[:,0]+value[:,1]+value[:,2],1))
    samples=np.asarray(samples)
    return dict(groups=len(groups),draws=draws,seed=8102026,
                macroF1_95CI=np.quantile(samples.mean(axis=1),[.025,.975]).tolist(),
                classF1_95CI=np.quantile(samples,[.025,.975],axis=0).T.tolist(),
                scope='Case/capture/duplicate group resampling; patient independence unverified. Zero-denominator class F1 is zero, matching the registered trainer.')


def main():
    import onnxruntime as ort
    import cv2, psutil
    model_dir = ROOT / 'services/core-api/models'
    manifest_path = model_dir / 'dental-yolox-s.json'
    manifest = json.loads(manifest_path.read_text('utf8'))
    history = json.loads((OUT/'training-history.json').read_text('utf8'))
    selected = max(history, key=lambda row:row['validation']['macroF1'])
    assert manifest['confidenceThreshold'] == selected['validation']['threshold']
    assert manifest['epochs'] == len(history)
    training_script = ROOT/'scripts/train_dental_yolox.py'
    registered = json.loads((OUT/'early-stopping-config.json').read_text('utf8'))
    assert hashlib.sha256(training_script.read_bytes()).hexdigest()==registered['trainingScriptSHA256']
    path = model_dir / 'dental-yolox-s.onnx'
    assert hashlib.sha256(path.read_bytes()).hexdigest() == manifest['modelHash']
    inventory = json.loads((OUT/'dataset-split.json').read_text('utf8'))
    items = [row for row in inventory['rows'] if row['split'] == 'test']
    predictions = json.loads((OUT/'heldout-predictions.json').read_text('utf8'))
    assert len(items) == len(predictions) == manifest['evaluation']['images']
    calibration = retained_detection_calibration(items, predictions, manifest['confidenceThreshold'], manifest['classes'])
    intervals=group_f1_intervals(items,predictions,manifest['confidenceThreshold'],manifest['classes'])
    assert np.allclose(intervals['macroF1_95CI'],manifest['evaluation']['groupBootstrapF1_95CI'],rtol=0,atol=1e-9),'Do not silently replace the frozen bootstrap estimator'
    # Performance uses fixed already held-out photos, without tuning outputs.
    options = ort.SessionOptions(); options.intra_op_num_threads=2; options.inter_op_num_threads=1
    process = psutil.Process(); baseline = process.memory_info().rss; started=time.perf_counter()
    session=ort.InferenceSession(str(path), sess_options=options, providers=['CPUExecutionProvider'])
    load_ms=(time.perf_counter()-started)*1000; elapsed=[]; sizes=[]; rss=[baseline,process.memory_info().rss]
    size=manifest['inputSize']
    for row in items[:20]:
        image=cv2.imread(row['path']); assert image is not None
        ratio=min(size/image.shape[0],size/image.shape[1]); resized=cv2.resize(image,(int(image.shape[1]*ratio),int(image.shape[0]*ratio)))
        canvas=np.full((size,size,3),114,np.uint8);canvas[:resized.shape[0],:resized.shape[1]]=resized
        tensor=canvas.transpose(2,0,1)[None].astype(np.float32)
        started=time.perf_counter(); output=session.run(None, {'images':tensor})[0];elapsed.append((time.perf_counter()-started)*1000)
        assert np.isfinite(output).all();sizes.append(list(output.shape));rss.append(process.memory_info().rss)
    proof=dict(modelHash=manifest['modelHash'], modelBytes=path.stat().st_size,
        libraryVersions=dict(onnxruntime=ort.__version__,opencv=cv2.__version__,numpy=np.__version__),
        calibration=calibration, groupBootstrap=intervals, measuredCPUThreads=2, sessionLoadMs=load_ms,
        inferenceMs=elapsed, medianInferenceMs=float(np.median(elapsed[1:])),
        sourceImages=20, outputShapes=sizes, sampledRSSBytes=dict(baseline=baseline,maximum=max(rss),after=rss[-1]),
        hardwareAcceptance=False, clinicalValidation=False)
    # Illustrative positive execution check, after selection is frozen. The
    # normal API front fixture may legitimately contain no retained candidates.
    # A whole-frame ROI is explicit here because this is a complete intraoral
    # source, not a FaceWorker/camera acceptance or a new population metric.
    def retained_matches(index):
        item=items[index]
        return sum(any(int(p[6])==cls and overlap(p[:4],[x,y,x+w,y+h])>=.5
                       for cls,x,y,w,h in item['boxes'])
                   for p in predictions[index] if p[4]*p[5]>=manifest['confidenceThreshold'])
    positive_index=max(range(len(items)),key=retained_matches)
    assert retained_matches(positive_index)>0,'No held-out positive can support this execution check'
    positive_source=items[positive_index]
    assert hashlib.sha256(Path(positive_source['path']).read_bytes()).hexdigest()==positive_source['sha256']
    positive_image=cv2.imread(positive_source['path']);assert positive_image is not None
    sys.path.insert(0,str(ROOT/'services/core-api'))
    import dental_analysis as product
    candidates,metadata=product.model_candidates(positive_image,np.ones(positive_image.shape[:2],bool))
    assert metadata['quality']=='valid' and metadata['modelHash']==manifest['modelHash']
    assert metadata['runtimeVersions']==proof['libraryVersions'] and candidates
    actual_match=False
    for candidate in candidates:
        box=candidate['bounds'];x,y,w,h=(box[key] for key in ('x','y','width','height'))
        assert 0<=x<x+w<=positive_image.shape[1]+.001 and 0<=y<y+h<=positive_image.shape[0]+.001
        assert candidate['classCode'] in manifest['classes'] and 0<=candidate['confidence']<=1
        actual_match|=any(manifest['classes'][cls]==candidate['classCode'] and overlap([x,y,x+w,y+h],[gx,gy,gx+gw,gy+gh])>=.5
                          for cls,gx,gy,gw,gh in positive_source['boxes'])
    assert actual_match,'Real product-coordinate candidates must match at least one original held-out label'
    proof['productPositiveCoordinateCheck']=dict(
        status='PASS',heldoutIndex=positive_index,sourceSHA256=positive_source['sha256'],
        modelHash=manifest['modelHash'],sourceWidth=positive_image.shape[1],sourceHeight=positive_image.shape[0],
        frozenThreshold=manifest['confidenceThreshold'],actualProductFunction='dental_analysis.model_candidates',
        candidates=candidates,atLeastOneSameClassIoU50Match=True,
        scope='Illustrative positive execution and source coordinates; full intraoral source supplied as ROI. Not automatic camera capture, physical acceptance, or population accuracy.')
    (OUT/'frozen-model-diagnostics.json').write_text(json.dumps(proof,indent=2),'utf8')
    manifest['additionalDiagnostics']={k:v for k,v in proof.items() if k not in ('modelHash','hardwareAcceptance','clinicalValidation','productPositiveCoordinateCheck')}
    # Detailed public-fixture candidate coordinates stay in the local evidence,
    # rather than turning the deployable model manifest into a case-level dataset.
    manifest['additionalDiagnostics']['productPositiveCoordinateCheck']=dict(
        status='PASS',candidateCount=len(candidates),sourceBoundsValid=True,
        atLeastOneSameClassIoU50Match=True,scope=proof['productPositiveCoordinateCheck']['scope'])
    manifest['selectedEpoch']=selected['epoch']
    manifest['evaluation']['classGroupBootstrapF1_95CI']=intervals['classF1_95CI']
    manifest['evaluation']['metricDefinition']='Score-ranked same-class greedy IoU matching; 101-point interpolated AP; macro over raw classes; IoU .5 and .5:.95 step .05. No area strata or official COCO evaluator/maxDets protocol claimed.'
    manifest['trainingProvenance']={
        'trainingScriptSHA256':registered['trainingScriptSHA256'],
        'inventorySHA256':hashlib.sha256((OUT/'dataset-split.json').read_bytes()).hexdigest(),
        'historySHA256':hashlib.sha256((OUT/'training-history.json').read_bytes()).hexdigest(),
        'bestWeightsSHA256':hashlib.sha256((OUT/'best-weights.npz').read_bytes()).hexdigest(),
        'completedEpochs':len(history),'selectedEpoch':selected['epoch'],
        'validationSelectedThreshold':selected['validation']['threshold'],
        'trainingLibraryVersions':{name:version(name) for name in ('torch','torchvision','onnx')},
        'partitionImages':inventory['partitions'],'uniqueLabeledImages':inventory['uniqueLabeledImages'],
        'groups':inventory['groups'],'patientIndependent':False,'groupLimitation':inventory['groupLimitation']}
    manifest_path.write_text(json.dumps(manifest,indent=2),'utf8')
    print(json.dumps(proof))


if __name__ == '__main__':main()
