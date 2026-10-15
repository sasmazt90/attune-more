"""Freeze the one-candidate protocol before any fit; no model imports or data mining."""
import hashlib
import json
import subprocess
from acne_takeover_support import ROOT, OUT, read, digest

DEST = OUT.parent / 'acne-learnability-20261015'


def main():
    DEST.mkdir(exist_ok=True)
    if (DEST/'preregistration.json').exists():
        raise ValueError('Preregistered plan preserved; do not overwrite after seeing results')
    receipt = read(OUT/'clean-pilot-hard-negative/receipt.json')
    sequence = read(OUT/'clean-pilot-hard-negative/sequence.json')
    sequence_hash = hashlib.sha256(json.dumps(sequence,sort_keys=True).encode()).hexdigest()
    assert sequence_hash == receipt['sampleSequenceSHA256'] and len(sequence) == 600
    review = read(OUT/'source-negative-repair-probe.json')
    assert review['trainOnly'] and len(review['components']) == 5
    original = {r['sha256']:r for r in read(OUT/'inputs/original-reviewed-detector-data.json')['rows']}
    cohort = read(OUT/'inputs/controlled_train_cohort.json')
    excluded = set(cohort['pilotControlShas']) | {r['sha256'] for r in read(OUT/'evaluation-step0/summary.json')['rows'] if r['cohort']=='scope-B-development'}
    train = set(cohort['pilotTrainShas'])
    assert not train & excluded
    assert not {original[s]['group'] for s in train} & {original[s]['group'] for s in excluded}
    positive_probes = []; groups = set(); seen = set()
    for row in sequence:
        assert row['sha256'] in train and original[row['sha256']]['split']=='train'
        assert row['sha256'] not in excluded
        key = (row['sha256'],tuple(row['rect']))
        if row['boxes'] and row['group'] not in groups and key not in seen:
            positive_probes.append(row);groups.add(row['group']);seen.add(key)
        if len(positive_probes)==10:break
    assert len(positive_probes)==10
    plan = dict(version='source-object-feature-learnability-v1',sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        candidateCount=1,initialModelSHA256=receipt['initialWeightsSHA256'],steps=150,measureSteps=[0,1,5,10,25,50,100,150],
        seed=20261015,learningRate=3e-5,optimizer='AdamW',weightDecay=.01,warmup=30,cosineEnd=150,gradientClipNorm=5,
        microbatch=1,accumulation=4,confidence=.30,hardNMS=.30,sourceMatchIoU=.50,negativeWeight=20,
        data='Exact previous repaired 600 TRAIN tiles, original Pimple only; reviewed Mole objects; pseudo positives and surroundings UNKNOWN',
        sampleSequenceSHA256=sequence_hash,previousReferenceModelSHA256=receipt['checkpointSHA256'],
        graph='Original model has shared reg_convs, no obj_convs. Clone reg_convs into obj_convs initialized identically, route only obj_preds through copy; shared stems frozen',
        trainable=['head.obj_convs.*.conv.weight (8)','head.obj_preds.*.weight/bias (8)'],
        frozen=['backbone and FPN','head.stems','head.reg_convs and reg_preds','head.cls_convs and cls_preds','all BN affine parameters and statistics'],
        prefitRequired='Each of five objects has nonzero allowed negatives, normalized negative loss and gradients to objectness feature/prediction weights; original positives protected; Step0 output parity before fitting',
        trainSuccess='All five fixed-source object max obj*cls <0.30, retain all Step0 matched original Pimple targets on fixed 10-group TRAIN probes and five object tiles; no box/class/BN change',
        continuation='No long run if known TRAIN mistakes remain. TRAIN success is not generalization. Freeze at <=150 then evaluate same 28 controls and Scope B; require no source-target loss and fewer reviewed-negative FP vs Step0',
        noAdaptiveTuning=True,noProductionActivation=True,scopeBOrControlsUsedForFit=False,
        earlyStop='Safety only: missing label/gradient path, changed frozen state, nonfinite or resource failure; preserve complete checkpoints',
        comparability='Same Step0/data/order/LR/schedule/loss/clip as prior repaired objectness-only arm. Additional feature parameters, backward work and global clip scaling differ; not a causal proof about all backbone features',
        positiveProbes=positive_probes,
        inputHashes={f:digest(OUT/f) for f in ['clean-pilot-hard-negative/sequence.json','source-negative-repair-probe.json','train-clean-support/manifest.json','inputs/original-reviewed-detector-data.json','inputs/train-data-engineering-reviewed-20261013.json']})
    (DEST/'preregistration.json').write_text(json.dumps(plan,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in plan.items() if k not in ['positiveProbes','inputHashes']}))


if __name__=='__main__':main()
