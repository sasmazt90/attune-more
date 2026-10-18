"""Count only tile/source orders proven consumed; report lower bounds honestly."""
import collections,json
from pathlib import Path
from expanded_sources import OUT,write,sha

def main():
 folder=OUT/'mask-continuation';generation=folder/(folder/'CURRENT').read_text('utf8');state=json.loads((generation/'state.json').read_text('utf8'));data=json.loads((OUT/'continuation-valid-skin-data.json').read_text('utf8'));tr=[r for r in data['rows'] if r['split']=='train'];ids=set();proofs=[]
 prior=OUT/'actual-consumed-training-coverage.json'
 if prior.exists():
  previous=json.loads(prior.read_text('utf8'))
  if previous['ledgerSHA256']==sha(OUT/'continuation-valid-skin-data.json'):
   ids.update(previous['provenConsumedTileIDs']);proofs=previous.get('proofs',[])
   proofs.append(dict(source='previous-hash-bound-actual-consumption-receipt',receiptSHA256=sha(prior),cumulativeKnownConsumptionPreserved=True))
 migration=json.loads((folder/'support-migration.json').read_text('utf8'))
 if state['epoch']>=1:
  for pair in migration['oldOrder']:ids.update(pair)
  proofs.append(dict(source='support-migration.json',fullOrderConsumedByCompletedEpoch=1))
 for p in folder.glob('frozen-user-correction-20261011/**/state.json'):
  archived=json.loads(p.read_text('utf8'));full=archived['epoch']+1<=state['epoch'];pairs=archived['order'] if full else archived['order'][:archived['cursor']]
  for pair in pairs:ids.update(pair)
  proofs.append(dict(source=str(p.relative_to(folder)),futureOrderIncludedOnlyAfterProvenEpochCompletion=full,archivedEpoch=archived['epoch'],archivedCursor=archived['cursor']))
 for pair in state['order'][:state['cursor']]:ids.update(pair)
 ids.update(state.get('actualConsumedTileIDs',[]));used=[tr[i] for i in ids];counts={}
 for target in data['targets']:
  pool=[r for r in tr if r['target']==target];pos={r['sha256'] for r in pool if r['positivePixels']};rs=[r for r in used if r['target']==target]
  counts[target]=dict(provenPositivePhotos=len({r['sha256'] for r in rs if r['positivePixels']}),provenIndependentNegativePhotos=len({r['sha256'] for r in rs if r['knownNegativePixels'] and r['sha256'] not in pos}),provenPositiveROIs=sum(bool(r['positivePixels']) for r in rs),provenOnlyNegativeROIs=sum(r['positivePixels']==0 and r['knownNegativePixels']>0 for r in rs),lowerBound=True,phaseMixedExposureDisclosed=True)
 detector=OUT/'yolox';detgen=detector/(detector/'CURRENT').read_text('utf8');detstate=json.loads((detgen/'state.json').read_text('utf8'));detdata=json.loads((OUT/'detector-data.json').read_text('utf8'));tilepath=detector/'tensor-overlap.json';tiles=json.loads(tilepath.read_text('utf8'))['rows'];detids=set()
 if prior.exists():
  previous=json.loads(prior.read_text('utf8'))
  if previous.get('detectorLedgerSHA256')==sha(OUT/'detector-data.json'):detids.update(previous.get('provenDetectorConsumedTileIDs',[]))
 for p in detector.glob('frozen-user-correction-20261011/**/state.json'):
  archived=json.loads(p.read_text('utf8'));detids.update(archived['order'] if archived['epoch']+1<=detstate['epoch'] else archived['order'][:archived['cursor']])
 migration=json.loads((detector/'support-migration.json').read_text('utf8'));detids.update(migration['order'] if migration['epoch']+1<=detstate['epoch'] else migration['order'][:migration['cursor']]);detids.update(detstate['order'][:detstate['cursor']]);detids.update(detstate.get('actualConsumedTileIDs',[]))
 usedtiles=[tiles[i] for i in detids];positive_photos={r['sha256'] for r in tiles if r['boxes']}
 detector_counts=dict(provenPositivePhotos=len({r['sha256'] for r in usedtiles if r['boxes']}),provenIndependentNegativePhotos=len({r['sha256'] for r in usedtiles if r['knownNegativeCells'] and r['sha256'] not in positive_photos}),provenPositiveROIs=sum(bool(r['boxes']) for r in usedtiles),provenOnlyNegativeROIs=sum(not r['boxes'] and bool(r['knownNegativeCells']) for r in usedtiles),lowerBound=True,sourceLesionsInPreparedTrain=detdata['counts']['train']['lesions'])
 new_phases={}
 for phase,ledger in [('negative-mask-continuation','negative-expanded-mask-data.json'),('negative-yolox','negative-expanded-detector-data.json')]:
  p=OUT/phase
  if not (p/'CURRENT').exists():continue
  ns=json.loads((p/(p/'CURRENT').read_text('utf8')/'state.json').read_text('utf8'));newdata=json.loads((OUT/ledger).read_text('utf8'));used=ns.get('actualConsumedTileIDs',[])
  if 'mask' in phase:
   pool=[r for r in newdata['rows'] if r['split']=='train'];bytarget={}
   for target in newdata['targets']:
    rs=[pool[i] for i in used if pool[i]['target']==target];positive={r['sha256'] for r in pool if r['target']==target and r['positivePixels']}
    bytarget[target]=dict(provenPositivePhotos=len({r['sha256'] for r in rs if r['positivePixels']}),provenIndependentNegativePhotos=len({r['sha256'] for r in rs if r['knownNegativePixels'] and r['sha256'] not in positive}),provenPositiveROIs=sum(bool(r['positivePixels']) for r in rs),provenOnlyNegativeROIs=sum(not r['positivePixels'] and r['knownNegativePixels']>0 for r in rs))
   measured=bytarget
  else:
   nt=json.loads((p/'tensor-overlap.json').read_text('utf8'))['rows'];rs=[nt[i] for i in used];positive={r['sha256'] for r in nt if r['boxes']};measured=dict(provenPositivePhotos=len({r['sha256'] for r in rs if r['boxes']}),provenIndependentNegativePhotos=len({r['sha256'] for r in rs if r['knownNegativeCells'] and r['sha256'] not in positive}),provenPositiveROIs=sum(bool(r['boxes']) for r in rs),provenOnlyNegativeROIs=sum(not r['boxes'] and bool(r['knownNegativeCells']) for r in rs))
  new_phases[phase]=dict(ledgerSHA256=sha(OUT/ledger),validatedEpochs=ns['epoch'],partialCursor=ns['cursor'],separatePhaseOnlyNotAddedToParentCounts=True,counts=measured)
 write('actual-consumed-training-coverage.json',dict(mask=counts,detector=detector_counts,newPhaseActualConsumption=new_phases,detectorLedgerSHA256=sha(OUT/'detector-data.json'),detectorTensorOrderSHA256=sha(tilepath),provenDetectorConsumedTileIDs=sorted(detids),phaseEpochs=state['epoch'],cursor=state['cursor'],checkpointModelSHA256=state['modelSHA256'],ledgerSHA256=sha(OUT/'continuation-valid-skin-data.json'),proofs=proofs,provenConsumedTileIDs=sorted(ids),preparedPoolNotSubstitutedForTrainingExposure=True,newNegativePhaseStarted=bool(new_phases)))
 print(json.dumps(dict(mask=counts,detector=detector_counts)),flush=True)
if __name__=='__main__':main()
