"""Report frozen evidence, not a model/file-existence acceptance claim."""
import json
from prepare_focused_data import ROOT,OUT

def read(path):return json.loads((OUT/path).read_text('utf8'))
def n(value):return '—' if value is None else f'{value:.3f}'

def main():
    registry=read('installed-registry.json');type_test=read('type-final-test.json');degrees=read('degrees-final-test.json')
    build=(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text().strip()
    execution=json.loads((ROOT/'audit-results/all-health-20261010/focused-final-execution.json').read_text('utf8'))
    assert execution['buildId']==build and len(execution['checks'])==13 and all(v['exit']==0 for v in execution['checks'].values())
    lines=['# TOGG Attune — focused skin training and integration, 2026-10-10','',
      f'Production BUILD_ID: `{build}`. Exact delivery SHA and served-file hashes: local `audit-results/all-health-20261010/delivery.json` after commit.',
      '', 'UI completion is separate from analysis accuracy. No interim user test, paid call, cloud training, new source search or failed-model fallback is used. All experiments/checkpoints/private photographs remain ignored. The existing source branch and prior fixes are preserved.',
      '', '## Data and protocol', '',
      'Type train/validation/test: 1802/367/342. Masked degree train/validation/test: 124/21/33. Source-family grouping spans both corpora; known duplicates and conflicting classes are excluded. Degree test groups are absent from backbone training/selection. Unknown person links remain; this is not patient-independent validation. Source labels lack a verified expert protocol. Original vendor 640×640 stretch cannot be reversed by cropping.',
      '', 'The numeric corruption filter and initial visual sample did not guarantee clean type inputs. Frozen validation error sheets show residual speckle, makeup, processing and text. This failed source-quality requirement is an additional promotion gate, not a post-test threshold adjustment. No new tuning/retraining cycle on the exposed split is opened. The separate ordinal subset was reviewed on validation and sampled training photographs before its protected test.',
      '', 'Predeclared epoch/patience/wall budgets, preprocessing, baselines, licenses and hashes: `skin-focused-protocol-20261010.md` and `THIRD_PARTY_NOTICES.md`. Wall checks occur at epoch starts and finish the ongoing epoch; recorded elapsed time includes any boundary overrun.',
      '', '## Type: only ResNet18 vs EfficientNet-B0', '', '| Candidate | Validation macro-F1 | Balanced accuracy | Selected checkpoint | Training seconds |', '|---|---:|---:|---|---:|']
    for name in ['resnet18','efficientnet_b0']:
        s=read(name+'/selection.json');lines.append(f"| {name} | {n(s['validation']['macroF1'])} | {n(s['validation']['balancedAccuracy'])} | `{s['weightsSHA256']}` | {n(s['seconds'])} |")
    runtime=read('type-runtime-comparison.json')
    lines+=['', '| Candidate | ONNX bytes | Cold load ms | Median warm inference ms | Session RSS delta bytes | Max parity error |', '|---|---:|---:|---:|---:|---:|']
    import statistics
    for r in runtime:
        lines.append(f"| {r['model']} | {r['modelBytes']} | {n(r['coldLoadMs'])} | {n(statistics.median(r['warmInferenceMs']))} | {r['sessionRSSDelta']} | {r['maxAbsParity']:.8f} |")
    lines+=['', 'Both candidates used the same eight validation inputs, two CPU inference threads and crop/RGB/ImageNet preprocessing. Another bounded detector training process was active during these measurements. They are comparable observations under shared load, not idle-device benchmarks or a demonstrated speedup. RSS deltas do not include the entire interpreter/runtime.']
    m=type_test['metrics'];lines+=['',f"Frozen selected candidate: **{type_test['selected']}**. Protected test n={m['images']}, macro-F1={n(m['macroF1'])}, balanced accuracy={n(m['balancedAccuracy'])}; dataset metric acceptance={type_test['accepted']}; installed acceptance={registry['models']['type']['accepted']}.", '', '| Class | Precision | Recall | F1 | Support |', '|---|---:|---:|---:|---:|']
    for c in m['classes']:lines.append(f"| {c['label']} | {n(c['precision'])} | {n(c['recall'])} | {n(c['F1'])} | {c['support']} |")
    lines+=['', 'Confusion matrix (truth rows/prediction columns, normal/dry/oily/combination): `'+json.dumps(m['confusionMatrix'])+'`.', '', 'Temperature/confidence thresholds use validation only. Confidence never becomes appearance severity. Comparable two-model ONNX size, cold/warm time, parity and process memory: private `type-runtime-comparison.json`; these timings do not establish a camera-domain speedup.', '', '## Eighteen masked ordinal targets', '', '| Target | Validation MAE | Test MAE | Test ordinal agreement | Validation/test support | Frozen target acceptance |', '|---|---:|---:|---:|---|---|']
    for h in degrees['heads']:
        v=h.get('validation',{});t=h.get('test',{});lines.append(f"| {h['target']} | {n(v.get('MAE'))} | {n(t.get('MAE'))} | {n(t.get('ordinalAgreement'))} | {v.get('support',0)}/{t.get('support',0)} | {bool(h.get('accepted'))} |")
    lines+=['', '| Target | Test constant median MAE | Test constant mean MAE | Comparable analytic MAE / learned MAE / n |', '|---|---:|---:|---|']
    for h in degrees['heads']:
        a=h.get('testExistingMethod',{});comparison='unavailable'
        if a.get('available'):
            comparison=f"{n(a['baseline']['MAE'])} / {n(a['model']['MAE'])} / {a['model']['support']}"
        lines.append(f"| {h['target']} | {n(h.get('testMedianBaseline',{}).get('MAE'))} | {n(h.get('testMeanBaseline',{}).get('MAE'))} | {comparison} |")
    lines+=['', 'Per-target train-mean/median and available analytic-method comparisons are retained in `degrees-final-test.json`. Only accepted product targets may be promoted; all heads remain whole-photo predictions. No regional/pixel grade is inferred. Acne grade cannot replace detector-driven card/count/marks. Elasticity is not sagging; dehydration is not biological moisture.', '', '## Native acne detector comparison', '', '| Candidate | Precision | Recall | F1 | AP50 | mAP .50–.95 | TP / unmatched / missed | Unmatched/photo | Images |', '|---|---:|---:|---:|---:|---:|---|---:|---:|']
    for name in ['yolox','fasterrcnn']:
        if not (OUT/name/'final-test.json').exists():
            budget=read(name+'/runtime-budget-review.json')
            assert name=='fasterrcnn' and budget.get('stopped') and not budget.get('trainedCheckpointExists')
            lines.append('| fasterrcnn | — | — | — | — | — | no validated epoch | — | no protected inference |')
            continue
        result=read(name+'/final-test.json');v=result['metrics'];lines.append(f"| {name} | {n(v['precision'])} | {n(v['recall'])} | {n(v['F1'])} | {n(v['AP50'])} | {n(v['mAP50to95'])} | {v['truePositive']} / {v['falsePositive']} / {v['falseNegative']} | {n(v['annotationRelativeFalseCandidatesPerPhoto'])} | {v['images']} |")
    lines+=['', '| Candidate | Completed epochs | Last epoch elapsed seconds | Frozen validation threshold | Checkpoint bytes |', '|---|---:|---:|---:|---:|']
    for name in ['yolox','fasterrcnn']:
        if not (OUT/name/'history.json').exists():
            budget=read(name+'/runtime-budget-review.json');assert budget.get('stopped')
            lines.append(f"| fasterrcnn | 0 validated | {n(budget['elapsedSeconds'])} operational elapsed | no selection | no trained checkpoint |")
            continue
        history=read(name+'/history.json');frozen=read(name+'/frozen-selection.json')
        lines.append(f"| {name} | {len(history)} | {n(history[-1]['seconds'])} | {n(frozen['threshold'])} | {(OUT/name/'selected.safetensors').stat().st_size} |")
    budget_path=OUT/'fasterrcnn/runtime-budget-review.json'
    if budget_path.exists():
        budget=read('fasterrcnn/runtime-budget-review.json')
        if budget.get('stopped'):
            learning=read('fasterrcnn/learning.json')
            lines+=['', f"**Faster-RCNN comparison remains incomplete (runtime-budget FAIL).** Fresh initialization and the train-only {learning['steps']}-step learning-chain check passed (mean loss {n(learning['firstLoss'])} to {n(learning['lastLoss'])}); the tiny check model was discarded before fresh full training. The epoch-start 3600-second rule permitted a first-epoch overrun. An operational 7200-second process ceiling was added during the run, not falsely described as predeclared. At {n(budget['elapsedSeconds'])} seconds no validated checkpoint existed; only the verified owned training process was stopped. Its files/manifest/seed/initialization/learning evidence remain; partial in-memory weights were lost because that original loop had no intermediate checkpoint. No protected-test metric or architecture comparison success is claimed. No restart, new architecture or post-test threshold change was opened."]
            lines+=['', 'The epoch-boundary program was archived locally before changing the source. The future detector loop now checks its wall budget between batches, writes atomic partial safetensors/progress every 100 batches and saves partial weights before a budget exception. Partial weights are explicitly ineligible for validation selection and do not include optimizer state. This correction was syntax-checked; no new expensive training or retroactive recovery of the stopped in-memory weights is claimed.']
    lines+=['', '| Research export | ONNX bytes | Cold session load ms | Median warm ms | Max parity error |', '|---|---:|---:|---:|---:|']
    for name in ['yolox','bags']:
        e=read(name+'/export.json');lines.append(f"| {name} | {e['bytes']} | {n(e['coldLoadSeconds']*1000)} | {n(statistics.median(e['warmSeconds'])*1000)} | {e['maxAbsParity']:.8f} |")
    lines+=['', 'These rejected research exports are not installed. Shared-load timings cover model load/inference only, not the complete native tiled request or clinical performance. No Faster-RCNN production ONNX is claimed; it is the fresh frozen research baseline. Process RSS snapshots are retained in local execution records; no unsupported peak-memory comparison is inferred.']
    bags=read('bags/final-test.json')
    lines+=['', 'The baseline and main detector were configured with the same fresh source split/native crop/tiles. A missing baseline final result is an incomplete comparison, not an inherited old result. Unmatched predictions are annotation-relative errors: unlabelled skin is not a verified healthy negative. Old Faster-RCNN results remain historical failures, not current evidence. Source-coordinate NMS deduplicates overlapping tiles. Boxes are displayed at box resolution, with no Gaussian or GradCAM severity.', '', '## Eye-bag mask', '',f"Frozen polygon-supported test: n={bags['annotatedROIs']} ROIs, Dice={n(bags['Dice'])}, IoU={n(bags['IoU'])}; restricted mask metric acceptance={bags['maskMetricsAccepted']}; installed acceptance={registry['models']['bags']['accepted']}.", '', 'Supervision/metrics include actual nonrectangular polygons and a two-source-pixel boundary band. 122 rectangular polygons and 327 box-only annotations are not exact masks. Unknown outer ROI is excluded. These Dice/IoU values cannot establish whole-ROI specificity or separation from pigment, shadow and normal lower lids. Independent native portrait outputs and manual confounder review remain separate in `domain-review` and `independent-domain-review.json`.', '', '## Installed product gates', '', '| Task | Accepted | Version | ONNX hash |', '|---|---|---|---|']
    for task,item in registry['models'].items():lines.append(f"| {task} | {item['accepted']} | {item['version']} | `{item['sha256']}` |")
    lines+=['', 'Rejected ONNX files remain private and are not shipped. The registry records rejection without loading them. No center-surround acne fallback or fake zero fills their gap. Existing real contour/fold bags and other analytic proxies remain independent. Source RGB/background/crop, new overview plus six region views, side-photo ownership, NULL semantics, fixed integer percent presentation and normalization/model-compatible history remain distinct.', '', '## Criterion matrix', '', '| Criterion | Global | Regional | Local layer | Acceptance/gap |', '|---|---|---|---|---|',
      '| Skin type | accepted four-class model only, otherwise NULL | none | none | dataset metrics, clean input and camera-domain acceptance separate |',
      '| Tone / redness | actual union or accepted ordinal head | analytic eligible skin | actual analytic pixel signal | directional lighting/skin-tone confounders remain |',
      '| Oil | eligible highlight union or accepted ordinal head | highlight area | actual highlight signal | natural shiny source miss remains; no moisture/sebum claim |',
      '| Acne | deduplicated accepted source candidates | same owned candidates | source boxes/marks, not severity mask | detector plus independent domain gate; failed candidate yields NULL |',
      '| Sagging | supported lower-face contour/fold summary | visible anatomy only | actual supported contour/fold only | some bands lack support; not elasticity |',
      '| Dryness | eligible flake union or accepted ordinal head | flake candidates | actual eligible flake signal | pores/JPEG/shine confounders and natural positive support remain limited |',
      '| Lines / dark circles | observed periorbital or accepted whole-photo target | local outer-corner/lower-lid | actual analytic signals | expression/lighting/detail confounders remain |',
      '| Eye bags | observed contour or accepted mask/whole-photo target | actual lower lid | contour or accepted genuine mask | mask-specificity/domain acceptance separate from annotated-band Dice |',
      '', 'Global learned scores do not recolor analytic maps into learned severity. Every saved record retains analysis/capture identity, dimensions/transforms, method/normalization/hash and validity. Old six-region records retain six views. There is no total-health aggregate.', '', '## Final evidence and limitations', '',
      'A real cross-module history check caught a compatibility defect: the new seven-view adapter hid numeric indicators from legacy records without schemaVersion 3. The adapter now carries the existing regional rows unchanged. Three focused unit regressions passed; the fresh production dental/history check verifies the old 0.02 contour value as 20 ×10⁻³ contour ratio, not a percentage or fabricated overview. All thirteen current-build controlled checks passed. The initial API assertion before the normal launcher reached running status remains recorded as an unsuccessful startup-timing attempt; it is not copied as final acceptance.', '',
      'Final current-build UI/API execution ledger: `audit-results/all-health-20261010/focused-final-execution.json`; fresh overview/regions/maps/history/quiet desktop/narrow/native200 screenshots are referenced there. Nine current-build captures were manually inspected; their file hashes and concrete observations are in `final-ui/visual-review.json`. The failed preliminary native200 scan remains recorded: vehicle-state safety lock returned to start and screenshot capture timed out during concurrent training. Its first desktop pass is not final-build acceptance.', '',
      'Source-family bootstrap intervals use frozen outputs only (`frozen-group-uncertainty.json`); they do not estimate unknown person linkage, annotation bias or camera-domain shift. NASA high-detail portraits are FRONT-only. The three-angle video is controlled pose evidence, not three high-detail people or physical user acceptance.', '',
      'Production npm audit: 0. Development audit: **7 high + 2 moderate remain**. No forced dependency change or paid API call was added. Physical eye closure/hand/object positives, auditory pronunciation and broader natural clinical accuracy are not inferred from callback/fixture/playback success. Normal profile/history are untouched by audits.', '',
      '**Full skin analysis/user final acceptance is not automatically ready because the UI/build passed. The concrete frozen model gates and natural/physical gaps above control that decision.**']
    ledger_path=ROOT/'audit-results/all-health-20261010/focused-final-execution.json'
    if ledger_path.exists():
        ledger=json.loads(ledger_path.read_text('utf8'));assert ledger['buildId']==build
        lines+=['', '## Current production execution', '', '| Check | Exit | Seconds | Fresh log |', '|---|---:|---:|---|']
        for name,entry in ledger['checks'].items():
            lines.append(f"| {name} | {entry['exit']} | {n(entry['seconds'])} | `{entry['log']}` |")
        api=ROOT/'audit-results/focused-skin-20261010/api-final/proof.json'
        if api.exists():
            proof=json.loads(api.read_text('utf8'));assert proof['buildId']==build
            times=proof['firstVsWarmRequestMs']
            lines+=['',f"Normal-launcher API: first request {n(times[0])} ms, repeated same-source request {n(times[1])} ms. These are complete request times, not isolated inference. Source-hash rejection and invalid-quality NULL/no-map checks passed. No normal history record was added."]
            runs=read('api-final/runs-private.json')
            lines.append(f"Normal backend RSS before/after first request: {runs[0]['rssBefore']} / {runs[0]['rssAfter']} bytes; repeat: {runs[1]['rssBefore']} / {runs[1]['rssAfter']} bytes. These are process snapshots, not peak ONNX memory.")
            model_time=runs[0]['general'].get('modelInference',{}).get('degrees',{})
            if model_time:
                lines.append(f"Accepted degree ONNX session initialization {n(model_time['loadMs'])} ms; first degree inference {n(model_time['inferenceMs'])} ms. Initialization is cached for the process; its recorded load time on subsequent results is not a repeated load. Image decoding/CV/map encoding and camera-worker preparation are outside these ONNX timings.")
        scan=ROOT/'audit-results/all-health-20261010/e2e/focused-final-skin/proof.json'
        if scan.exists():
            proof=json.loads(scan.read_text('utf8'));assert proof['buildId']==build
            lines+=['', '| Controlled scan | Worker initialization round trip ms | First frame round trip ms | Median later frame round trip ms |', '|---|---:|---:|---:|']
            for i,run in enumerate(proof['runs']):
                t=run['cameraWorkerTiming'];lines.append(f"| {'Desktop' if i==0 else 'Native browser 200%'} | {n(t['initializeRoundTripMs'][0])} | {n(t['firstFrameRoundTripMs'])} | {n(t['medianFrameRoundTripMs'])} |")
            lines+=['', 'Worker round trips include asset/runtime initialization or frame IPC/inference/response. Concurrent CPU training was active. They do not prove a speedup against the earlier approximately 19-second cold preparation. Camera preparation, accepted backend ONNX initialization, inference and complete API requests are reported separately.']
    lines+=['', '**Ready for full user acceptance: NO.** Skin type, acne detection and learned eye-bag specificity failed their frozen gates. The Faster-RCNN comparison is incomplete at the operational ceiling. Natural oil/dryness and physical/audio acceptance gaps remain. The delivered UI and limited accepted global redness head do not close these accuracy gaps. No further user test is requested to finish independent work.']
    (ROOT/'docs/skin-focused-results-20261010.md').write_text('\n'.join(lines)+'\n','utf8')
    legacy=ROOT/'docs/all-health-delivery-20261010.md'
    text=legacy.read_text('utf8')
    marker='<!-- focused-current-release -->'
    if marker not in text:
        text=marker+'\n# Güncel odaklı cilt teslimi\n\nSonlu eğitim, Genel Bakış ve güncel model/harita kabulü: [skin-focused-results-20261010.md](skin-focused-results-20261010.md). Aşağıdaki önceki beş-modül raporu eski build kanıtı ve korunmuş düzeltmelerin bağlamıdır; güncel final kabul değildir. Önceki merkez/çevre sivilce yolu artık normal API’da etkin değildir. Sağlanan yeni Roboflow/Kaggle kaynaklarıyla odaklı eğitim tamamlandığından eski ACNE-DET erişim sorunu güncel ana eğitim engeli değildir.\n\n'+text
    legacy.write_text(text,'utf8')
    print('Wrote frozen-result report; no aggregate acceptance inferred')

if __name__=='__main__':main()
