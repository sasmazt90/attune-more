"""Prepare sealed, genuinely unused source-photo groups without opening pixels.

This is a separate metadata preparation task, not model validation. All prior
review/training scopes and uncertain cross-group relations are excluded. Source
face collages are excluded pending component identities. Clinical person
independence and complete pixel-label coverage are never inferred.
"""
import collections,json
from pathlib import Path
from expanded_sources import OUT,PREVIOUS,write,sha,targets


def main():
 existing=OUT/'unused-final-preparation/manifest.json'
 if existing.exists():
  sealed=json.loads(existing.read_text('utf8'))
  assert sealed['parentManifestSHA256']==sha(PREVIOUS/'manifest.json') and sealed['acceptanceProtocolSHA256']==sha(Path(__file__).parent/'label-function-acceptance-v2.json'),'SEALED_FINAL_SOURCE_OR_PROTOCOL_DRIFT'
  print('Existing sealed unused preparation preserved; run verify_unused_final_seal.py against new exposure ledgers',flush=True);return
 manifest=PREVIOUS/'manifest.json';m=json.loads(manifest.read_text('utf8'));rows=m['rows'];exposed=set();decoded=set();usedgroups=set();receipts={}
 ledgers=['candidates.json','supplement/candidates.json','detector-data.json','mask-data.json','continuation-mask-data.json','continuation-valid-skin-data.json','sag-controls/candidates.json','sag-controls/additional-candidates.json','local-control-review/dry-negative-index.json']
 for name in ledgers:
  p=OUT/name
  if not p.exists():continue
  v=json.loads(p.read_text('utf8'));rs=v if isinstance(v,list) else v.get('rows',[]);receipts[name]=sha(p)
  for r in rs:
   exposed.add(r['sha256']);usedgroups.add(r['group'])
   if r.get('decodedSHA256'):decoded.add(r['decodedSHA256'])
 # Any relation uncertainty involving a development group is quarantined, not
 # resolved by treating a perceptual hash as subject identity.
 uncertain=set()
 for a,b,*_ in m['perceptualQuarantinePairs']:
  if rows[a]['group']!=rows[b]['group']:uncertain.update([rows[a]['group'],rows[b]['group']])
 chosen=[];seen=set();reasons=collections.Counter()
 for r in rows:
  if r['split']!='test':continue
  reason=None
  if r.get('reviewExposed') or r.get('groupExposed') or r['sha256'] in exposed or r.get('decodedSHA256') in decoded:reason='PREVIOUS_EXPOSURE'
  elif r['group'] in usedgroups:reason='USED_SOURCE_GROUP'
  elif r['group'] in uncertain:reason='UNRESOLVED_NEAR_PHOTO_GROUP_RELATION'
  elif r['source']=='face':reason='COLLAGE_COMPONENT_RELATIONS_PENDING'
  elif r.get('excluded'):reason=r['excluded']
  elif not targets(r):reason='NO_MATCHED_TARGET_LABEL'
  if reason:reasons[reason]+=1;continue
  if r['group'] in seen:reasons['SAME_PHOTO_FAMILY_ALTERNATE_EXPORT']+=1;continue
  seen.add(r['group']);chosen.append({**r,'applicableTargets':targets(r),'blindTargetROIReviewPending':True,'completeNegativeTruth':False,'gradeTruthAvailable':False})
 assert not seen&usedgroups and not {r['sha256'] for r in chosen}&exposed
 protocol=Path(__file__).parent/'label-function-acceptance-v2.json'
 result=dict(version='unused-source-group-preparation-20261011-v2',preparationTaskSeparate=True,parentManifestSHA256=sha(manifest),acceptanceProtocolSHA256=sha(protocol),priorExposureReceipts=receipts,rows=chosen,counts=dict(photos=len(chosen),sourceGroups=len(seen),sources=dict(collections.Counter(r['source'] for r in chosen)),targets=dict(collections.Counter(t for r in chosen for t in r['applicableTargets']))),quarantineReasons=dict(reasons),testPixelsOpened=False,modelPredictionsUsed=False,personIndependent=False,readyForBlindLabelROIReview=True,readyForIndependentPerformanceClaim=False,missing=['blind per-target annotation/negative ROI completeness review','image-specific rights review','class/grade targets cannot be invented','natural-camera-domain review'],oldOpenedTestsIncluded=False)
 write('unused-final-preparation/manifest.json',result);write('unused-final-preparation/receipt.json',{k:v for k,v in result.items() if k!='rows'});print(json.dumps(result['counts']),flush=True)


if __name__=='__main__':main()
