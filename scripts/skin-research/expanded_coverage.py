"""Criterion ledger over every selected source image, including unreviewed ones.

Counts separate a source photo from a reviewed positive/negative tile. Geometry
alone does not confirm a target; absent annotations never establish negatives.
Frozen training ledgers are read without rewriting their identity.
"""
import collections,json
from expanded_sources import OUT,PREVIOUS,TARGETS,LABELS,annotations,key,sha,write

SOURCES={
 'type':{'old-skin'},'acne':{'smart','clean3','v11','care','merve','old-eye'},
 'oil':{'v11','clean3','csv','old-skin'},'dry':{'merve','clean3','csv','old-skin'},
 'redness':{'v11','care','clean3','old-skin'},'tone':{'v11','care','skin5','arnold','old-skin'},
 'lines':{'face','wrinkles','skin5'},'dark':{'dc','skin5','wrinkles','arnold'},
 'bags':{'dc','v11','old-eye','arnold','csv'},
 'sag':{'old-skin','v11','care','face','dc','wrinkles','skin5','arnold','clean3'},
}


def append_active(coverage):
 """Keep the historical preparation table and append immutable current phases."""
 for name in ['continuation-valid-skin-data','negative-expanded-mask-data']:
  path=OUT/(name+'.json')
  if not path.exists():continue
  data=json.loads(path.read_text('utf8'));training=name=='continuation-valid-skin-data' or (OUT/'negative-mask-continuation/CURRENT').exists()
  for target,v in coverage['criteria'].items():
   rs=[r for r in data['rows'] if r['target']==target];splits={}
   for split in ['train','validation','test']:
    rows=[r for r in rs if r['split']==split];pos={r['sha256'] for r in rows if r['positivePixels']}
    splits[split]=dict(photos=len({r['sha256'] for r in rows}),groups=len({r['group'] for r in rows}),positivePhotos=len(pos),independentNegativePhotos=len({r['sha256'] for r in rows if r['knownNegativePixels'] and r['sha256'] not in pos}),positiveROIs=sum(r['positivePixels']>0 for r in rows),onlyNegativeROIs=sum(r['positivePixels']==0 and r['knownNegativePixels']>0 for r in rows),partialROIs=sum(not r['completeROI'] for r in rows))
   v.setdefault('separatePreparedPhases',{})[name]=dict(ledgerSHA256=sha(path),splits=splits,trainingStarted=training,actualConsumedCountsMustBeReadSeparately=True)
 consumed=OUT/'actual-consumed-training-coverage.json'
 if consumed.exists():
  for target,counts in json.loads(consumed.read_text('utf8'))['mask'].items():coverage['criteria'][target]['provenConsumedTrainingLowerBound']=counts
 detector=OUT/'negative-expanded-detector-data.json'
 if detector.exists():coverage['criteria']['acne']['negativeExpandedDetectorPhase']=dict(ledgerSHA256=sha(detector),counts=json.loads(detector.read_text('utf8'))['counts'],trainingStarted=(OUT/'negative-yolox/CURRENT').exists())
 coverage['earlyPreparedMaskTableIsHistorical']=True;coverage['activePhasePreparationIsNotActualConsumption']=True
 return coverage

