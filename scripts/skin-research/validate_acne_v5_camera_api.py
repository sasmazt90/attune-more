"""One existing photo payload for normal API contract, not new model evaluation."""
import sys,os,json,time,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT.parent/'cdc-progress/acne-v5-consistency-fix-20261017'
sys.path[:0]=[str(ROOT/'services/core-api'),str(ROOT/'scripts/skin-research')]
os.environ.update(ATTUNE_EXPERIMENTAL_ACNE_V5='1',ATTUNE_LOAD_LOCAL_ENV='0')
from heavy_job_lease import HeavyJobLease
from acne_v5_product import METHOD
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--payload',type=Path,required=True,help='Existing browser payload JSON; no photo collection or model evaluation.')
args=parser.parse_args()
with HeavyJobLease('CDC-acne-v5-normal-camera-API-contract',peak_mib=1800,minimum_available_mib=1600,memory_metric='private') as lease:
 from fastapi.testclient import TestClient
 import main
 p=json.loads(args.payload.read_text('utf8'))['payload'];p.pop('includeRuntimeTrace',None);p['hostedProcessingConsent']=False
 with TestClient(main.app) as client:
  t=time.perf_counter();response=client.post('/api/local-health/skin',json=p);elapsed=time.perf_counter()-t;assert response.status_code==200,(response.status_code,response.text[:500]);d=response.json()
  assert d['acneRuntime']['status']=='measured',d['acneRuntime'];assert d['acneRuntime']['nonAcnePreservation']['equal'];assert len(d['general']['measurements'])==9
  assert all(r['methodVersion']==METHOD for rows in d['measurements'].values() for r in rows if r['id']=='acne');assert not any(k.endswith(':acne') for k in d['maps'])
  for region,rows in d['measurements'].items():
   for row in rows:
    if row['id']=='acne':assert row['components']['candidateCount']==len(d['acneCandidates'][region])
  (OUT/'normal-api-photo-contract.json').write_text(json.dumps(dict(status=response.status_code,seconds=elapsed,evidenceKind='recorded-photo payload; not physical camera acceptance',response=d,resource=lease.receipt()),ensure_ascii=False),encoding='utf8');print(json.dumps(dict(seconds=elapsed,acne=d['acneRuntime'],units={r['region']:r['unit'] for rows in d['measurements'].values() for r in rows if r['id']=='acne'},overviewAcne=next(r for r in d['general']['measurements'] if r['id']=='acne')['unit']),indent=2))
