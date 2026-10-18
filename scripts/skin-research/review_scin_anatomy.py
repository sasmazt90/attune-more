"""Record visual anatomy review of the 169 numbered contact-sheet candidates.
This is an AI-assisted visible-anatomy exclusion, NOT dermatologist diagnosis,
lesion annotation, full-face truth or a training target. Keep uncertainty open.
Contact order is tied to the complete pinned geometry manifest SHA256.
"""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'audit-results/skin-expanded-20261008/scin'
# Obvious limbs/trunk/scalp/feet falsely returned as a face by the SDK.
NON_FACE={21,28,33,38,42,45,46,53,54,58,59,65,67,72,73,76,78,83,86,87,88,89,91,92,101,126,127,128,129,130,131,132,133,136,137,138,140,141,143,144,146,151,152,155,157,159,160,163,164,165,167}

def main():
 manifest=OUT/'manifest.json';rows=json.loads(manifest.read_text('utf8'))
 candidates=[r for r in rows if r['geometry'].get('faces')==1];assert len(candidates)==169
 for i,row in enumerate(candidates):
  row['visualAnatomyReview']={'reviewer':'AI visual inspection of four native-photo contact sheets','contactIndex':i,'status':'reject-obvious-non-face' if i in NON_FACE else 'visible-face-surface-candidate','expertClinicalReview':False,'lesionPresenceConfirmed':False}
 usable=[r for i,r in enumerate(candidates) if i not in NON_FACE and r['qualityAudit']['engineeringUsable'] and r['expertGradableCase'] and r['target'] in [0,1]]
 def summary(rs):
  return {'images':len(rs),'cases':len({r['case_id'] for r in rs}),'positiveProxyImages':sum(r['target']==1 for r in rs),'positiveProxyCases':len({r['case_id'] for r in rs if r['target']==1}),'negativeProxyImages':sum(r['target']==0 for r in rs)}
 report={'geometryManifestSHA256':hashlib.sha256(manifest.read_bytes()).hexdigest(),'reviewedCandidates':169,'obviousNonFaceRejected':len(NON_FACE),'anatomyReviewIsClinicalTruth':False,'postVisualFaceSurfaceQualityCaseProxy':summary(usable),'fullGeometryPostVisual':summary([r for r in usable if r['geometry']['full']]),'partialGeometryPostVisual':summary([r for r in usable if not r['geometry']['full']]),'regionalExpertLabels':0,'trainingAdmitted':False,'remaining':'Expert photo-specific anatomy/lesion presence and confirmed absence labels; neutral pose/camera-domain validation. Full geometry flag does not prove a complete unoccluded face.'}
 (OUT/'visual-reviewed-manifest.json').write_text(json.dumps(candidates,indent=2),'utf8');(OUT/'visual-review-report.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report))
if __name__=='__main__':main()
