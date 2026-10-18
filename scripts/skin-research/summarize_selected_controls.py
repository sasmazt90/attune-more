"""Disclosed engineering appearance separation, with nulls and groups retained."""
import collections,json
import numpy as np
from selected_sources import OUT,write

def main():
 report=json.loads((OUT/'natural-appearance-review.json').read_text('utf8'));rows=report['rows'];summary={}
 for target in ['acne','oil','dry','redness','tone','lines','dark','bags','sag']:
  buckets=collections.defaultdict(dict);missing=collections.Counter();errors=[]
  for r in rows:
   label=r['engineeringAppearanceLabels'].get(target,'uncertain')
   if r['result'] is None:missing[r['captureRejectedReason']]+=1;continue
   v=next(v for v in r['result']['measurements'] if v['id']==target)
   if v['value'] is None:missing[v['reason'] or 'UNAVAILABLE']+=1;continue
   buckets[label].setdefault(r['group'],[]).append(float(v['value']))
   if label in ['positive','negative']:errors.append(dict(source=r['source'],sourceSHA256=r['sha256'],group=r['group'],engineeringLabel=label,value=v['value'],unit=v['unit'],notes=r['reviewNotes']))
  levels={}
  for label,groups in buckets.items():
   values=[float(np.median(v)) for v in groups.values()]
   levels[label]=dict(sourceGroups=len(values),median=float(np.median(values)),minimum=min(values),maximum=max(values))
  pair=None
  if 'positive' in buckets and 'negative' in buckets:
   positive=np.asarray([np.median(v) for v in buckets['positive'].values()]);negative=np.asarray([np.median(v) for v in buckets['negative'].values()]);pair=float(((positive[:,None]>negative).astype(float)+.5*(positive[:,None]==negative)).mean())
  # Ranking is descriptive. It does not select a score/threshold or establish
  # expert accuracy, independent acceptance or camera-user performance.
  summary[target]=dict(engineeringGroupAppearance=levels,descriptivePositiveAboveNegativePairFraction=pair,unavailableOrRejected=dict(missing),examples=errors,acceptedNewMethod=False,calibratedSeverity=False,independentTest=False)
 local={}
 for target in ['lines','dark','bags']:
  values=collections.defaultdict(dict);unavailable=collections.Counter()
  for r in rows:
   if r['result'] is None:continue
   v=next((v for v in r['result']['regionMeasurements'].get('periorbital',[]) if v['id']==target),None)
   if not v or v['value'] is None:unavailable[v['reason'] if v else 'ROI_NOT_VISIBLE']+=1;continue
   label=r['engineeringAppearanceLabels'].get(target,'uncertain');values[label].setdefault(r['group'],[]).append(v['value'])
  local[target]=dict(scope='actual visible periorbital ROI; full-face coverage not required; no synthetic pixel truth',levels={label:dict(sourceGroups=len(groups),median=float(np.median([np.median(v) for v in groups.values()])),minimum=float(min(min(v) for v in groups.values())),maximum=float(max(max(v) for v in groups.values()))) for label,groups in values.items()},unavailable=dict(unavailable))
 write('appearance-summary.json',dict(naturalPhotos=len(rows),sourceGroups=len({r['group'] for r in rows}),engineeringLabels=True,expertLabels=False,thresholdSelected=False,criteria=summary,appropriateLocalROI=local,qualityScope='offline source pose/luminance eligibility; full physical camera acceptance only covered by separately disclosed fixture'))
 print(json.dumps({k:{n:v[n] for n in ['engineeringGroupAppearance','descriptivePositiveAboveNegativePairFraction','unavailableOrRejected']} for k,v in summary.items()},indent=2))
if __name__=='__main__':main()
