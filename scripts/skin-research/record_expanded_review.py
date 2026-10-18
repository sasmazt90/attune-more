"""Explicit engineering decisions from hash-bound source/annotation boards.

No prediction or expert diagnosis. Partial source annotations are never promoted
to exhaustive pixel labels. Unseen boards/uncertain targets remain pending.
"""
import json
from expanded_sources import OUT,PREVIOUS,TARGETS,write,sha

# Visible notices/stock or third-party promotional provenance not established by
# the publisher declaration. These are concrete reviewed exclusions, not a
# dataset-wide statement about rights of uninspected images.
RIGHTS={5:'SFS notice',12:'First Derm',15:'Dermnet',17:'SFS',19:'clinic promotion',20:'Dermnet',28:'medical source notice',39:'product promotion',45:'Dermnet',68:'physician notice',72:'product comparison',75:'Dermnet',85:'Dermnet',92:'Science Photo',114:'GirlCircle',115:'Dermnet',126:'Alamy',140:'Dermnet',147:'Dermnet',149:'external notice',150:'Dermnet',157:'medical photo notice',163:'photo notice',165:'Galderma',168:'medical source notice',177:'Science Photo',181:'promotion',183:'Shutterstock',200:'medical source notice',202:'Getty',210:'Dermnet',211:'product promotion',215:'commercial edited composition',221:'external photo notice',232:'Dermnet',241:'product promotion',247:'collage unknown provenance',250:'medical source notice',255:'Dermnet',261:'promotion notice',268:'Instagram photo credit',273:'Dermnet',285:'external photo credit'}
COLLAGE={2,25,30,32,132,167,214,265}
NON_FACE={98,297}
ACTIVE={35,40,48,60,65,70,100,105,120,122,125,127,135,138,143,145,155,170,172,175,185,190,193,195,205,220,225,226,230,235,240,245,246,248,257,260,270,275,280,282,287,290,295}
PIGMENT={3,13,18,23,33,38,43,53,58,63,73,78,83,93,103,108,113,118,123,128,133,138,153,158,173,174,178,184,188,198,208,213,218,219,223,228,233,238,243,253,254,258,259,263,274,278,283,284,288,293,298}
# Bag labels often trace discoloration/normal lid rather than a visible contour.
# Keep them uncertain rather than teaching dark pigmentation as bag presence.
BAG_CONTOUR={4,139,144,199,209,249,289}
SMART_RIGHTS={303,320,326,333,346,361,364,367,368,377,390,391,398,405,410,421,422,440,441,442,498}
SMART_UNCERTAIN={305,319,330,338,339,341,343,348,350,354,355,363,366,374,379,388,397,402,407,409,423,428,432,434,435,445,447,450,457,464,467,468,471,474,481,488,491,497}
DC_BAGS={507,553,566,580,599,643,669,676,677}
DC_DARK={503,504,505,506,508,514,516,520,526,528,536,538,544,548,556,562,564,568,572,576,578,579,580,584,586,588,592,593,594,595,604,606,607,608,610,616,618,622,624,628,634,640,642,644,648,651,654,656,657,658,659,661,662,664,666,668,670,674,676,678}
WRINKLE_LINES={831,837,843,846,870,887,891,894,897,899}
WRINKLE_DARK={830,832,850,853,856,868,872,875,877,878,886,888,892}
WRINKLE_ACNE={830,832,833,839,842,845,848,854,857,863,866,869,872,875}
DRY_VISIBLE={961,967,969,975,979,981,983,985,987,989,991,993,995,997,999,1001,1003,1005,1007,1009,1011,1015,1017,1021,1023,1025,1027,1031,1033,1035,1037,1039,1050,1054,1062,1067,1074,1078,1098,1103,1106,1110,1118,1131,1138,1200,1206,1227,1242}
CLEAN_ACNE={1040,1044,1047,1056,1059,1064,1068,1076,1080,1083,1084,1088,1092,1096,1100,1108,1120,1124,1127,1128,1131,1132}
CLEAN_OIL={1049,1059,1069,1085,1096}
CLEAN_RED={1043,1047,1051,1055,1059,1063,1083,1087,1115,1123,1127,1131}
ARNOLD_TONE={1140,1143,1146,1152,1155,1158,1161,1164,1167,1170,1173,1176,1179,1185,1188}
ARNOLD_BAGS={1163,1175,1187}
EXTRA_NOTICES={836,851,860,878,940,959,963,965,966,970,973,977,988,990,994,1013,1016,1022,1029,1030,1034,1048,1058,1060,1061,1071,1091,1095,1097,1099,1104,1107,1111,1114,1119,1122,1126,1130,1139,1191,1197,1209,1215,1222,1230,1232,1233,1236,1243,1244,1277,1295,1303,1305}

