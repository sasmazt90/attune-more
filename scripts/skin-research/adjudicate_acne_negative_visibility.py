"""Post-prediction source visibility adjudication, no inference/parameter changes.
This is internal Codex visual engineering review, NOT blinded or clinical truth.
Original all-visible-face negative reviews explicitly leave hair UNKNOWN. Their
anatomical projection leaks over blond/white hair; retain both raw and audited counts.
"""
import json
from prepare_acne_classical_comparison import ROOT,OUT,read,sha
# Explicitly inspected object support; every other produced negative-photo object
# is UNKNOWN/partly hair-covered, never assumed healthy. IDs pinned by result hashes.
KNOWN={
 'A':{'36e4010b':[],'02386f86':[],'0597e811':[],'0560bfd8':[0,1,2,3,5,6],'0f3354ae':[],'33da7a52':[0],'02413bf9':[0]},
 'B':{'36e4010b':[11,12],'02386f86':[0,1,2],'0597e811':[],'0560bfd8':[0,1,2,3,4,5,6,7,10,13,19,20,21,22,23,24],'0f3354ae':[0],'33da7a52':[0,1],'02413bf9':[0,1,2,3]}}

def main():
 rows=[]
 for method in ['A','B']:
  path=OUT/method/'results.json';data=read(path)
  for r in data['rows']:
   if not r.get('valid') or not r['metrics']['verifiedNegativePixels']:continue
   prefix=r['sha256'][:8];known=KNOWN[method][prefix];assert all(0<=v<len(r['candidates']) for v in known)
   for i,obj in enumerate(r['candidates']):
    rows.append(dict(method=method,sha256=r['sha256'],candidateIndex=i,sourceBox=[obj[k] for k in ['x','y','width','height']],status='reviewed-non-pimple-visible-skin-support' if i in known else 'UNKNOWN-hair-or-border-support',basis='existing explicit negative-face review plus source-coordinate visual visibility review; no biological diagnosis',overlaySHA256=sha(OUT/(prefix+'-review.png')) if method=='B' else sha(OUT/'A'/(r['sha256']+'-overlay.png')),resultsSHA256=sha(path)))
 result=dict(version='acne-negative-visibility-adjudication-v1',reviewer='Codex visual engineering; not dermatologist or human adjudication',blinded=False,performedAfterFrozenPredictions=True,parametersChanged=False,newInference=False,scope='object support visibility only; not pixel segmentation/precision',unknownRule='blond hair, white eyebrow hair, beard overlap or ambiguous boundary remains UNKNOWN',rows=rows,counts={k:dict(known=sum(r['method']==k and r['status'].startswith('reviewed') for r in rows),unknown=sum(r['method']==k and r['status'].startswith('UNKNOWN') for r in rows)) for k in ['A','B']})
 (OUT/'negative-visibility-adjudication.json').write_text(json.dumps(result,indent=2),'utf8');print(json.dumps(result['counts']))
if __name__=='__main__':main()