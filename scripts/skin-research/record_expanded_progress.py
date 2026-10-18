"""Sanitized phase-separated progress snapshot; never treats preparation as training."""
import argparse,datetime,json,shutil
from expanded_sources import OUT,ROOT,write,sha


def read(path,default=None):return json.loads(path.read_text('utf8')) if path.exists() else default

def compact(metrics):
 return {key:value for key,value in metrics.items() if key not in ['rows','classes','confusionMatrix']}

def main(save_docs=False):
 coverage=read(OUT/'coverage.json');actual=read(OUT/'actual-consumed-training-coverage.json');snapshots={}
 for name in ['yolox','mask-continuation','negative-yolox','negative-mask-continuation']:
  folder=OUT/name
  if not (folder/'CURRENT').exists():continue
  generation=(folder/'CURRENT').read_text('utf8');state=read(folder/generation/'state.json');history=[]
  migration=read(folder/'support-migration.json',{});numeric=read(folder/'numerical-correction.json',{})
  for entry in state['history']:
   if name.startswith('negative-'):phase=name
   elif name=='mask-continuation':phase='mixed-support-transition' if entry['epoch']==1 else 'complete-refined-support'
   elif entry.get('numericalCorrectionRevalidation'):phase='same-selected-weights-revalidated-with-bounded-decoder'
   elif numeric and entry['epoch']==numeric['epoch']+1:phase='mixed-numerical-transition'
   elif migration and entry['epoch']==migration['epoch']+1:phase='mixed-negative-support-transition'
   elif migration and entry['epoch']>migration['epoch']+1:phase='bounded-decoder-complete-refined-support'
   else:phase='bounded-decoder-prior-support'
   metrics=entry['validation'];metrics={t:compact(m) for t,m in metrics.items()} if 'mask' in name else compact(metrics)
   history.append(dict(epoch=entry['epoch'],phase=phase,loss=entry.get('loss'),epochSeconds=entry['epochSeconds'],metrics=metrics))
  snapshots[name]=dict(checkpoint=generation,modelSHA256=state['modelSHA256'],optimizerSHA256=state['optimizerSHA256'],completedEpochs=state['epoch'],partialCursor=state['cursor'],step=state['step'],trainingComplete=(folder/'selection.json').exists(),history=history,protocol=read(folder/'protocol.json'),parent=read(folder/'parent-receipt.json'),lastEpochSeconds=history[-1]['epochSeconds'] if history else None)
  if state.get('targetBest'):snapshots[name]['selectedPerTarget']={target:dict(epoch=value['epoch'],score=value['score'],metrics=compact(value['metrics'])) for target,value in state['targetBest'].items()}
  if isinstance(snapshots[name]['parent'],dict):snapshots[name]['parent'].pop('parentHistory',None)
  if name=='yolox':snapshots[name]['originalDecoderHistoryBeforeCorrection']=[dict(epoch=e['epoch'],metrics=compact(e['validation'])) for e in read(folder/'numerical-prior-history.json',[])]
  if name=='mask-continuation':snapshots[name]['parentCompletedEpochs']=2
 decisions=read(OUT/'label-function-current-decisions.json',{'rows':{}})
 source={target:{key:v[key] for key in ['counts','sources','sourceSplits','deduplicatedSourceGroups','pendingGroups','pendingOrExclusionReasons','separatePreparedPhases','provenConsumedTrainingLowerBound','negativeExpandedDetectorPhase'] if key in v} for target,v in coverage['criteria'].items()}
 unused=read(OUT/'unused-final-preparation/typed-label-index.json',{});unused={k:v for k,v in unused.items() if k!='rows'}
 ready_keys=['type','acneDetector','oilAnalytic','dryAnalytic','rednessAnalytic','toneAnalytic','linesAnalytic','darkAnalytic','bagsAnalytic','sagAnalytic']
 all_ready=all(key in decisions['rows'] and decisions['rows'][key]['decision']['accepted'] for key in ready_keys)
 result=dict(version='skin-expanded-actual-phase-progress-v2',capturedUTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),training=snapshots,actualConsumedLowerBounds=actual['mask'],actualDetectorConsumedLowerBound=actual.get('detector'),dryPresencePhase=read(OUT/'negative-dry-presence/selection.json'),dryPresenceDataCounts=read(OUT/'negative-dry-presence/data.json',{}).get('counts'),sourceInventory=source,typeSourceClassDistribution=decisions['rows'].get('type',{}).get('evidence',{}).get('sourceClassDistribution'),acceptance={k:v['decision'] for k,v in decisions['rows'].items()},naturalAppearanceControls=read(OUT/'current-proxy-controls-v3/receipt.json',{}).get('summary'),unusedFinalPreparation=unused,freeDiskGB=shutil.disk_usage(OUT).free/1024**3,allTenUserReady=all_ready,oneUninterruptedTrainingCurveAllowed=False,gradeLabelsNotInvented=True)
 write('progress-snapshot.json',result)
 if save_docs:(ROOT/'docs/skin-expanded-progress-20261011.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),'utf8')
 print('Sanitized actual progress snapshot saved',result['capturedUTC'],flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--write-docs',action='store_true');main(p.parse_args().write_docs)
