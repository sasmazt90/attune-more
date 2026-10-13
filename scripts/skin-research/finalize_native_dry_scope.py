"""Compute compact public evidence; source photos/payloads stay local and ignored."""
import hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/native-dry-scale-20261013'
def read(path):return json.loads(path.read_text('utf8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
proposal=read(OUT/'independent-v3-comparison.json');gate=read(OUT/'native-gate-comparison.json');path=read(OUT/'native-staging-path.json');sag=read(OUT/'sag-source-scope.json')
label_file=ROOT/'audit-results/dry-sag-component-followup-20261013/object-labels.json';assert sha(label_file)==proposal['labelsSHA256']==read(OUT/'native-gate-protocol.json')['labelsSHA256']
summary=[];objects=[];negatives=[]
for factor in [1.,.5]:
    for kind in ['pul','raw','old']:
        groups=[r['scales'][int(factor==.5)] for r in proposal['rows'] if r['kind']==kind];obj=[o for g in groups for o in g['objects'] if o['label']=='visible-material']
        summary.append(dict(kind=kind,factor=factor,objects=len(obj),previousSingleMSERHits=sum(o['fields']['previousSingleMSER']['objectHit'] for o in obj),newProposalHits=sum(o['fields']['multiscaleNative']['objectHit'] for o in obj),previousNegativePixels=sum(g['reviewedNegative']['previousSingleMSER']['activeSourcePixels'] for g in groups),newNegativePixels=sum(g['reviewedNegative']['multiscaleNative']['activeSourcePixels'] for g in groups)))
for row in proposal['rows']:
    for scale in row['scales']:
        negatives.append(dict(controlIndex=row['controlIndex'],factor=scale['factor'],old=scale['reviewedNegative']['previousSingleMSER'],new=scale['reviewedNegative']['multiscaleNative']))
        for obj in scale['objects']:
            if obj['label']!='visible-material':continue
            stages=['stage:envelope','stage:seeded','stage:geometry','stage:ring','stage:edge','stage:pore-separated']
            objects.append(dict(controlIndex=row['controlIndex'],objectIndex=obj['index'],split=row['split'],kind=row['kind'],sourceSHA256=row['sourceSHA256'],sourceShape=row['sourceShape'],cropOrigin=row['cropOrigin'],referenceSpan=row['referenceSpan'],metricBasis=row['metricBasis'],factor=scale['factor'],fields=obj['fields'],firstFailedObjectCriterionStage=next((k for k in stages if not obj['fields'][k]['objectHit']),None)))
native=[r['scales'][0] for r in proposal['rows']];all_obj=[o for r in native for o in r['objects'] if o['label']=='visible-material'];val=[o for r in proposal['rows'] if r['split']=='validation' for o in r['scales'][0]['objects'] if o['label']=='visible-material']
decision=dict(nativeObjects=len(all_obj),oldNativeHits=sum(o['fields']['previousSingleMSER']['objectHit'] for o in all_obj),newNativeHits=sum(o['fields']['multiscaleNative']['objectHit'] for o in all_obj),validationObjects=len(val),oldValidationHits=sum(o['fields']['previousSingleMSER']['objectHit'] for o in val),newValidationHits=sum(o['fields']['multiscaleNative']['objectHit'] for o in val),oldNegativePixels=sum(r['reviewedNegative']['previousSingleMSER']['activeSourcePixels'] for r in native),newNegativePixels=sum(r['reviewedNegative']['multiscaleNative']['activeSourcePixels'] for r in native),gatedNativeHits=sum(r['gatedHits'] for r in gate['summary'] if r['factor']==1),gatedNegativePixels=sum(r['negativeSourcePixels'] for r in gate['summary'] if r['factor']==1),independentFinalTest=False,normalProductEnabled=False)
assert decision['newNativeHits']==17 and decision['gatedNativeHits']==6
assert all(r['currentProductionUnchanged'] for r in path['rows'])
assert any(r['nativeMetadata']['tiles']>1 and r['nativeMetadata']['sourceImageSize']==[1944,2592] for r in path['rows'])
assert subprocess.check_output(['git','diff','11a6447d1e3419bab867b6d3c70a5ba3804bc606','--','services/core-api/appearance_analysis.py','services/core-api/instant_appearance.py','apps/vehicle-app','packages/shared'],cwd=ROOT)==b''
artifact_names=['protocol.json','independent-v3-parameters.json','independent-v3-comparison.json','native-gate-protocol.json','native-gate-reviewed.json','native-gate-model.json','native-gate-comparison.json','native-staging-path.json','sag-source-scope.json','targeted-sag-selection.json']
artifacts=[dict(path=str((OUT/n).relative_to(ROOT)),bytes=(OUT/n).stat().st_size,sha256=sha(OUT/n)) for n in artifact_names]
evidence=dict(baselineSHA='11a6447d1e3419bab867b6d3c70a5ba3804bc606',BUILD_ID='JO0Xyvupv72uoBiX42mWq',productionMethodChanged=False,labelsSHA256=sha(label_file),annotationScope='same 50 partial optical labels, source/group separated; 21 material, 24 reviewed non-flake, 5 unknown; etiology unconfirmed',proposalDecision=decision,resolutionComparisons=summary,materialStageAttribution=objects,reviewedNegativeSupport=negatives,componentGate={k:v for k,v in gate.items() if k!='rows'},nativeAnatomicalPath=path,targetedSag=sag,
    normalProduct=dict(dry='eligible-flake-luma-union-v3',chin='contour-fold-lower-chin-observed-runs-v9',cheek='contour-fold-visible-region-unique-centers-v7',newNativePathSelected=False,oldRecordsRewritten=False),
    limitations=['Multiscale extraction captures material but also pore/gloss texture; 1153 reviewed-negative native pixels versus 4 for the prior single-MSER diagnostic.',
                 'Single native gate loses 11/17 proposal hits and yields 18 false positive components among 23 familiar reviewed negatives; not eligible for production.',
                 'Partial-face component controls have no valid full-face anatomy. Their source-span-320 resampling is optical, not a fabricated normal API payload.',
                 'Native chin gray sampling creates a seven-sample f90 run but residual 4.83 and paired edge zero do not validate a lower-jaw sag target.',
                 'Chin formula structurally requires fold AND local silhouette deflection. Smooth contour-only appearance is not measured; normal shape is not sag ground truth.',
                 'Selected dedbb pleat is mostly submental/neck, 538/2933 pixels within target band, and chin has directional shadow. Cheek 3.03 is not proof of a strong chin positive.'],
    tests=dict(command='python -m pytest tests/unit/test_native_dry_path.py tests/unit/test_observed_chin_tracking.py tests/unit/test_dry_sag_visible_support.py -q',passed=24,productionBuildRun=False,reason='normal source paths unchanged; rejected staging methods never selected'),artifactInventory=artifacts)
target=ROOT/'docs/native-dry-sag-scope-evidence-20261013.json';target.write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n','utf8')
print(json.dumps(dict(decision=decision,resolution=summary,publicEvidenceBytes=target.stat().st_size)))
