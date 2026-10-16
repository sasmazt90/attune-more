"""V5 invariants without extra model fits, detector calls or photo review."""
import unittest,sys,collections
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts/skin-research'))
from verifier_v5_common import *
class V5Tests(unittest.TestCase):
 def test_real_category_group_weights(self):
  rows=[r for r in read(V4/'data-list.json')['rows'] if r['split']=='learn'];w=balanced_weights(rows);s=weight_summary(rows,w);self.assertAlmostEqual(w.mean(),1)
  for t,share in SHARES.items():
   self.assertAlmostEqual(s['types'][t]['fraction'],share)
   totals=list(s['types'][t]['perGroup'].values());np.testing.assert_allclose(totals,np.repeat(totals[0],len(totals)),rtol=1e-12)
  self.assertAlmostEqual(sum(w[np.array([r['label']==1 for r in rows])])/sum(w),.5)
 def test_duplicate_group_invariant_objective_and_normalization(self):
  rows=[dict(type=t,group=g,label=int(t=='pos')) for g in ['g1','g2'] for t in TYPES];rng=np.random.default_rng(SEED);X=rng.normal(size=(len(rows),7));y=np.array([r['label'] for r in rows]);w=balanced_weights(rows);mean,scale=standardize_fit(X,w)
  # Duplicate the complete g1 contribution; do not pretend arbitrary within-group relabels are invariant.
  extra=[i for i,r in enumerate(rows) if r['group']=='g1']*4;ix=list(range(len(rows)))+extra;rr=[rows[i] for i in ix];XX=X[ix];yy=y[ix];ww=balanced_weights(rr);mm,ss=standardize_fit(XX,ww)
  np.testing.assert_allclose(mm,mean,atol=1e-12);np.testing.assert_allclose(ss,scale,atol=1e-12);coef=rng.normal(size=7)
  self.assertAlmostEqual(objective((X-mean)/scale,y,w,coef,.2,LAMBDA0),objective((XX-mm)/ss,yy,ww,coef,.2,LAMBDA0),places=12)
  self.assertAlmostEqual(1/(c_from_lambda(LAMBDA0,w)*sum(w)),1/(c_from_lambda(LAMBDA0,ww)*sum(ww)))
 def test_c_lambda_and_threshold(self):
  for m in [1,3,10]:
   for n in [276,808,1548]:self.assertAlmostEqual(1/(c_from_lambda(LAMBDA0*m,np.ones(n))*n),LAMBDA0*m)
  p=np.linspace(.001,.999,116);t=threshold95(p,np.ones(116));self.assertEqual(t,p[5]);self.assertGreaterEqual(np.mean(p>=t),.95)
 def test_fold_roles_are_disjoint_and_complete(self):
  f=read(OUT/'folds.json');rows=f['learnIDs'];seen=[];original=[r for r in read(V4/'data-list.json')['rows'] if r['split']=='learn'];self.assertEqual(len(rows),1548)
  for fold in f['folds']:
   tr=fold['trainIndices'];va=fold['validationIndices'];self.assertFalse(set(tr)&set(va));self.assertEqual(set(tr)|set(va),set(range(len(rows))));self.assertFalse(set(fold['trainGroups'])&set(fold['validationGroups']));seen+=va
   for ix in tr+va:self.assertEqual(rows[ix]['group'],original[ix]['group'])
  self.assertEqual(sorted(seen),list(range(len(rows))))
 def test_standardizer_uses_only_passed_training_data(self):
  X=np.arange(120,dtype=float).reshape(20,6);w=np.arange(1,21,dtype=float);tr=np.arange(12);before=standardize_fit(X[tr],w[tr]);X[12:]=1e12;after=standardize_fit(X[tr],w[tr]);np.testing.assert_equal(before,after);np.testing.assert_allclose(before[0],np.average(X[tr],axis=0,weights=w[tr]))
 def test_completed_fit_records_and_serialization(self):
  if not (OUT/'freeze.json').exists():self.skipTest('final fit not run yet')
  check_v4();c=read(OUT/'cv-results.json');self.assertEqual(c['CVFits'],9);self.assertEqual(len(c['results']),9);scores={int(k):v for k,v in c['meanNegativeRemovalByMultiplier'].items()};self.assertEqual(c['selectedMultiplier'],max(scores,key=lambda m:(scores[m],m)))
  self.assertEqual(read(OUT/'final-fit-start.json')['finalFitCount'],1);cal=read(OUT/'calibration.json');self.assertTrue(cal['noCalibrationFit']);self.assertLess(cal['serializationMaxProbabilityError'],1e-10)
  model=read(OUT/'verifier-v5.json');self.assertIsNone(model['model']['classWeight']);self.assertAlmostEqual(1/(model['model']['C']*model['model']['sampleWeightSum']),model['model']['lambdaValue'])
  self.assertGreaterEqual(cal['calibration']['positiveKeptFraction'],.95)
  for n,d in read(OUT/'freeze.json')['files'].items():self.assertEqual(sha(OUT/n),d)
  phases=read(OUT/'feature-access.json')['phases'];self.assertEqual([p['role'] for p in phases],['learn','learn','calibration']);self.assertLess(read(OUT/'selected-lambda.json')['timeUTC'],phases[-1]['timeUTC'])
 def test_actual_fold_standardizers(self):
  if not (OUT/'cv-results.json').exists():self.skipTest('CV not run yet')
  rows=[r for r in read(V4/'data-list.json')['rows'] if r['split']=='learn'];X=np.empty((len(rows),1920));by=collections.defaultdict(list)
  for i,r in enumerate(rows):by[r['photo']].append((i,r['idx']))
  for ph,entries in by.items():
   with np.load(CACHE/'train'/(ph+'.npz')) as a:
    for i,ix in entries:X[i]=a['features'][ix]
  for f in read(OUT/'folds.json')['folds']:
   tr=f['trainIndices'];train=[rows[i] for i in tr];w=balanced_weights(train);mean,scale=standardize_fit(X[tr],w);saved=read(OUT/f'cv/fold-{f["fold"]}-standardizer.json');np.testing.assert_allclose(mean,saved['mean'],atol=1e-12);np.testing.assert_allclose(scale,saved['scale'],atol=1e-12)
  final=read(OUT/'verifier-v5.json') if (OUT/'verifier-v5.json').exists() else None
  if final:
   mean,scale=standardize_fit(X,balanced_weights(rows));np.testing.assert_allclose(mean,final['standardizer']['mean'],atol=1e-12);np.testing.assert_allclose(scale,final['standardizer']['scale'],atol=1e-12)
 def test_single_dev_and_reused_baselines(self):
  if not (OUT/'dev-results.json').exists():self.skipTest('DEV not run yet')
  d=read(OUT/'dev-results.json');old=read(V4/'dev-results.json');self.assertEqual(read(OUT/'dev-start.json')['count'],1);self.assertLess(read(OUT/'freeze.json')['timeUTC'],read(OUT/'dev-start.json')['timeUTC'])
  for n,t in old['table'].items():self.assertEqual(d['table'][n],t)
  t=d['table']['v5'];self.assertEqual(t['of'],108);changes=d['pointChangesVsV3'];self.assertEqual(sum(len(v['addedFalse'])-len(v['removedFalse']) for v in changes.values()),t['false']-d['table']['v3']['false']);self.assertEqual(len(d['targetsVsV3']['gained'])-len(d['targetsVsV3']['lost']),t['found']-68)
  self.assertEqual(d['selection']['passed'],t['found']>=68 and t['false']<=60 and (t['found']>68 or t['false']<60))
if __name__=='__main__':unittest.main()
