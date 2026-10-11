"""Explicit partial engineering review of additional hash-bound source boards.

Only listed, actually viewed boards enter the review; other photos stay pending.
The running pools and prior review receipts remain immutable.
"""
import json
from expanded_sources import OUT,sha,write
REVIEWED_BOARDS=list(range(61))
RIGHTS={5,7,8,9,15,16,31,33,41,44,49,88,90,96,106,126,128,129,148,154,167,183,201,210,225,232}
COMPONENTS={89,94,99,104,105,112,182,207,214,215}
ACNE={0,2,3,4,6,10,11,12,13,18,19,22,23,26,35,38,46,50,53,54,63,64,65,66,68,69,70,80,83,85,101,107,111,113,115,125,132,133,134,136,138,141,145,158,161,169,172,176,178}
OIL={17,18,21,24,26,27,28,32,36,37,40,46,50,55,70,74,81,82,86,95,100,102,103,120,131,135,142,145,146,151,152,153,155,156,162,175}
RED={34,39,45,52,56,58,59,60,64,79,115,116,117,119,122,137,140,165,170,172,174,176,179}
TONE={43,55,57,68,73,91,97,111,124,130,139,144,147,160,171,176}
BAGS={48,98,109}
ACNE|={184,188,189,202,222,223,238}
OIL|={186,187,192,194,203,206,208,209,216,217,224,229,236}
RED|={180,195,199,223}
TONE|={181,189,193,198,204,205,213,220,221,226,227,233,235,236,238}
BAGS|={185,191,196,197}
RIGHTS|={266,277,283,299}
ACNE|={242,248,250,255,256,263,268,272,275,286,289,297}
OIL|={248,252,254,267,271,276,278,284,287,294,298}
RED|={244,245,249,253,270,273,275,280}
TONE|={240,246,247,248,261,262,275,290,295,298}
BAGS|={241,251,258,259,292}
RIGHTS|={315,326,330,331,333,340,346}
COMPONENTS|={335}
ACNE|={310,312,329,351,357}
OIL|={306,307,308,309,316,317,321,324,332,345,348,350,352,354}
RED|={305,327,341,347}
TONE|={311,320,336,338,342,343,355,357}
BAGS|={318,322}
RIGHTS|={361,366,373,379,382,390,394,407,408,410}
ACNE|={368,371,375,386,398,399,401,404,411,413,418}
OIL|={360,364,370,374,376,381,386,413,414,416}
RED|={367,378,384,393,397,413}
TONE|={363,372,374,380,383,385,387,389,396,403,409,415,419}
BAGS|={377,387,391}
RIGHTS|={430,458,464}
ACNE|={421,422,427,436,437,443,444,449,453,456,457,467,468,475,477}
RED|={425,427,429,431,435,440,442,447,450,451,452,454,461,462,472,478,479}
TONE|={423,427,433,438,446,448,460,472}
RIGHTS|={488,504,506}
ACNE|={481,485,487,489,490,495,498,503,505,510,514,520,524,531,532,533,534}
RED|={483,491,492,502,515,518,522,524,527,528,529,535,538}
TONE|={484,512}
RIGHTS|={557,561,573,574}
ACNE|={542,544,545,550,563,567,572,575,577,580,582,585,586,594}
RED|={540,546,551,553,554,556,562,565,571,578,583,590,591,592,599}
TONE|={541,549,558,569,593,598}
RIGHTS|={607,613,657}
ACNE|={600,603,605,606,612,617,618,621,623,626,627,634,640,651,659}
RED|={601,602,609,620,629,630,637,638,642,646,658}
TONE|={628,645}
RIGHTS|={660,681}
ACNE|={661,668,679,680,682,685,700,703,706,709,711,714,717,718,719}
RED|={663,665,667,671,684,687,690,691,694,695,707,720,722}
TONE|={662,663,666,669,672,673,675,688,692,710,723}

def main():
 path=OUT/'supplement/candidates.json';rows=json.loads(path.read_text('utf8'))['rows'];result=[]
 sets=dict(acne=ACNE,oil=OIL,redness=RED,tone=TONE,bags=BAGS)
 for r in rows:
  i=r['reviewIndex'];board=i//12
  if board not in REVIEWED_BOARDS:continue
  accepted=[t for t in r['reviewTargets'] if i in sets.get(t,set())]
  if i in COMPONENTS:accepted=[]
  reasons={t:('COMPONENT_CROP_GROUP_REVIEW_PENDING' if i in COMPONENTS else 'GENERAL_FOREHEAD_MOUTH_OR_LOWER_LID_WRINKLE_FIELD_NOT_CROWS' if t=='lines' and r['source']=='care' else 'ACTIVE_VS_RESIDUAL_PIGMENT_OR_BAG_VS_NORMAL_LID_OR_COSMETIC_LIGHT_UNCERTAIN') for t in r['reviewTargets'] if t not in accepted}
  result.append(dict(reviewKey=r['reviewKey'],reviewIndex=i,sha256=r['sha256'],board=f'{board:03d}.jpg',boardSHA256=sha(OUT/'supplement/boards'/f'{board:03d}.jpg'),engineeringReview=True,expertLabels=False,predictionsUsed=False,rightsBasis='publisher declaration; individual rights not independently verified',rightsEligible=i not in RIGHTS,excludedReason='VISIBLE_THIRD_PARTY_NOTICE_PROVENANCE_UNRESOLVED' if i in RIGHTS else None,acceptedTargets=accepted,completeMaskTargets=[],completePimpleROI=False,negativeROIs={},targetReasons=reasons,naturalRGB=False if 'oil' in accepted else True,colorCalibrationEligible=False,supervision='genuine local source mask or source area box, partial positives only; diffuse acne is not individual count truth'))
 write('supplement/decisions.json',dict(rows=result,candidatesSHA256=sha(path),reviewedBoards=REVIEWED_BOARDS,pendingPhotos=len(rows)-len(result),expertLabels=False,independentFinal=False))
 print('Supplement reviewed',len(result),'pending',len(rows)-len(result))

if __name__=='__main__':main()
