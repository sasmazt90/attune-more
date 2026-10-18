"""Serialize explicitly inspected contact-sheet observations, never automatic truth.
Candidate-specific ROI annotations and quantitative acceptance are separate.
"""
import hashlib,json
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/dry-sag-source-census-20261013'
# One explicit observation for every displayed cell on all nine PUL sheets.
# F is visible flake-like material, NOT an expert diagnosis or complete pixel mask.
PUL_PAGES=[
 'U C F F C P P P F F U F F C F P F C C F P F F U',
 'C F U F F U P F F U F F F H F F F U F F O C P F',
 'C P F O C U P P O F P F P U F C P F F F U P U F',
 'F P C F P C P U O P F H C O F F F F P U F P P P',
 'P F F H F F P F F F F F F F F C F U C F F F P O',
 'F U F U U F P P P U F U U C H P P C C C U P U U',
 'F P P F P C U C P C F P P C C F P P U F P F F P',
 'F C P P P F P P P F F C P O F F F P U U F P C P',
 'C P P F P U P F P C O P P U C'
]
meaning={
 'F':dict(status='suitable-local-review',categories=['visible-flake-like-material','partial-face-closeup'],reason='Irregular white fragments or lifted edges are visible; cause and exact positive pixel extent remain unverified.'),
 'P':dict(status='rejected-as-flaking-positive',categories=['pores-reflections','partial-face-closeup'],reason='Visible dominant signal is pores, acne texture, wrinkles or reflections; a Dry/PUL source tag is not peeling truth. Only separately reviewed local ROI may be negative.'),
 'C':dict(status='ambiguous',categories=['cosmetic-film-or-peeling-suspected','partial-face-closeup'],reason='Broad rolling film, cream/application context or peel-like material is visible; cosmetic versus skin origin is not established, so it is excluded from biological-flake training truth.'),
 'H':dict(status='rejected-as-flaking-positive',categories=['hair-eyelash-accessory','partial-face-closeup'],reason='Hair/eye/eyebrow/accessory dominates; no clearly attributable local skin flake established at sheet resolution.'),
 'O':dict(status='rejected',categories=['non-face-or-composite','partial-closeup'],reason='Body/unknown-anatomy patch or composite/edited comparison is not an individual complete-face product acceptance input.'),
 'U':dict(status='ambiguous',categories=['uncertain','partial-face-closeup'],reason='Sheet shows fine grain, rash, compression or low-contrast material without enough visual evidence to distinguish flake from normal texture.'),
}
rows=json.loads((OUT/'pul-selection.json').read_text('utf8'));codes=[c for page in PUL_PAGES for c in page.split()];assert len(codes)==len(rows)
full_face={32,34,66,81,87,107,121,161,163,168,172,185,203}
near_copy_sets=[ [12,36],[31,71,100,103,110,173],[32,87,107],[4,24,77,137,157],[25,117,147],[89,97],[48,139],[95,118],[120,130],[63,114],[163,168],[98,183],[59,177],[66,206],[158,206],[197,205] ]
records=[]
for r,code in zip(rows,codes):
    path=Path(r['absolutePath']);assert hashlib.sha256(path.read_bytes()).hexdigest()==r['sha256']
    categories=list(meaning[code]['categories'])
    if r.get('naturalRGB') is False:categories.append('processed-CLAHE-provenance')
    if r['censusIndex'] in full_face:categories.append('photographic-face-visible; raw-natural-provenance-not-established')
    sheet=OUT/f"pul-sheet-{r['censusIndex']//24:02d}.jpg"
    records.append(dict(censusIndex=r['censusIndex'],sha256=r['sha256'],group=r['group'],source=r['source'],rights=r.get('rights'),
        reviewStatus=meaning[code]['status'],categories=categories,reason=meaning[code]['reason'],observationCode=code,
        sourceWidth=r['width'],sourceHeight=r['height'],sheet=str(sheet.relative_to(ROOT)),sheetSHA256=hashlib.sha256(sheet.read_bytes()).hexdigest(),
        reviewAuthority='engineering visual contact-sheet inspection; not expert clinical label',wholeFaceVisible=r['censusIndex'] in full_face,
        naturalCompleteFaceAccepted=False,negativeOutsideReviewedROI=False,
        visuallyRelatedCensusIndices=sorted({i for group in near_copy_sets if r['censusIndex'] in group for i in group if i!=r['censusIndex']})))
