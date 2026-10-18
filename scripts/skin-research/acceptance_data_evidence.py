"""Read final-data assertions from hash-bound receipts, with missing = unknown.

Development reviews and a prepared unopened manifest cannot stand in for a
completed independent annotation/rights/domain review. No personal data read.
"""
import hashlib,json
from pathlib import Path

FIELDS=['sourceReviewComplete','rightsReviewComplete','labelSemanticsMatched',
        'splitRelationsResolved','unusedHoldout','naturalCameraDomainReviewed','engineeringLabelsDisclosed']

def digest(path):
 with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def final_data(out,target=None):
 out=Path(out);values={k:None for k in FIELDS};proof=[]
 receipt=out/'unused-final-preparation/receipt.json'
 if receipt.exists():
  r=json.loads(receipt.read_text('utf-8-sig'))
  # Preparation explicitly lists unfinished reviews. They remain unfinished.
  pending=' '.join(r.get('missing',[])).lower()
  for field,terms in [('sourceReviewComplete',['annotation','review']),('rightsReviewComplete',['rights']),('naturalCameraDomainReviewed',['natural-camera'])]:
   if all(term in pending for term in terms):values[field]=False
  proof.append(dict(path=str(receipt),sha256=digest(receipt),scope='preparation receipt, not reviewed final evidence'))
 # A target-specific final receipt must reference the actual assertion file
 # and its complete bytes. A free-standing True in the index is insufficient.
 index=out/'final-evidence-index.json'
 if index.exists():
  registry=json.loads(index.read_text('utf-8-sig'))
  for field,ref in registry.get('targets',{}).get(target,{}).items():
   if field not in values:continue
   path=(out/ref['file']).resolve()
   if not path.is_relative_to(out.resolve()):raise ValueError('FINAL_EVIDENCE_PATH_ESCAPE')
   if not path.is_file() or digest(path)!=ref['sha256']:continue
   evidence=json.loads(path.read_text('utf-8-sig'));value=evidence
   try:
    for key in ref['keyPath']:value=value[key]
   except (KeyError,TypeError,IndexError):continue
   if isinstance(value,bool):values[field]=value
   proof.append(dict(field=field,path=str(path),sha256=ref['sha256'],keyPath=ref['keyPath']))
 return {**values,'evidenceFiles':proof,'missingEvidence':[k for k in FIELDS if values[k] is not True],
         'developmentDoesNotConstituteIndependentFinal':True}