def main():
 manifest=PREVIOUS/'manifest.json';rows=json.loads(manifest.read_text('utf8'))['rows']
 decisions=json.loads((OUT/'decisions.json').read_text('utf8'))['rows']
 supplement=OUT/'supplement/decisions.json'
 if supplement.exists():decisions+=json.loads(supplement.read_text('utf8'))['rows']
 by={r['reviewKey']:r for r in decisions}
 type_path=PREVIOUS.parent/'skin-followup-20261011/development-manifest-v2.json'
 type_rows=json.loads(type_path.read_text('utf8'))['rows'] if type_path.exists() else []
 type_ready={r['sha256']:r for r in type_rows if r.get('typeEligible')}
 quality_path=type_path.parent/'quality/decisions.json'
 type_excluded={r['sha256']:r['reasons'] for r in json.loads(quality_path.read_text('utf8'))['excluded']} if quality_path.exists() else {}
 training={}
 for kind in ('mask','detector'):
  p=OUT/f'{kind}-data.json'
  if p.exists():training[kind]=json.loads(p.read_text('utf8'))
 criteria={};statuses=[]
 for t in TARGETS:
  associated=[r for r in rows if r['source'] in SOURCES[t]]
  counts=collections.Counter();reasons=collections.Counter();source=collections.defaultdict(lambda:collections.Counter());splits=collections.defaultdict(lambda:collections.Counter())
  ready_groups=set();pending_groups=set();positive=set();negative=set();partial=set();geometric=set()
  for r in associated:
   aa=annotations(r);target_anns=[a for a in aa if LABELS.get(r['source'],{}).get(a['label'])==t]
   n=len(target_anns);valid=sum(bool(a['validBox'] or a['validMask']) for a in target_anns)
   counts['totalSourceImages']+=1;counts['targetAnnotations']+=n;counts['geometricallyValidAnnotations']+=valid
   source[r['source']]['images']+=1;source[r['source']]['targetAnnotations']+=n
   if valid:geometric.add(r['group'])
   d=by.get(key(r));status='pending';reason='SOURCE_TARGET_VISUAL_REVIEW_PENDING'
   if t=='type' and r['sha256'] in type_excluded:status='excluded';reason='TYPE_PHOTO_QUALITY:'+','.join(type_excluded[r['sha256']])
   elif t=='type' and r['sha256'] in type_ready:
    status='ready';reason='PREVIOUS_HASH_BOUND_ENGINEERING_PHOTO_QUALITY_REVIEW_SOURCE_CLASS_UNVERIFIED'
    ready_groups.add(r['group']);positive.add(r['sha256'])
   elif r.get('excluded'):status='excluded';reason=r['excluded']
   elif d and not d['rightsEligible']:status='excluded';reason=d['excludedReason'] or 'REVIEWED_PROVENANCE_UNRESOLVED'
   elif d and d.get('excludedReason'):
    # An unresolved collage needs preparation, not an invented rights failure.
    reason=d['excludedReason']
    if reason=='NON_FACIAL_DOMAIN' and t in ('type','sag'):status='excluded'
   elif d and t in d['acceptedTargets']:
    status='ready';reason='REVIEWED_TARGET_SUPPORT'
    positive.add(r['sha256']);ready_groups.add(r['group'])
    partial.add(r['sha256'])
    if t in d.get('completeMaskTargets',[]):partial.discard(r['sha256'])
    if not valid:reason='REVIEWED_PHOTO_PRESENCE_ONLY_NO_PIXEL_TRUTH'
   elif d:reason=d.get('targetReasons',{}).get(t,'TARGET_NOT_REVIEWED_IN_THIS_PHOTO')
   counts[status+'Images']+=1;splits[r['split']][status+'Images']+=1
   if status!='ready':reasons[reason]+=1
   if status=='pending':pending_groups.add(r['group'])
   statuses.append(dict(reviewKey=key(r),sha256=r['sha256'],source=r['source'],group=r['group'],criterion=t,split=r['split'],status=status,reason=reason,targetAnnotations=n,validGeometryAnnotations=valid,reviewed=bool(d),rightsBasis=d.get('rightsBasis') if d else 'publisher declaration only; image review pending',expertLabels=False))
  maskrows=[r for r in training.get('mask',{}).get('rows',[]) if r['target']==t]
  # A negative tile in a positive photo is a negative ROI, not a negative photo.
  whole=collections.defaultdict(lambda:[0,0,False])
  for r in maskrows:
   if r['completeROI']:
    v=whole[r['sha256']];v[0]+=r['positivePixels'];v[1]+=r['knownNegativePixels'];v[2]=True
  negative={h for h,(p,n,c) in whole.items() if c and p==0 and n>0}
  counts.update(eligiblePositivePhotos=len(positive),eligiblePositiveGroups=len(ready_groups),partialPositiveOnlyPhotos=len(partial),fullyReviewedNegativePhotos=len(negative),fullyReviewedNegativeTiles=sum(r['completeROI'] and r['positivePixels']==0 and r['knownNegativePixels']>0 for r in maskrows),knownNegativePixels=sum(r['knownNegativePixels'] for r in maskrows))
  prepared={s:dict(images=len({r['sha256'] for r in maskrows if r['split']==s}),groups=len({r['group'] for r in maskrows if r['split']==s}),positivePhotos=len({r['sha256'] for r in maskrows if r['split']==s and r['positivePixels']}),completeROIs=sum(r['completeROI'] for r in maskrows if r['split']==s),partialROIs=sum(not r['completeROI'] for r in maskrows if r['split']==s)) for s in ('train','validation','test')}
  criteria[t]=dict(counts=dict(counts),sourcePhotoClassLabels=len(associated) if t=='type' else None,deduplicatedSourceGroups=len({r['group'] for r in associated}),geometricCandidateGroups=len(geometric),pendingGroups=len(pending_groups),sources={s:dict(v) for s,v in source.items()},sourceSplits={s:dict(v) for s,v in splits.items()},pendingOrExclusionReasons=dict(reasons),preparedMaskSplits=prepared,previousTypeDevelopmentSplits={s:dict(images=sum(r.get('typeEligible') is True and r['split']==s for r in type_rows),groups=len({r['group'] for r in type_rows if r.get('typeEligible') and r['split']==s})) for s in ('train','validation')} if t=='type' else None,detectorSplits=training.get('detector',{}).get('counts') if t=='acne' else None,preparationComplete=False)
 write('coverage.json',append_active(dict(manifestSHA256=sha(manifest),decisionsSHA256=sha(OUT/'decisions.json'),criteria=criteria,imageCriterionStatuses=statuses,reviewedPhotos=len(decisions),allSelectedSourceImages=len(rows),personIndependent=False,expertLabels=False,unknownIsNotNegative=True,rightsDeclarationsNotIndependentlyVerified=True,trainingLedgerHashes={k:sha(OUT/f'{k}-data.json') for k in training})))
 print(json.dumps({t:{**v['counts'],'groups':v['deduplicatedSourceGroups']} for t,v in criteria.items()},indent=2))

if __name__=='__main__':main()
