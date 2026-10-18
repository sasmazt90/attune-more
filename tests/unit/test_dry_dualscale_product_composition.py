"""Pure composition on retained real response structures, model calls stubbed.
This is NOT the blocked full factory/API acceptance and sends no request.
"""
import copy,json,sys,os
from pathlib import Path
from types import SimpleNamespace
import pytest
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT.parent/'cdc-progress/skin-dryness-dualscale-20261018'
sys.path.insert(0,str(ROOT/'services/core-api'))

def test_dry_only_composition_and_explicit_scale_metadata(monkeypatch):
 path=OUT/'757f74cd-staging-result.json'
 if not path.exists():pytest.skip('Task-local retained real response is outside Git')
 import product_dryness as P,dry_dualscale_runtime_staging as S
 from skin_measurement_contract import attach_result_receipts
 snapshot=json.loads((OUT/'factory-response.json').read_text('utf8')) if (OUT/'factory-response.json').exists() else json.loads(path.read_text('utf8'))
 row=json.loads((OUT/'runtime-third-resumed-checks.json').read_text('utf8'))['rows'][0]
 original=copy.deepcopy(snapshot)
 native=dict(photoId=snapshot['photoId'],sourceWidth=snapshot['sourceWidth'],sourceHeight=snapshot['sourceHeight'],measurements={k:copy.deepcopy(next(x for x in v if x['id']=='dry')) for k,v in snapshot['measurements'].items()},general=copy.deepcopy(next(x for x in snapshot['general']['measurements'] if x['id']=='dry')),maps={k:copy.deepcopy(v) for k,v in snapshot['maps'].items() if k.endswith(':dry')},nativeMetadata=copy.deepcopy(snapshot['drynessRuntime']))
 staged=dict(candidate=native,halfContract=row['halfContract'],profile=row['profile'],support=SimpleNamespace(metadata=dict(nativeLostSourcePixels=0)))
 monkeypatch.setattr(P,'runtime',lambda check:({},object()))
 monkeypatch.setattr(S,'analyze_staging',lambda *args:copy.deepcopy(staged))
 frozen=copy.deepcopy(original)
 for promoted in (False,True):
  result=S.analyze_product_candidate({},lambda v:copy.deepcopy(original),lambda:None,promoted=promoted)
  assert result['drynessRuntime']['nonDryPreservation']['equal']
  assert result['drynessRuntime']['analysisResize'] is True and result['drynessRuntime']['sourcePhotoOrDisplayResized'] is False
  assert [x['factor'] for x in result['drynessRuntime']['analysisScales']]==[1.,.5]
  for rows in result['measurements'].values():
   r=next(x for x in rows if x['id']=='dry')
   assert 'nativeAnalysisResize' not in r['components'] and r['components']['halfBranchAnalysisResize'] is True
   assert r['methodVersion']==('appearance-native-dry-3' if promoted else S.METHOD)
  assert attach_result_receipts(copy.deepcopy(result))==result
  if promoted and os.getenv('ATTUNE_DRY_CONTRACT_RECEIPT'):
   from local_skin_type import finalize_product_type
   result=finalize_product_type(result);assert finalize_product_type(copy.deepcopy(result))==result
   target=Path(os.environ['ATTUNE_DRY_CONTRACT_RECEIPT']).resolve();assert target==OUT/'promoted-contract-replay.json'
   target.write_text(json.dumps(dict(evidenceKind='Pure production metadata/serialization replay of retained actual factory response; model calls stubbed; NOT a second API response',modelInferenceCalls=0,result=result),ensure_ascii=False),'utf8')
 assert original==frozen