receipt=dict(records=records,reviewedGroups=len({r['group'] for r in records}),statusCounts=dict(Counter(r['reviewStatus'] for r in records)),
    unreviewedSelectedGroups=len(rows)-len(records),scope='All remaining PUL groups; alternatives and detailed ROI review are recorded separately',
    automaticQualityDidNotSupplyVisualLabels=True)
(OUT/'pul-visual-review.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),'utf8')
print(json.dumps({k:v for k,v in receipt.items() if k!='records'}))

# Explicit exceptions to mosaic/composite observations after viewing all 23
# contour sheets. Automatic pose/quality is recorded separately, not a label.
single={
 1:'E',14:'Q',16:'E',22:'QH',27:'E',30:'E',34:'N',36:'E',40:'EH',51:'E',54:'O',56:'S',57:'N',58:'E',85:'L',86:'OH',87:'E',88:'Q',95:'O',97:'QH',98:'LO',105:'N',111:'L',124:'E',126:'E',130:'E',134:'QH',136:'E',153:'Q',156:'N',185:'E',194:'E',201:'Q',204:'N',206:'E',208:'E',209:'E',211:'E',213:'E',221:'O',224:'E',225:'LH',226:'EQ',236:'NH',245:'OH',247:'E',264:'LH',273:'E',274:'E',275:'QH',278:'H',283:'E',287:'E',291:'E',303:'EO',306:'QH',313:'E',319:'LH',320:'QH',321:'HU',323:'E',326:'E',327:'E',340:'L',342:'L',345:'NQ',355:'E',360:'E',363:'E',365:'E',366:'E',367:'E',368:'O',371:'O',382:'E',396:'E',400:'U',402:'N',407:'QH',417:'E',420:'EQ',437:'E',438:'O',440:'L',444:'E',445:'E',448:'Q',450:'E',451:'E',456:'EQ',461:'E',462:'UQ',468:'L',477:'U',487:'E',491:'E',513:'L',521:'QH',529:'E',533:'E',534:'LQ',535:'NQ',536:'E',537:'E',541:'E'
}
descriptions=dict(M='Mosaic/cut-and-paste collage and/or black occlusions; not one natural camera photograph.',
 E='Visible smile, speech or open-mouth expression; excluded from neutral sag-positive truth even if SDK pose passes.',
 Q='Single photograph but native pose, frame, ROI or capture conditions are incompatible; no override.',
 H='Facial hair, eyewear or dense hair can confound the observed lower-face boundary/fold.',
 O='Hand, sleeve, cigarette or object occludes/deforms the lower-face target.',
 S='Strong directional illumination; contour/fold versus shadow is not established.',
 N='Single neutral-looking photo with visible lower face; local fold truth is not established at sheet resolution.',
 L='Single photograph with visible lower-cheek/jaw fold or contour support; engineering candidate for full-resolution inspection, not expert sag truth.',
 U='Expression/target or landmark interpretation remains uncertain; not positive truth.')
rows=json.loads((OUT/'contour-selection.json').read_text('utf8'));poses=json.loads((OUT/'contour-pose-census.json').read_text('utf8'))['rows'];reviews=[]
assert len(rows)==len(poses)==543
for r,p in zip(rows,poses):
    index=r['censusIndex'];code=single.get(index,'M');sheet=OUT/f'contour-sheet-{index//24:02d}.jpg'
    status='appropriate-for-detailed-review' if 'L' in code and len(code)==1 or code=='N' else 'ambiguous' if 'U' in code or 'L' in code else 'rejected-for-neutral-product-acceptance'
    reviews.append(dict(index=index,sha256=r['sha256'],group=r['group'],source=r['source'],rights=r.get('rights'),reviewStatus=status,
        observationCode=code,reasons=[descriptions[c] for c in code],singlePhotograph=code!='M',
        sheet=str(sheet.relative_to(ROOT)),sheetSHA256=hashlib.sha256(sheet.read_bytes()).hexdigest(),
        actualPoseQuality=p,expertLabel=False,acceptedSagPositive=False))
result=dict(records=reviews,reviewedGroups=len({r['group'] for r in reviews}),statusCounts=dict(Counter(r['reviewStatus'] for r in reviews)),
    remainingSelectedGroups=len(rows)-len(reviews),otherFaceGroupsWithoutTheseContourLabelsUnreviewed=json.loads((OUT/'census.json').read_text('utf8'))['contour']['otherFaceGroupsOutsideThisLabeledScope'],
    singlePhotographCandidates=sum(r['singlePhotograph'] for r in reviews),qualityDidNotSupplyVisualLabel=True)
(OUT/'contour-visual-review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8')
print(json.dumps({k:v for k,v in result.items() if k!='records'}))

# All fourteen weak Dry-Skin sheets were inspected. Unknown is an explicit
# observation, not an automatic healthy-negative label.
weak_groups={
 'F':{8,10,38,42,47,53,77,83,88,109,113,114,125,130,146,180,195,198,199,224,225,229,231,237,248,272,296,311},
 'C':{0,13,15,26,52,58,61,69,85,91,103,110,120,124,151,154,156,159,177,178,192,197,203,206,207,215,218,223,226,243,251,265,281,289,291,306,307,316},
 'O':{2,36,40,75,78,82,97,112,131,165,190,193,213,214,216,233,235,242,249,250,256,258,271,283,284,290,310,312,318,320,327},
 'D':{6,11,17,19,31,34,41,44,49,57,74,115,117,132,133,139,142,150,160,166,174,196,200,211,221,255,257,309,315},
 'P':{3,4,5,7,9,12,14,16,18,20,21,22,23,24,25,28,29,30,32,33,35,37,39,43,45,46,48,50,51,54,55,56,59,60,62,63,64,65,66,67,68,70,71,72,73,76,79,80,81,84,86,87,89,90,92,93,94,95,96,98,99,100,101,102,104,105,106,107,108,111,116,118,119,121,122,123,126,127,128,129,134,135,136,137,138,140,143,144,145,147,148,149,152,153,155,157,158,161,162,163,164,167,168,169,170,171,172,173,175,176,179,181,182,183,184,185,186,187,188,189,191,194,201,202,204,205,208,209,210,212,217,219,220,222,227,228,230,232,234,236,238,239,240,241,244,245,246,247,252,253,254,259,260,261,262,263,264,266,267,268,269,270,273,274,275,276,277,278,279,280,282,285,286,287,288,292,293,294,295,297,298,299,300,301,302,303,304,305,308,313,314,317,319,321,322,323,324,325,326,328}
}
codes={}
for code,indices in weak_groups.items():
    for index in indices:
        assert index not in codes,(index,code,codes.get(index));codes[index]=code
rows=json.loads((OUT/'dry-label-selection.json').read_text('utf8'));assert len(rows)==329
meaning['D']=dict(status='rejected',categories=['edited-illustration-magnifier-collage'],reason='Crack overlays, marketing panels or composites are not actual skin-flake pixel truth.')
reviews=[]
for r in rows:
    index=r['censusIndex'];code=codes.get(index,'U');entry=meaning[code];sheet=OUT/f'dry-label-sheet-{index//24:02d}.jpg'
    reviews.append(dict(index=index,sha256=r['sha256'],group=r['group'],source=r['source'],rights=r.get('rights'),sourceWidth=r['width'],sourceHeight=r['height'],
        observationCode=code,reviewStatus=entry['status'],categories=entry['categories'],reason=entry['reason'],
        sheet=str(sheet.relative_to(ROOT)),sheetSHA256=hashlib.sha256(sheet.read_bytes()).hexdigest(),
        expertLabel=False,sourceTagIsNotFlakingTruth=True,negativeOutsideReviewedROI=False))
receipt=dict(records=reviews,reviewedGroups=len({r['group'] for r in reviews}),statusCounts=dict(Counter(r['reviewStatus'] for r in reviews)),unreviewedSelectedGroups=len(rows)-len(reviews))
(OUT/'dry-label-visual-review.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),'utf8')
print(json.dumps({k:v for k,v in receipt.items() if k!='records'}))
