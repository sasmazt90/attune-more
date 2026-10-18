"""Record the 158 source overlays and 12 native Pimple crops reviewed this run.

These are explicit engineering judgements, not expert truth or unused-test labels.
IDs are bound to the candidate photo hashes. No predictions supplied any labels.
"""
import json
from selected_sources import OUT,write,sha

def main():
 path=OUT/'review/candidates.json';c=json.loads(path.read_text('utf8'));assert len(c['rows'])==158
 assert not (OUT/'review/decisions.json').exists(),'Frozen review preserved'
 stock={3,5,7,10,16,18,22,23,42,46,47,58,59,63,65,90,98,105,123,130,133,134,135,139,152}
 processed={64,80,84,*range(85,107),*range(140,142),144,145,146,149,151,*range(152,158)}
 complete={0:['redness'],4:['redness'],12:['redness'],14:['redness'],15:['redness'],13:['tone'],17:['oil'],26:['oil'],21:['bags'],24:['bags'],45:['bags','dark'],48:['dark'],50:['bags','dark'],55:['lines'],57:['lines'],67:['lines'],69:['lines'],72:['lines'],75:['lines'],79:['lines'],82:['lines'],83:['lines']}
 negative={27:['lines','bags'],29:['lines','bags'],30:['lines','bags'],31:['lines','bags'],32:['lines','bags'],34:['lines','bags'],35:['lines','bags'],38:['lines','bags'],39:['lines','bags'],40:['lines','bags'],41:['lines','bags'],113:['oil','redness','tone','lines','dark','bags'],119:['oil','lines','bags'],150:['bags','lines']}
 positives={
  'redness':{0,3,4,12,14,15,28,33,35,36,43,44,108,112,125,132,138,157},
  'oil':{1,2,17,25,26,27,32,37,40,41,122,127,129,138},
  'tone':{2,6,13,19,20,27,28,29,30,31,32,33,35,36,37,43,44,60,61,62,66,74,107,111,112,125,126,128,132},
  'lines':{45,50,52,54,55,56,57,67,69,71,72,75,79,82,83,107,109,114,116,117,118},
  'dark':{11,24,26,45,48,50,51,62,68,70,74,76,77,78,119,120,142,143,147,148},
  'bags':{21,24,45,50,114,117},
  'acne':{1,6,19,27,28,29,30,31,32,33,34,35,36,37,38,43,44,60,61,62,66,112,125,126},
  'dry':{153,154,155,156},
  'sag':{45,50,71,75,82,107,114}}
 negatives={
  'redness':{1,2,8,9,11,17,25,26,27,39,40,41,113,119,122,127},
  'oil':{0,4,12,14,15,24,28,29,31,33,35,43,44,45,50,55,57,67,72,75,82,113,119,125,132},
  'tone':{8,9,113},
  'lines':set(negative)|{6,19,20,24,26,113,119},
  'dark':{9,113},
  'bags':set(negative)|{6,19,20,113,119,150},
  'acne':{8,9,11,21,24,26,45,50,55,57,67,69,71,72,75,79,82,83,113,114,116,117,118,119,120,121,150},
  'dry':{1,2,6,8,9,11,17,19,20,21,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,43,44,113,119,122,127,128},
  'sag':{1,2,6,8,9,11,19,20,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,43,44,113,119,121,122,125,126,127,150}}
 records=[]
 for r in c['rows']:
  i=r['reviewIndex'];labels={t:'positive' if i in positives[t] else 'negative' if i in negatives[t] else 'uncertain' for t in positives}
  scopes=list(dict.fromkeys(complete.get(i,[])+negative.get(i,[])))
  notes=['Visual engineering review of source crop and typed annotation overlay; publisher declaration is not a third-party rights guarantee.','Unlisted targets remain uncertain; no CSV zero becomes a negative mask.']
  if i in stock:notes.append('Known stock/watermark or unsupported commercial/clinical promotional provenance: excluded pending individual rights evidence.')
  if i in processed or r.get('naturalRGB') is False:notes.append('Processed/CLAHE, grayscale, cutout, collage or black-square corruption: excluded from natural RGB calibration and current natural full-face training.')
  if r['source']=='smart':notes.append('Pimple-only boxes inspected at source crop; flat marks, freckles and other labels retained as confounders. Unlabelled active lesions remain possible, so ROI completeness is NOT asserted.')
  if scopes:notes.append('Entire applicable visible anatomical ROI reviewed; original source polygon boundaries are approximate engineering targets, not expert pixel truth.')
  if i in [128,153,154,156]:notes.append('Peeling coating/cosmetic intervention possible; texture support/control only, never biological moisture or natural dry-grade calibration.')
  if i in [49,51,55,69,70,83,117,121]:notes.append('Smile/expression retained as a confounder; no age-based sag label.')
  if i in [9,17,25,28,32,37,68,77,78,121,122]:notes.append('Direction of illumination, head pose, hat or pigmentation retained as confounders.')
  if i in [8,21,39,40,45,50,55,72,79,82,113,114,116,118]:notes.append('Beard/hair, normal folds, glasses or natural jaw/face shape checked as confounders; unavailable ROI must remain null.')
  eligible=i not in processed and r.get('naturalRGB') is not False
  no_acne=i in negatives['acne'] and eligible and i not in stock
  records.append(dict(sha256=r['sha256'],reviewIndex=i,naturalEligible=eligible,rightsEligible=i not in stock,rightsBasis='publisher-declared CC-BY-4.0; no detected third-party restriction' if i not in stock else 'excluded',completeMaskTargets=scopes,maskOverrides={t:[] for t in negative.get(i,[])},excludedMaskTargets=['bags'] if i in [8,9,11,49,51] else [],pimpleBoxesReviewed=r['source']=='smart' or no_acne,completePimpleROI=no_acne,appearanceLabels=labels,notes=notes))
 write('review/decisions.json',dict(candidateSHA256=sha(path),manifestSHA256=c['manifestSHA256'],rows=records,engineeringLabels=True,expertLabels=False,predictionsUsed=False,independentFinal=False,reviewedSheets=14,nativePimpleDetailSheets=3))
 print('Frozen engineering decisions',len(records),flush=True)
if __name__=='__main__':main()
