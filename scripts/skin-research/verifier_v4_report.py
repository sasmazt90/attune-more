"""Finalize the one V4 round from immutable stored results. Never fits or re-evaluates."""
import collections,sys
from verifier_v4_round import *
from verifier_v4_dev import key

def atomic_text(name,s):
 p=OUT/name;temp=p.with_name(p.name+'.tmp-'+str(os.getpid()))
 with temp.open('w',encoding='utf8') as f:f.write(s);f.flush();os.fsync(f.fileno())
 os.replace(temp,p)

def main():
 data=read(OUT/'data-list.json');cal=read(OUT/'calibration.json');dev=read(OUT/'dev-results.json');vis=read(OUT/'visual-evidence.json')
 assert not dev['selection']['passed'],'REPORT_ASSUMES_THIS_COMPLETED_REJECTED_ROUND'
 photos=sorted(dev['perPhoto']);tab=dev['table'];baseFalse={(ph,key(b)) for ph in photos for b,c in zip(dev['candidateBoxes']['v3'][ph],dev['perPhotoClasses']['v3'][ph]['classes']) if c=='false'}
 diff={}
 for n in tab:
  nf={(ph,key(b)) for ph in photos for b,c in zip(dev['candidateBoxes'][n][ph],dev['perPhotoClasses'][n][ph]['classes']) if c=='false'}
  diff[n]=dict(removedVsV3=[dict(photo=ph,box=list(b)) for ph,b in sorted(baseFalse-nf)],addedVsV3=[dict(photo=ph,box=list(b)) for ph,b in sorted(nf-baseFalse)])
 runtime={}
 for n,p in [('v1',V1/'dev-decisions.json'),('v3',V3/'dev-decisions-v3.json')]:
  runtime[n]=dict(verifierCompute42Sec=sum(r['verifierSec'] for r in read(p)['photos'].values()),measurement='historical saved application time, other environment; not rerun',verifierPeakPrivateMiB=None)
 cache=[read(p) for p in (V1/'dev').glob('*.json')];runtime['Step0']=dict(historicalChain42Sec=sum((r.get('chainSec') or 0) for r in cache),historicalInfer42Sec=sum((r.get('inferSec') or 0) for r in cache),historicalFeature42Sec=sum((r.get('featureSec') or 0) for r in cache),historicalMaxRssMiB=max((r.get('maxRssMiB') or 0) for r in cache),measurement='historical shared cached extraction, not a new performance run')
 runtime['v4']=dict(verifierCompute42Sec=dev['runtime']['verifierComputeSec'],loadAndApply42Sec=dev['runtime']['applyAll42Sec'],verifierPeakPrivateMiB=dev['runtime']['resource']['peakMeasuredPrivateMiB'],fitSec=cal['timing']['fitSec'],fitPeakPrivateMiB=cal['resource']['peakMeasuredPrivateMiB'],detectorInferenceCount=0)
 observations={
  1:'Focal reddish cheek target P15 is recovered by v4. Source pixels and match radius unchanged.',
  2:'Reddish chin/jaw target P21 is recovered; neighbouring accepted/duplicate points remain separately shown.',
  3:'Focal red forehead target P2 is recovered. This is point-target recall, not pixel segmentation.',
  4:'Dense inflamed lower-cheek target P26 is lost; nearby accepted points/duplicates do not count as this target under the same one-to-one matcher.',
  5:'A false point next to the mouth corner is removed; a nearby frozen TARGET remains covered. Mouth-edge appearance is an observation, not relabelled ground truth.',
  6:'A false lower-cheek point over texture/colour variation is removed.',
  7:'An additional false point over cheek texture between existing marked lesions is retained by v4.',
  8:'An additional false point on the cheek beside the nose/upper lip is retained; no focal frozen TARGET at this centre.',
  9:'An additional false forehead point lies among fine hairs/texture; the neighbouring frozen TARGET ring is separate.',
  10:'An additional false cheek point is retained alongside separately scored nearby lesions.',
  11:'An additional false forehead point over low-contrast texture/marks is retained.',
  12:'An additional false chin point over local texture/colour variation is retained. The mask/negative status is the frozen DEV protocol, not an inferred whole-face negative label.'}
 atomic('visual-review-notes.json',dict(reviewLevel='post-freeze AI engineering appearance observations; not expert, not new labels',cases=[dict(file=c['file'],sha256=c['sha256'],kind=c['kind'],photo=c['photo'],observation=observations[i+1]) for i,c in enumerate(vis['cases'])],noFrozenLabelChange=True,noParameterChanges=True))
 summary=dict(table=tab,targets=dev['targets'],falsePointChanges=diff,runtime=runtime,training=dict(reviewedNew=1868,newCategories=data['reviewedNew'],labelled=data['labelled'],positive=data['positives'],negative=data['negatives'],photos=data['photos'],coverage=data['coverage'],excluded=data['excluded']),decision=dev['selection'],fitCount=read(OUT/'fit-start.json')['fitCount'],devCount=read(OUT/'dev-start.json')['evaluationCount'],modelSHA256=sha(OUT/'verifier-v4.json'))
 atomic('report-data.json',summary)
 lines=['# Acne verifier v4 — single round completed, development selection failed','',
 'The only new model is one L2 logistic-regression verifier on the existing 1920-dimensional cached Step0 features. Detector/backbone, candidate generation, confidence, NMS, masks and pose rules were not changed. No detector inference, second fit, threshold retuning, push, merge or production activation was performed.','',
 '## Frozen DEV comparison','',
 '| Method | Found / target denominator | False | False per reviewed photo: mean / median / max | Duplicates | On uncertain | Points | Gained / lost targets vs v3 | Removed / added false points vs v3 | Verifier compute for 42 photos | Measured private peak |',
 '|---|---:|---:|---|---:|---:|---:|---|---|---|---|']
 for n,t in tab.items():
  d=dev['falseDistribution'][n];tg=dev['targets'][n];fd=diff[n]
  tm='historical shared detector chain: %.3f s'%runtime['Step0']['historicalChain42Sec'] if n=='Step0' else ('%.3f ms%s'%(runtime[n]['verifierCompute42Sec']*1000,' (historical)' if n!='v4' else ' (current)'))
  mem='not measured separately' if n!='v4' else '%.2f MiB (evaluation process)'%runtime['v4']['verifierPeakPrivateMiB']
  lines.append(f'| {n} | {t["found"]}/{t["of"]} | {t["false"]} | {d["meanReviewed"]:.3f} / {d["medianReviewed"]:.0f} / {d["maximum"]} | {t["duplicate"]} | {t["onUncertain"]} | {t["points"]} | +{len(tg["gainedVsV3"])}/-{len(tg["lostVsV3"])} | -{len(fd["removedVsV3"])}/+{len(fd["addedVsV3"])} | {tm} | {mem} |')
 lines += ['',
 'The table is the unchanged 108-target scope on 28 already exposed DEV photos; 22 have nonempty reviewed masks. Per-photo vectors and all class counts are in dev-results.json/report-data.json. The 14 cached clear-photo controls have zero Step0 candidates and provide no new verifier negative-discrimination evidence. Cached replay eyewear remains UNKNOWN. This is research development evidence, not a live camera/product or clinical acceptance.',
 '',
 'Old Step0/v1/v3 counts match the previous frozen table exactly. Historical Step0 time includes the shared chain (inference %.3f s plus preprocessing/filtering), historical feature extraction %.3f s; recorded maximum RSS %.2f MiB. Historical v1/v3 timers and current v4 timers were obtained in different environments and are not a controlled speed comparison. Separate historical verifier memory was not recorded; it is not invented here.'%(runtime['Step0']['historicalInfer42Sec'],runtime['Step0']['historicalFeature42Sec'],runtime['Step0']['historicalMaxRssMiB']),
 '',
 'V4 loaded/applied all 42 cached feature files in %.6f s; verifier arithmetic took %.6f s. The single scoring pass took %.6f s; total recorded work section %.6f s (lease setup excluded). Evaluation private peak %.2f MiB, RSS %.2f MiB. Fit took %.6f s (cache load %.6f s), fit private peak %.2f MiB, RSS %.2f MiB. Resource peaks cover the owned Python process; child/whole-system memory is not included.'%(dev['runtime']['applyAll42Sec'],dev['runtime']['verifierComputeSec'],dev['runtime']['scoreSec'],dev['runtime']['totalSec'],dev['runtime']['resource']['peakMeasuredPrivateMiB'],dev['runtime']['resource']['peakMeasuredRSSMiB'],cal['timing']['fitSec'],cal['timing']['cacheLoadSec'],cal['resource']['peakMeasuredPrivateMiB'],cal['resource']['peakMeasuredRSSMiB']),
 '',
 '## Target and false-point changes','',
 'V4 gains vs v3: '+', '.join(dev['targets']['v4']['gainedVsV3'])+'.',
 '',
 'V4 loses vs v3: '+', '.join(dev['targets']['v4']['lostVsV3'])+'.',
 '',
 'V4 removes 2 old false points and adds 25, net +23. It rejects 9 v3-retained candidate identities and adds 52, net +43 points. One-to-one matching/classes are recomputed consistently on each frozen retained list; the comparison uses classified source-coordinate identities, not just the change in total candidate count. Full coordinates and classification transitions are in dev-results.json. V4 has the same hit identities as v1 and 5 more false points on this fixed scope.',
 '',
 '## TRAIN review and unchanged protocol','',
 'All 1,868 unseen TRAIN candidates were reviewed once in 59 pages, each containing full-source context, tight crop and wider crop. No previous labels, probabilities or acceptance flags appeared on the blind pages. Categories: A=48, F=398, M=84, P=582, O=429, U=327. This is AI engineering appearance review, not dermatologist verification. Unknown skin and the 941 uncertain photos were not treated as negatives.',
 '',
 'All original V3 decisions remain recorded and source files unchanged. The 244 previous uncertain and 6 previous conflict candidates remain excluded. Reusing V3\'s same-location conflict rule excludes another 28 candidates: 12 old (11 positive, 1 negative) and 16 new (5 positive, 11 negative). These are explicit V4 conflict exclusions, not overwritten V3 labels. The final pool is 1,936 candidates (316 positive, 1,620 negative) from %d photos. Learn: 200 positive/1,348 negative in 96 groups. Calibration: 116 positive/272 negative in 37 groups.'%data['photos'],
 '',
 'All previously used V3 group roles are preserved. New roles were hashed deterministically before review. The original dHash<=10 TRAIN near-copy groups were rechecked; no role crossing was found. No TRAIN/DEV exact, source-group or dHash<=10 overlap was found. Prior-test and 15-photo supplement IDs remain excluded. Unknown persons are not claimed to be independent persons. Detailed identity/group records are in group-isolation.json and dev-inputs.json.',
 '',
 'Fit: learn-only mean/std, same 1920 features, LogisticRegression L2 C=0.1, balanced classes, lbfgs, max_iter=2000, tol=0.0001. The one fit converged in 91 iterations; only an upstream SciPy disp/iprint deprecation warning was recorded. No hyperparameter search. Scikit-learn 1.5.2, joblib 1.4.2 and threadpoolctl 3.5.0 were installed only in the isolated research runtime after explicit user permission; no image/data upload.',
 '',
 '## TRAIN calibration, separate from DEV','',
 'Threshold %.17g is the sixth-lowest of 116 calibration-positive probabilities (zero-based index 5), exactly the previous floor(0.05*n) rule. It keeps 111/116 positives (%.2f%%). Calibration AUC %.6f; negatives removed 47/272 (%.2f%%). The historical V3 calibration used a different, smaller pool: its AUC/removal numbers are not the same-denominator comparison. Learn AUC %.6f is not generalization evidence.'%(cal['calibration']['threshold'],100*cal['calibration']['keptPositives'],cal['calibration']['auc'],100*cal['calibration']['removedNegatives'],cal['learn']['auc']),
 '',
 '| Calibration negative appearance | Count | Photos | Removed | Removed fraction | AUC vs positives |',
 '|---|---:|---:|---:|---:|---:|']
 for typ,q in cal['calibration']['byType'].items():lines.append(f'| {typ} | {q["n"]} | {q["photos"]} | {q["removed"]} | {100*q["removedFrac"]:.2f}% | {q["aucVsPositives"]:.4f} |')
 lines += ['',
 'The calibration gate passes its old AUC>=0.65/removal>=15% rule. The DEV selection nevertheless fails: 70>=68 is true, but 83<=60 is false. At its frozen TRAIN-derived operating point v4 admits substantially more reviewed-skin false points. This establishes the outcome of this round; it does not isolate whether feature separability, new-label difficulty, group composition or their interaction caused it. No causal claim is made without a separate experiment, and no additional experiment was started.',
 '',
 '## Visual evidence (local only)','',
 'Each figure shows the original full-photo context, then the same source crop with V3 and V4 points. Yellow rings are frozen point-matching radii, not segmentation masks. Green=matched, red=false, blue=duplicate, orange=uncertain, white diamond=focus. The zoom is a display transform only; inference/source coordinates are unchanged. All 12 cases were visually inspected after freeze; no DEV labels, mask, threshold or model was changed.']
 for i,c in enumerate(vis['cases']):lines += ['',f'### Case {i+1:02}: {c["photo"]} {c.get("targetID","")}', '', observations[i+1], '',f'![case {i+1:02}](visual-evidence/case-{i+1:02}.jpg)']
 lines += ['',
 '## Decision and preservation','',
 'V4 is not selected. V3 (68/108, 60 false) is preserved as the development reference; the V1 research default is unchanged. Production remains accepted:false, file:null. No normal-product code, UI, build, shortcut, voice, health records, AG/Claude checkout or model was modified. No new detector/backbone training, cloud photo call, paid service, push or merge occurred. This single round is complete; no threshold adjustment, second fit/DEV round or longer training was started.',
 '',
 'Focused verification: 7 checks passed (all review IDs once, old decisions preserved, group isolation, threshold ties/95% rule, canonical matching/unknown areas, learn-only normalization and serialization parity, single-fit/evaluation provenance and exact baseline parity, visual-source hashes/transforms). No unrelated production build/test campaign was run.',
 '',
 'V4 model SHA-256: `'+sha(OUT/'verifier-v4.json')+'`.',
 '',
 'Source HEAD: `'+read(OUT/'protocol.json')['sourceHEAD']+'`; separate branch: `research/cdc-acne-verifier-v4-20261017`. `checkpoint-index.json` points to the actual full scaler/coefficient JSON, not metadata standing in for a model. `hash-index.json` covers outputs and code; `freeze.json` is the pre-DEV model/data commitment. Status is atomic. All photos and local visual evidence remain outside Git.',
 '']
 old=OUT/'report.md'
 if old.exists() and not (OUT/'report-before-dependency-approval.md').exists():atomic_text('report-before-dependency-approval.md',old.read_text('utf8'))
 atomic_text('report.md','\n'.join(lines))
 atomic('focused-verification.json',dict(command='Python311 tests/unit/test_verifier_v4_round.py',tests=7,passed=7,skipped=0,fitRepeated=False,devRepeated=False,execution='observed exit code 0; unittest OK',modelSerializationMaxProbabilityError=cal['serializationMaxProbabilityError']))
 atomic('checkpoint-index.json',dict(model=dict(path=str(OUT/'verifier-v4.json'),bytes=(OUT/'verifier-v4.json').stat().st_size,sha256=sha(OUT/'verifier-v4.json')),state='single DEV complete; development selection rejected',scope='actual full fitted scaler and classifier coefficients; detector unchanged',freezeSHA256=sha(OUT/'freeze.json'),devResultsSHA256=sha(OUT/'dev-results.json'),productionAccepted=False))
 status('completed: V4 development selection rejected; V3 preserved',1868,1868,fitCount=1,devCount=1,found=70,targets=108,falsePoints=83,developmentSelected=False,modelSHA256=sha(OUT/'verifier-v4.json'),report=str(OUT/'report.md'))
 print('REPORT_WRITTEN',OUT/'report.md')
if __name__=='__main__':main()
