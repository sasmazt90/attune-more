"""Focused invariants for the one-round research verifier; no fitting/inference."""
import sys,unittest,collections
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts/skin-research'))
from verifier_v4_round import *
import numpy as np
from verifier_v4_train import threshold95,assert_new_run
sys.path.insert(0,str(ROOT/'scripts/skin-research/external_acne'))
import relabel_compare as RC
import common_scope_compare as CS
class V4Tests(unittest.TestCase):
 def test_all_new_once_and_old_decisions_unchanged(self):
  items=read(OUT/'review-list.json')['items'];d=read(OUT/'review-decisions.json');lab=read(OUT/'data-list.json')['rows'];old=read(V3/'labels-v3.json')['rows']
  self.assertEqual(len(items),1868);self.assertEqual(len(d['decisions']),1868);self.assertEqual({x['rid'] for x in items},set(d['decisions']));self.assertEqual(len(d['pages']),59)
  for a,b in zip(old,lab):
   self.assertEqual((a['photo'],a['idx'],a['label'],a['source']),(b['photo'],b['idx'],b['priorLabel'],b['priorSource']))
   if a['source'] in ['uncertain-excluded','conflict-excluded']:self.assertIsNone(b['label'])
  for page,r in d['pages'].items():self.assertEqual(r['sheetSHA256'],sha(OUT/'blind-sheets'/f'page-{int(page):03}.jpg'))
 def test_group_roles_and_splits(self):
  rows=read(OUT/'data-list.json')['rows'];roles=read(OUT/'group-roles.json');learn={r['group'] for r in rows if r['split']=='learn'};cal={r['group'] for r in rows if r['split']=='calibration'}
  self.assertFalse(learn&cal)
  for g,s in roles['existingRoles'].items():self.assertEqual(roles['roles'][g],s)
  for r in rows:
   if r['label'] is not None:self.assertEqual(r['split'],roles['roles'][r['group']]);self.assertNotIn(r['photo'],roles['exclusionMetadataIds'])
  self.assertEqual(read(OUT/'group-isolation.json')['roleCrossings'],0)
  self.assertFalse(read(OUT/'dev-inputs.json')['trainDevNearDuplicates'])
 def test_threshold_uses_positive_order_statistic_including_ties(self):
  p=np.array([.3,.3,.9,.99]+[.001]*50);y=np.array([1]*4+[0]*50);t=threshold95(p,y);self.assertEqual(t,.3);self.assertEqual(float(np.mean(p[y==1]>=t)),1.)
  p=np.linspace(.01,.99,116);self.assertEqual(threshold95(p,np.ones(116)),p[5]);self.assertGreaterEqual(float(np.mean(p>=p[5])),.95)
 def test_canonical_matching_and_unknown_areas(self):
  self.assertEqual(len(RC.match([(0,0),(2,0)],[(1,0),(0,0)],1.1)),2)
  mask=np.zeros((100,100),bool);mask[10:40,10:40]=1;oval=np.ones_like(mask)
  lab=dict(points=[dict(id='T',cat='TARGET',x=20,y=20),dict(id='U',cat='UNCERTAIN',x=30,y=30)])
  b=lambda x,y:[x-1,y-1,x+1,y+1]
  r=CS.classify(lab,[b(20,20),b(21,20),b(30,30),b(80,80)],mask,oval,2)
  self.assertEqual(r['hitIds'],['T']);self.assertEqual(r['classes'],['matched','duplicate','onUncertain','unreviewedInOval'])
 def test_model_freeze_and_standardizer_learn_only(self):
  if not (OUT/'freeze.json').exists():self.skipTest('fit not run yet')
  freeze=read(OUT/'freeze.json')
  for n,d in freeze['files'].items():self.assertEqual(sha(OUT/n),d)
  with self.assertRaises(AssertionError):assert_new_run()
  rows=[r for r in read(OUT/'data-list.json')['rows'] if r['split']=='learn'];s=np.zeros(1920);ss=np.zeros(1920);by=collections.defaultdict(list)
  for r in rows:by[r['photo']].append(r['idx'])
  for ph,ix in by.items():
   with np.load(V1/'train'/(ph+'.npz')) as a:F=a['features'][ix].astype(float);s+=F.sum(0);ss+=(F*F).sum(0)
  m=s/len(rows);scale=np.sqrt(np.maximum(ss/len(rows)-m*m,0));scale[scale<1e-8]=1;model=read(OUT/'verifier-v4.json')
  np.testing.assert_allclose(model['standardizer']['mean'],m,atol=1e-10);np.testing.assert_allclose(model['standardizer']['scale'],scale,atol=1e-9)
  self.assertLess(read(OUT/'calibration.json')['serializationMaxProbabilityError'],1e-10)
 def test_one_fit_one_dev_and_frozen_baseline_parity(self):
  if not (OUT/'dev-results.json').exists():self.skipTest('DEV not run yet')
  self.assertEqual(read(OUT/'fit-start.json')['fitCount'],1);self.assertEqual(read(OUT/'dev-start.json')['evaluationCount'],1)
  freeze=read(OUT/'freeze.json');devstart=read(OUT/'dev-start.json');self.assertLess(freeze['timeUTC'],devstart['timeUTC']);self.assertEqual(devstart['freezeSHA256'],sha(OUT/'freeze.json'))
  r=read(OUT/'dev-results.json');old=read(TOGG/'claude-progress/acne-verifier-v3-dev-results-20261016.json')
  for n,k in [('Step0','A'),('v1','v1'),('v3','v3')]:self.assertEqual(r['table'][n],old['table'][k])
  for n,t in r['table'].items():self.assertEqual(t['of'],108);self.assertEqual(t['points'],t['found']+sum(t[c] for c in ['false','duplicate','onUncertain','onOther','nearOutOfScopeTarget','unreviewedInOval','nonSkin','unreviewedPhoto']))
  changed=r['pointChangesVsV3'];removed=sum(len(c['removedFalse']) for c in changed.values());added=sum(len(c['addedFalse']) for c in changed.values());self.assertEqual(added-removed,r['table']['v4']['false']-r['table']['v3']['false'])
  gain=r['targets']['v4']['gainedVsV3'];loss=r['targets']['v4']['lostVsV3'];self.assertEqual(len(gain)-len(loss),r['table']['v4']['found']-r['table']['v3']['found'])
  v=r['table']['v4'];self.assertEqual(r['selection']['passed'],v['found']>=68 and v['false']<=60 and (v['found']>68 or v['false']<60))
 def test_visual_sources_and_coordinates_are_traceable(self):
  if not (OUT/'visual-evidence.json').exists():self.skipTest('visual evidence not rendered')
  vis=read(OUT/'visual-evidence.json');self.assertEqual(len(vis['cases']),12)
  for case in vis['cases']:
   self.assertEqual(sha(case['file']),case['sha256']);self.assertEqual(sha(case['sourceFile']),case['sourceSHA256'])
   transform=case['cropTransform'];self.assertAlmostEqual(transform['sourceSide']*transform['displayScale'],384);self.assertEqual(transform['focus'],[case['x'],case['y']])

if __name__=='__main__':unittest.main()
