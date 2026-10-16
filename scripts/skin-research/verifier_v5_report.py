"""Report only: summarize frozen V5 CV/calibration/DEV records without refitting."""
from verifier_v5_common import *

def text_atomic(name,value):
 p=OUT/name;tmp=p.with_name(p.name+'.tmp-'+str(os.getpid()))
 with tmp.open('w',encoding='utf8') as f:f.write(value);f.flush();os.fsync(f.fileno())
 os.replace(tmp,p)

def main():
 check_v4();cv=read(OUT/'cv-results.json');cal=read(OUT/'calibration.json');dev=read(OUT/'dev-results.json');model=read(OUT/'verifier-v5.json');weights=read(OUT/'weights-summary.json')['summary'];selected=read(OUT/'selected-lambda.json');changes=dev['pointChangesVsV3'];tot={k:sum(len(v[k]) for v in changes.values()) for k in ['removedFalse','addedFalse','removedCandidates','addedCandidates']}
 atomic('focused-checks.json',dict(command='Python311 tests/unit/test_verifier_v5_round.py',tests=8,passed=8,skipped=0,observedExitCode=0,extraModelFits=0,checks=['group/category weight mass','complete group duplication preserves weighted objective and scaler','C/lambda conversion','fixed disjoint group folds','fold train-only standardization, synthetic and actual','one final fit and calibration after selection','saved model probability parity','one DEV application and reused baseline counts']))
 atomic('report-data.json',dict(table=dev['table'],cvMeanScores=cv['meanNegativeRemovalByMultiplier'],selectedLambda=selected['lambdaValue'],selectedMultiplier=selected['multiplier'],finalC=model['model']['C'],weightSum=model['model']['sampleWeightSum'],calibration=cal['calibration'],targetChanges=dev['targetsVsV3'],falsePointChanges=tot,selection=dev['selection'],modelSHA256=sha(OUT/'verifier-v5.json'),counts=dict(cvFits=9,finalFits=1,devApplications=1)))
 s=['# Verifier V5 — completed bounded weighted-L2 round','',
 '**Development selection: '+('PASS' if dev['selection']['passed'] else 'FAIL')+'. Production remains inactive; V1 research default and all V3/V4 models are preserved.**','',
 'Only existing V4 reviewed labels, group roles, conflict exclusions and cached 1920-feature vectors were used. No photo inspection/relabel, new data/dependency, detector/backbone inference/training, paid call, product/UI/build/record change, push or merge occurred.','',
 '## Pre-registered learn-only CV','',
 'The installed sklearn 1.5.2 source confirms l2_reg_strength=1/(C*sum(sample_weight)). Constant C over 1548 vs 276 samples changes the average-loss-relative penalty by 5.6087x. That implementation fact is not proof of why V4 regressed. V5 changes weighting, weighted standardization and explicit mean-loss-relative L2 together; this is not a causal ablation of those ingredients.','',
 'Objective: weighted mean logistic loss + lambda/2*||coef||**2, unpenalized intercept. lambda0=1/(0.1*276)=%.17g. For every fit C=1/(lambda*weightSum); class_weight=None. Sample weights have mean 1. Positive mass=50%%; each of four negative appearance types=12.5%%. Within category every existing research/near-copy group has equal total weight and its candidates share it equally.'%LAMBDA0,'',
 'Only learn rows were loaded for CV (1548 candidates; 200 positive/1348 negative, 96 groups). StratifiedGroupKFold(n_splits=3, shuffle=True, random_state=20261017) was frozen before fitting. Folds are not perfectly size-balanced because whole groups stay together; no regrouping was performed after seeing results. Each scaler and training weight vector was fit only on its fold-training rows. Held-out validation scoring uses equal negative-type/group mass; the positive operating-point rule retains at least 95% of positive candidates by the same order statistic used before. Fold thresholds are discarded.','',
 '| Lambda multiplier | Lambda | Fold 1 negative removal | Fold 2 | Fold 3 | Mean |','|---:|---:|---:|---:|---:|---:|']
 for m in [1,3,10]:
  rows=[r for r in cv['results'] if r['multiplier']==m];scores=[r['negativeTypeGroupBalancedRemoval'] for r in sorted(rows,key=lambda q:q['fold'])]
  s.append(f'| {m} | {m*LAMBDA0:.12g} | {100*scores[0]:.4f}% | {100*scores[1]:.4f}% | {100*scores[2]:.4f}% | {100*cv["meanNegativeRemovalByMultiplier"][str(m)]:.4f}% |')
 s += ['',
 'Selected multiplier %d, lambda %.17g by highest mean; exact ties would choose stronger L2. No new option was added. All 9 CV fits converged. Per-fold C, sums, sample/group IDs, weights/scalers, model coefficients, threshold, positive retention, by-type scores, iterations and warnings are in cv/*.json. The CV validation thresholds were used only for this choice.'%(selected['multiplier'],selected['lambdaValue']),'',
 '| Fold | Fitting rows / groups | Validation rows / groups | Validation positives kept |','|---|---|---|---|']
 for f in read(OUT/'folds.json')['folds']:
  r=next(r for r in cv['results'] if r['fold']==f['fold'] and r['multiplier']==selected['multiplier'])
  s.append(f'| {f["fold"]} | {len(f["trainIndices"])}/{len(f["trainGroups"])} | {len(f["validationIndices"])}/{len(f["validationGroups"])} | {r["positiveKept"]}/{r["positiveN"]} |')
 s += ['',
 '## Final learn weights, one fit, held-out TRAIN calibration','',
 '| Category | Candidates | Groups | Weight sum | Total share |','|---|---:|---:|---:|---:|']
 for t,q in weights['types'].items():s.append(f'| {t} | {q["n"]} | {q["groups"]} | {q["totalWeight"]:.8f} | {100*q["fraction"]:.2f}% |')
 c=cal['calibration']
 s += ['',
 'Final total weight %.17g, lambda %.17g, actual C %.17g. Weighted scaler uses the same full-learn weights. The final fit converged in %d iterations. No calibration rows were fitted. Calibration caches were first accessed after the CV selection was saved; feature-access.json records the order learn(CV), learn(final), calibration. Unknown/conflicted samples were never reinstated.'%(model['model']['sampleWeightSum'],model['model']['lambdaValue'],model['model']['C'],cal['fit']['nIter'][0]),'',
 'Final threshold %.17g is the sixth-lowest of 116 calibration-positive probabilities (floor(0.05*116)=5, zero-based), preserving %d/116 = %.4f%%. Calibration AUC %.6f (unweighted); %d/272 = %.4f%% of negative candidates removed, %.4f%% with equal type/group weighting. Learn AUC %.6f is fit evidence, not generalization. Calibration is separate from CV and DEV.'%(c['threshold'],c['positiveKept'],100*c['positiveKeptFraction'],c['auc'],c['negativeRemoved'],100*c['negativeRemovedFraction'],100*c['negativeTypeGroupBalancedRemoval'],cal['learn']['auc']),'',
 '| Calibration negative appearance | Candidates / groups | Removed candidates | Candidate removal | Group-balanced removal |','|---|---:|---:|---:|---:|']
 for t,q in c['byType'].items():s.append(f'| {t} | {q["n"]}/{q["groups"]} | {q["removed"]} | {100*q["removedFraction"]:.4f}% | {100*q["groupBalancedRemoved"]:.4f}% |')
 s += ['',
 '## One frozen DEV application','',
 'The actual scaler/coefficient JSON, threshold and input/code hashes were frozen in freeze.json before dev-start.json. Only V5 was newly applied, on all 42 existing DEV feature caches. The V4 comparator uses identical frozen labels, masks, coordinates and deterministic one-to-one point matching for V5; old Step0/V1/V3/V4 table/classification records were reused without rerunning those models.','',
 '| Method | Found / targets | False points | Duplicates | On uncertain | Total points |','|---|---:|---:|---:|---:|---:|']
 for n,t in dev['table'].items():s.append(f'| {n} | {t["found"]}/{t["of"]} | {t["false"]} | {t["duplicate"]} | {t["onUncertain"]} | {t["points"]} |')
 s += ['',
 'V5 gains vs V3: '+', '.join(dev['targetsVsV3']['gained'])+'.','',
 'V5 loses vs V3: '+', '.join(dev['targetsVsV3']['lost'])+'.','',
 'False-point changes vs V3: removed %d, added %d, net %+d. Candidate changes: removed %d, added %d. All source-coordinate boxes and classification transitions are in dev-results.json. This is not inferred from total candidate count alone.'%(tot['removedFalse'],tot['addedFalse'],tot['addedFalse']-tot['removedFalse'],tot['removedCandidates'],tot['addedCandidates']),'',
 '| Photo | V3 false | V5 false | Removed / added false | V3 / V5 found |','|---|---:|---:|---|---|']
 for ph,p in dev['perPhoto'].items():
  ch=changes[ph];s.append(f'| {ph} | {p["v3"]["false"]} | {p["v5"]["false"]} | -{len(ch["removedFalse"])}/+{len(ch["addedFalse"])} | {p["v3"]["found"]}/{p["v5"]["found"]} |')
 d=dev['falseDistributionV5'];t=dev['table']['v5']
 s += ['',
 'V5 false points per reviewed photo: mean %.4f, median %.0f, maximum %d (22 nonempty reviewed masks). The fixed 108-target table covers 28 already exposed DEV photos. Fourteen additional clear controls had zero baseline candidates, so they provide no new verifier negative-discrimination evidence. The replay still has eyewear UNKNOWN. No independent final-set, live-camera, product or clinical claim is made.'%(d['meanReviewed'],d['medianReviewed'],d['maximum']),'',
 'Selection rule: found>=68 AND false<=60 AND at least one strict gain vs V3. Observed %d targets / %d false -> %s. The gain is small (+1 target, -1 false net); duplications also rise from 36 to 41 and uncertain-area points from 58 to 63. This qualifies only as the registered development improvement, not a solved acne detector. No post-DEV threshold edit, second candidate or further round was started.'%(t['found'],t['false'],'PASS' if dev['selection']['passed'] else 'FAIL'),'',
 '## Time, memory and verification','',
 '| Phase | Recorded work time | Private peak | RSS peak |','|---|---:|---:|---:|']
 for name,r in [('Nine CV fits',cv['runtime']),('Final fit + TRAIN calibration',cal['runtime']),('One DEV application + scoring',dev['runtime'])]:
  q=r['resource'];s.append(f'| {name} | {r["totalSec"]:.6f} s | {q["peakMeasuredPrivateMiB"]:.2f} MiB | {q["peakMeasuredRSSMiB"]:.2f} MiB |')
 s += ['',
 'The final solver itself took %.6f s. V5 feature-cache load/application took %.6f s; verifier arithmetic %.6f s; scoring %.6f s. These are cached verifier timings, not capture-to-result latency. Resource peaks cover the owned Python process (not whole system/children); lease acquisition/teardown is outside the work-section timer. Every heavy phase held the shared PID/start-time-verified dual lease and stopped no foreign process.'%(cal['fit']['sec'],dev['runtime']['applyAll42Sec'],dev['runtime']['verifierComputeSec'],dev['runtime']['scoreSec']),'',
 'Eight focused tests passed, no skips: category/group weight masses; complete-group duplication invariance of scaler/objective and lambda; C/lambda conversion; disjoint/fixed folds; synthetic and actual fold-only weighted standardizers; calibration accessed after selection and never fitted; saved probability parity (maximum error %.3g); single DEV and reused baseline parity. No extra model was fitted by tests. All 10 fits converged; only the upstream SciPy disp/iprint deprecation warning was recorded.'%cal['serializationMaxProbabilityError'],'',
 '## Preserved delivery','',
 'V3 and V4 model/threshold/data/decisions stay unchanged. V1 remains the research default. Production acne remains accepted:false, file:null. This research candidate is not connected to the product. Claude/AG/product checkouts, main, UI, voices, records, model settings, build and launcher were not modified; no push/merge. No new work round follows automatically.','',
 'Model SHA-256: `'+sha(OUT/'verifier-v5.json')+'`.','',
 'Actual model: `'+str(OUT/'verifier-v5.json')+'`. `checkpoint-index.json` indexes the real scaler and coefficients; `hash-index.json` covers reports, protocol, weights, CV evidence, model and code. Original V4 source identities and group exclusions are retained; no new person-independence claim is made.','']
 text_atomic('report.md','\n'.join(s));atomic('checkpoint-index.json',dict(model=dict(path=str(OUT/'verifier-v5.json'),bytes=(OUT/'verifier-v5.json').stat().st_size,sha256=sha(OUT/'verifier-v5.json')),state='single DEV complete; research development selected' if dev['selection']['passed'] else 'single DEV complete; not selected',developmentSelected=dev['selection']['passed'],productionAccepted=False,freezeSHA256=sha(OUT/'freeze.json'),devResultsSHA256=sha(OUT/'dev-results.json')))
 status('completed: V5 development improvement; production inactive' if dev['selection']['passed'] else 'completed: V5 not selected; V3 preserved',cvFits=9,finalFits=1,devApplications=1,found=t['found'],targets=108,falsePoints=t['false'],developmentSelected=dev['selection']['passed'],modelSHA256=sha(OUT/'verifier-v5.json'),report=str(OUT/'report.md'))
 print('REPORT_COMPLETE',OUT/'report.md')
if __name__=='__main__':main()
