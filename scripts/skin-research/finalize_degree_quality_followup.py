"""Complete separate 113-photo ordinal-source engineering quality review.

Decisions inspect source pixels/occlusion/ad content; no error-based removal.
V1 exploratory artifacts are retained. V2 uses identical surviving rows for
both feature backbones; final sources remain closed.
"""
import json,collections
from diagnose_followup import NEW,write
from prepare_focused_data import sha
DECISIONS={4:'visible-cosmetic-product-advertisement',20:'clearly-stylized-heavy-processing',43:'bilateral-cheek-hand-occlusion',50:'forehead-hand-occlusion',63:'forehead-hand-occlusion',104:'forehead-hand-occlusion'}
def main():
    assert sha(NEW/'quality/degree-index.json')=='7bf0432f00cc650d0bd3d05b4fef9886da69dbc0b23d0e0a0c9bdd5d5b4957cd','DEGREE_REVIEW_INDEX_CHANGED'
    p=NEW/'development-manifest.json';m=json.loads(p.read_text());review=json.loads((NEW/'quality/degree-index.json').read_text());groups={review[i]['group']:reason for i,reason in DECISIONS.items()}
    decisions=[]
    for r in m['rows']:
        if r.get('degreeEligible') and r['group'] in groups:
            r['degreeEligible']=False;decisions.append(dict(sha256=r['sha256'],group=r['group'],reason=groups[r['group']],labelChanged=False))
    write('quality/degree-decisions.json',dict(reviewedPhotos=len(review),allSourcesReviewed=True,engineeringReviewNotExpertLabels=True,modelOutcomeUsed=False,decisions=decisions,ambiguousRetouchOrMakeupNotAutomaticallyExcluded=True,originalIndexSHA256=sha(NEW/'quality/degree-index.json')))
    m['degreeQualityReviewSHA256']=sha(NEW/'quality/degree-decisions.json');write('development-manifest-v2.json',m)
    print(json.dumps(dict(degrees=collections.Counter(r['split'] for r in m['rows'] if r.get('degreeEligible')),additionalExclusions=len(decisions))),flush=True)
if __name__=='__main__':main()
