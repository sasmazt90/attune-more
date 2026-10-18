"""Verify the sealed final source pool against every current exposure ledger.

No final photographs or model predictions are opened. Photo-family independence
is not a claim of person independence. This does not invent absent labels.
"""
import json
from expanded_sources import OUT,write,sha


def main():
 path=OUT/'unused-final-preparation/manifest.json';sealed=json.loads(path.read_text('utf8'));used_sha=set();used_decoded=set();used_groups=set();receipts={}
 for name in ['candidates.json','supplement/candidates.json','detector-data.json','mask-data.json','continuation-mask-data.json','continuation-valid-skin-data.json','negative-expanded-mask-data.json','negative-expanded-detector-data.json','negative-expansion/candidates.json','sag-controls/candidates.json','sag-controls/additional-candidates.json','local-control-review/dry-negative-index.json']:
  source=OUT/name
  if not source.exists():continue
  data=json.loads(source.read_text('utf8'));rows=data if isinstance(data,list) else data.get('rows',[]);receipts[name]=sha(source)
  for row in rows:
   used_sha.add(row['sha256']);used_groups.add(row['group'])
   if row.get('decodedSHA256'):used_decoded.add(row['decodedSHA256'])
 collisions=[r['sha256'] for r in sealed['rows'] if r['sha256'] in used_sha or r.get('decodedSHA256') in used_decoded or r['group'] in used_groups]
 labels=json.loads((OUT/'unused-final-preparation/typed-label-index.json').read_text('utf8'))
 assert not collisions,'FINAL_PREPARATION_EXPOSURE_COLLISION'
 assert labels['manifestSHA256']==sha(path) and labels['preparationComplete'] and not labels['sourcePhotosDecoded'] and not labels['modelPredictionsOpened']
 write('unused-final-preparation/exposure-verification-v3.json',dict(version='sealed-preparation-current-exposure-v3',manifestSHA256=sha(path),typedLabelIndexSHA256=sha(OUT/'unused-final-preparation/typed-label-index.json'),developmentLedgerHashes=receipts,photos=len(sealed['rows']),groups=len({r['group'] for r in sealed['rows']}),exposureCollisions=collisions,metadataAndTypedPreparationComplete=True,blindTargetROIRightsReviewPending=True,independentPerformancePassed=None,personIndependenceVerified=False,finalPhotosOpened=False,finalPredictionsOpened=False))
 print('631 sealed source groups remain unused; typed preparation complete, blind review/performance pending',flush=True)
if __name__=='__main__':main()
