"""Hash-bound engineering negative photo review, distinct from training exposure."""
import collections,json
from expanded_sources import OUT,sha,write
# All ten candidate boards were actually viewed. No source class or prediction
# supplies absence labels. Uncertain targets remain absent from this ledger.
NATURAL={4,8,9,14,23,28,36,38,43,44,49,50,53,57,58,60,62,67,69,70,72,76,78,79,82,84,85,87,89,90,94,95,96,97,98,99,100,102,103,105,109,110,114,117}
NEG={
 'acne':{4,8,14,49,50,58,62,69},
 'oil':{4,14,23,49,50,53,69},
 'redness':{14,49},'tone':{14,49},'dark':set(),
 'lines':{4,8,9,14,23,28,36,38,43,44,49,53,57,58,60,62,67,69,70,79,85,87,94,95,96,98,105,117},
 'bags':{4,8,9,14,23,28,36,38,43,44,49,50,53,57,58,60,62,67,69,70,79,85,87,94,95,96,98,105,117},
 'dry':{4,8,9,14,23,28,36,38,43,44,49,50,53,57,58,60,62,67,69,70,72,76,78,79,82,85,87,89,90,94,95,96,97,98,99,100,102,105,109,110,114,117}}
LOW_DETAIL={22,27,30,33,74,77,81,84,86,92,93,103,111,115,116,119}
COLLAGE={17,18,35,55,73,83,101,112}
SOURCE_NOTICE={6,11,13,16,32,34,45,46,47,59,65,80,113}
rows=json.loads((OUT/'negative-expansion/candidates.json').read_text('utf8'))['rows'];decisions=[]
for r in rows:
 i=r['reviewIndex'];targets=[t for t,ids in NEG.items() if i in ids]
 reason='VISIBLE_NATURAL_APPEARANCE_ENGINEERING_REVIEW' if i in NATURAL else 'UNDOCUMENTED_COMMERCIAL_EDITORIAL_OR_PROCESSED_IMAGE'
 if i in LOW_DETAIL:reason='INSUFFICIENT_NATIVE_DETAIL_FOR_ABSENCE_REVIEW';targets=[]
 if i in COLLAGE:reason='COMPONENT_RELATION_OR_ARTIFICIAL_TREATMENT_APPEARANCE_PENDING';targets=[]
 if i in SOURCE_NOTICE:reason='VISIBLE_THIRD_PARTY_SOURCE_NOTICE_UNRESOLVED';targets=[]
 decisions.append(dict(reviewIndex=i,sha256=r['sha256'],group=r['group'],split=r['split'],boardSHA256=sha(OUT/'negative-expansion/boards'/f'{i//12:02d}.jpg'),reviewed=True,negativeTargets=targets,rightsEligible=i in NATURAL and i not in LOW_DETAIL,rightsBasis='Inherited publisher declaration; individual photo rights not independently verified',reason=reason,expertLabels=False,gradesAvailable=False,sourceClassUsed=False,predictionsUsed=False,negativeScope='visible anatomical skin only; eyes/lips/brows/nostrils/hair/occlusion unknown',wholePhotographHealthy=False))
write('negative-expansion/review.json',dict(version='criterion-specific-visible-negative-review-v1',candidatesSHA256=sha(OUT/'negative-expansion/candidates.json'),rows=decisions,allTenBoardsActuallyViewed=True,independentFinal=False,counts={t:{s:len({r['group'] for r in decisions if t in r['negativeTargets'] and r['split']==s}) for s in ['train','validation']} for t in NEG},trainingExposure=False))
print(json.dumps({t:len(ids) for t,ids in NEG.items()}))