def main():
 source=OUT/'candidates.json';c=json.loads(source.read_text('utf8'));decisions=[]
 for r in c['rows']:
  i=r['reviewIndex']
  d=dict(reviewKey=r['reviewKey'],reviewIndex=i,sha256=r['sha256'],engineeringReview=True,expertLabels=False,predictionsUsed=False,
   rightsBasis='publisher declared CC-BY-4.0; individual rights not independently verified',rightsEligible=i not in RIGHTS,
   excludedReason='VISIBLE_THIRD_PARTY_PROVENANCE_UNRESOLVED:'+RIGHTS[i] if i in RIGHTS else None,
   completeMaskTargets=[],completePimpleROI=False,negativeROIs={},acceptedTargets=[],targetReasons={},naturalRGB=True,
   appearanceLabels={t:'uncertain' for t in TARGETS},board=f'{i//12:03d}.jpg',boardSHA256=sha(OUT/'boards'/f'{i//12:03d}.jpg'))
  if i in COLLAGE:d['excludedReason']='COLLAGE_REQUIRES_COMPONENT_GROUP_AND_CROP_REVIEW'
  if i in NON_FACE:d['excludedReason']='NON_FACIAL_DOMAIN';d['naturalRGB']=True
  for t in r['reviewTargets']:
   okay=(t=='oil' or t=='redness' or t=='acne' and i in ACTIVE or t=='tone' and i in PIGMENT or t=='bags' and i in BAG_CONTOUR)
   if okay:d['acceptedTargets'].append(t);d['appearanceLabels'][t]='positive'
   else:d['targetReasons'][t]='AMBIGUOUS_ACTIVE_VS_RESIDUAL_PIGMENT' if t=='acne' else 'AMBIGUOUS_BAG_VS_DARK_NORMAL_LID' if t=='bags' else 'UNCERTAIN_APPEARANCE_TARGET'
  # Cosmetic studio shine is localization supervision, not natural-camera oil
  # calibration or a skin-type/physiological oil quantity label.
  if 'oil' in r['reviewTargets'] and i not in {128,136,143,154,178,184,218,219,226,246,259,266,283,284}:
   d['naturalRGB']=False;d['colorCalibrationReason']='COSMETIC_LIGHT_OR_PROCESSED_SHINE_CONFOUNDER'
  if i in {90,110,130,215}:d['naturalRGB']=False
  if 300<=i<500:
   d['acceptedTargets']=[] if i in SMART_UNCERTAIN else ['acne'];d['appearanceLabels']['acne']='uncertain' if i in SMART_UNCERTAIN else 'positive'
   if i in SMART_UNCERTAIN:d['targetReasons']['acne']='NATIVE_ACTIVE_LESION_REVIEW_REQUIRED'
   if i in SMART_RIGHTS:d.update(rightsEligible=False,excludedReason='VISIBLE_THIRD_PARTY_NOTICE_PROVENANCE_UNRESOLVED')
   d['pimpleBoxesReviewed']=i not in SMART_UNCERTAIN
   d['completePimpleROI']=False
  if 500<=i<680:
   d['acceptedTargets']=[t for t in r['reviewTargets'] if t=='dark' and i in DC_DARK or t=='bags' and i in DC_BAGS]
   d['targetReasons']={t:'NORMAL_LID_DARKNESS_SHADOW_OR_NATIVE_DETAIL_UNCERTAIN' for t in r['reviewTargets'] if t not in d['acceptedTargets']}
   if i in {516,598,644}:d['naturalRGB']=False;d['colorCalibrationReason']='GRAYSCALE'
  if 680<=i<830:
   d['acceptedTargets']=['lines'];d['naturalRGB']=False
   d['targetReasons']={};d['calibrationReason']='EXPRESSION_POSE_OR_COLLAGE_NOT_NEUTRAL_APPEARANCE'
   d['componentRelationsResolved']=False;d['evaluationEligible']=False
   d['trainingGeometry']='individual crows_feet annotation native local crop, not full mosaic resize'
  if 830<=i<900:
   d['acceptedTargets']=[t for t in r['reviewTargets'] if t=='lines' and i in WRINKLE_LINES or t=='dark' and i in WRINKLE_DARK or t=='acne' and i in WRINKLE_ACNE]
   d['targetReasons']={t:'NON_OUTER_EYE_LINE_OR_SHADOW_MAKEUP_OR_ACTIVE_TARGET_UNCERTAIN' for t in r['reviewTargets'] if t not in d['acceptedTargets']}
  if 900<=i<960:
   d['acceptedTargets']=[t for t in r['reviewTargets'] if t=='tone' and i not in {921,954} or t=='dark' and i in {908,911,923,944,953} or t=='lines' and i in {901,910,937,943,949,955}]
   d['targetReasons']={t:'FRECKLES_SEPARATE_OR_NON_OUTER_EYE_LINE_OR_SHADOW_UNCERTAIN' for t in r['reviewTargets'] if t not in d['acceptedTargets']}
  if 960<=i<1040:
   d['acceptedTargets']=[t for t in r['reviewTargets'] if t=='dry' and i in DRY_VISIBLE or t=='acne' and i not in {962,984,988,1024,1028}]
   d['naturalRGB']=False;d['colorCalibrationReason']='PROCESSED_LOCAL_TEXTURE_ONLY';d['targetReasons']={t:'NO_VISIBLE_FLAKE_OR_ACTIVE_TARGET_UNCERTAIN' for t in r['reviewTargets'] if t not in d['acceptedTargets']}
  if 1040<=i<1140:
   d['acceptedTargets']=[t for t in r['reviewTargets'] if t=='dry' and i in DRY_VISIBLE or t=='acne' and i in CLEAN_ACNE or t=='oil' and i in CLEAN_OIL or t=='redness' and i in CLEAN_RED]
   d['targetReasons']={t:'CREAM_LIGHT_WRINKLES_PIGMENT_OR_ACTIVE_TARGET_UNCERTAIN' for t in r['reviewTargets'] if t not in d['acceptedTargets']}
  if 1140<=i<1190:
   d['acceptedTargets']=[t for t in r['reviewTargets'] if t=='tone' and i in ARNOLD_TONE or t=='bags' and i in ARNOLD_BAGS or t=='dark' and i in {1141,1144,1147,1150,1153,1156,1159,1171,1177,1180,1181,1186,1189}]
   d['targetReasons']={t:'FRECKLES_NORMAL_LID_SHADOW_OR_NATIVE_DETAIL_UNCERTAIN' for t in r['reviewTargets'] if t not in d['acceptedTargets']}
  if 1190<=i<1250:
   d['acceptedTargets']=[t for t in r['reviewTargets'] if t=='dry' and i in DRY_VISIBLE or t=='oil' and i in {1193,1214} or t=='bags' and i in {1198,1210,1234,1246}]
   d['supervision']='reviewed photo presence only; CSV zero is not pixel negative'
   d['targetReasons']={t:'CSV_PRESENCE_NOT_CONFIRMED_OR_COLOR_LIGHT_NORMAL_LID_CONFOUNDER' for t in r['reviewTargets'] if t not in d['acceptedTargets']}
  if 1250<=i<1310:
   d['acceptedTargets']=[t for t in r['reviewTargets'] if t=='acne' and i not in {1264,1266,1278,1298,1302} or t=='bags' and i in {1267,1275,1283}]
   d['targetReasons']={t:'ACTIVE_TARGET_OR_BAG_VS_DARK_NORMAL_LID_UNCERTAIN' for t in r['reviewTargets'] if t not in d['acceptedTargets']}
  if i>=500:
   for t in d['acceptedTargets']:d['appearanceLabels'][t]='positive'
  if i in EXTRA_NOTICES:d.update(rightsEligible=False,excludedReason='VISIBLE_THIRD_PARTY_NOTICE_PROVENANCE_UNRESOLVED')
  decisions.append(d)
 write('decisions.json',dict(candidatesSHA256=sha(source),rows=decisions,reviewedBoards=list(range(110)),engineeringLabels=True,expertLabels=False,independentFinal=False))
 print('Reviewed',len(decisions),'source photos, uncertainty and exclusions retained')

if __name__=='__main__':main()
