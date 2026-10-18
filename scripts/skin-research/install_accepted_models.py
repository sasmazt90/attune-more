"""Promote only frozen accepted results; never distribute research-only weights."""
from pathlib import Path
import json,shutil
from prepare_focused_data import ROOT,OUT,CLASSES,sha,write,TARGETS

def read(name):return json.loads((OUT/name).read_text()) if (OUT/name).exists() else None
def main():
    folder=ROOT/'services/core-api/models';registry=dict(version='skin-focused-20261010-v1',classOrder=CLASSES,preprocessing={'RGB':True,'size':[224,224],'mean':[.485,.456,.406],'std':[.229,.224,.225],'cropVersion':'camera-crop-v1'},models={},sourceManifestSHA256=sha(OUT/'dataset-manifest.json'),sourceRights=read('source-rights.json'),pretrainedRights=read('pretrained/rights.json'))
    tests={'type':read('type-final-test.json'),'degrees':read('degrees-final-test.json'),'acne':read('yolox/final-test.json'),'bags':read('bags/final-test.json')}
    assert all(tests.values()),'Finish all independent bounded candidates before release promotion'
    selected=read('type-frozen-selection.json');export=read('type-export.json');name=selected['model']
    reviews=read('type-validation-review.json') or []
    type_source_ok=any(r['model']==name and r['weightsSHA256']==selected['weightsSHA256'] and r.get('visualReviewComplete') and r.get('cleanFaceSourceRequirementMet') for r in reviews)
    candidates={'type':(OUT/name/'selected.onnx',export['onnxSHA256'],tests['type']['accepted'] and type_source_ok,dict(temperature=selected['temperature'],confidenceThreshold=selected['confidenceThreshold'],version=f'skin-type-{name}-20261010-v1',validation=selected['validation'],finalTest=tests['type']['metrics'],sourceQualityAccepted=type_source_ok))}
    degrees=read('degrees-export.json');targets=[h['target'] for h in tests['degrees']['heads'] if h.get('accepted') and h['target'] in ['tone','oil','redness','dry','lines','dark','bags']]
    degree_review=read('degree-source-review.json') or {}
    degree_source_ok=bool(degree_review.get('sourceQualityAccepted'))
    product=read('degrees-product-export.json') if targets and degree_source_ok else None
    if targets and degree_source_ok:assert product and product['targets']==targets and product['noTestInputsRead'] and not product['rejectedHeadWeightsExported'],'Export only accepted product heads before promotion'
    candidates['degrees']=(OUT/('degrees-product.onnx' if product else 'degrees.onnx'),product['sha256'] if product else degrees['sha256'],bool(targets) and degree_source_ok,dict(version='skin-appearance-photo-ridge-20261010-v1',targets=targets if product else TARGETS,acceptedTargets=targets,sourceQualityAccepted=degree_source_ok,rejectedHeadWeightsDistributed=False,normalizationVersion='ordinal-0-5-times-20-v1',wholeFaceOnly=True,localSeverityMap=False))
    for task,experiment in [('acne','yolox'),('bags','bags')]:
        e=read(experiment+'/export.json');frozen=read(experiment+'/frozen-selection.json');domain=read('independent-domain-review.json')
        dataset_accepted=bool(tests[task].get('maskMetricsAccepted') if task=='bags' else tests[task].get('accepted'))
        accepted=dataset_accepted and bool(domain and domain.get(task,{}).get('accepted'))
        candidates[task]=(OUT/experiment/'candidate.onnx',e['sha256'],accepted,dict(version=f'skin-{task}-{experiment}-20261010-v1',confidenceThreshold=frozen['threshold'] if task=='acne' else None,probabilityThreshold=frozen['threshold'] if task=='bags' else None,pixelSegmentation=task=='bags',sourceCoordinateSpace='source-pixels'))
    for task,(path,digest,accepted,metadata) in candidates.items():
        assert path.exists() and sha(path)==digest,'Frozen ONNX hash changed'
        file=f'skin-focused-{task}.onnx'
        if accepted:shutil.copyfile(path,folder/file)
        registry['models'][task]={**metadata,'accepted':accepted,'file':file if accepted else None,'sha256':digest,'rejectedWeightsDistributed':False,'sourceLabelProtocolVerified':False,'cameraDomainAccepted':False}
    # Keep an existing accepted baseline if the new candidate failed. Never
    # replace it with rejected research tensors or silently change class order.
    existing=folder/'skin-focused.json'
    if existing.exists():
        old=json.loads(existing.read_text());assert old['classOrder']==CLASSES
        for task,m in old.get('models',{}).items():
            if m.get('accepted') and not registry['models'].get(task,{}).get('accepted'):registry['models'][task]=m
    existing.write_text(json.dumps(registry,ensure_ascii=False,indent=2),'utf8');write('installed-registry.json',registry);print(json.dumps({task:m['accepted'] for task,m in registry['models'].items()}),flush=True)
if __name__=='__main__':main()
