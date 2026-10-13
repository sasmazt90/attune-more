"""Record actual component-sheet inspection before any feature fit.

Explicit IDs are annotation provenance only, never inference rules.
"""
import collections,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/native-material-contour-20261013'
data=json.loads((OUT/'added-components-unreviewed.json').read_text('utf8'));sources=json.loads((OUT/'added-train-source-selection.json').read_text('utf8'))
# Complete component outlines and near/source context were inspected. Mixed
# material/skin, cosmetic film etiology, smooth shadows and tiny ambiguous dots
# remain UNKNOWN. Source F never assigns every proposal a material label.
M={12,13,14,15,16,17,18,19,38,39,41,42,43,52,183}
P={76,77,86,87,88,90,91,98,100,101,102,144,145,147,148,149,150,218,219}
R={89,99}
H={133,136,140,141,142,143,151,153,154,155,220,221,223,224,225,226,227}
excluded_sources={14:'possible near-copy of preserved validation C11; visible source attribution',16:'visible stock notice; no rights promotion',17:'visible stock notice; no rights promotion',19:'mixed garment/background and visible watermark'}
for row in data['rows']:
    i=row['index'];row['reviewed']=True;row['class']='material' if i in M else 'pore-texture' if i in P else 'reflection' if i in R else 'filament-ringing' if i in H else 'UNKNOWN'
    row['label']=1 if row['class']=='material' else 0 if row['class']!='UNKNOWN' else None
    row['reviewReason']='complete candidate outline on visible irregular surface material; etiology unconfirmed' if i in M else 'visible pore/dense skin texture without material edge' if i in P else 'smooth bright skin/gloss support without a lifted material edge' if i in R else 'visible strand/brow/beard support and adjacent ringing' if i in H else 'mixed/out-of-skin candidate, ambiguous cosmetic film or insufficient component detail'
    if row['sourceIndex'] in excluded_sources:row.update(label=None,**{'class':'UNKNOWN','reviewReason':excluded_sources[row['sourceIndex']]})
    if row['sourceIndex']==15:row['group']=sources[4]['group'];row['reviewReason']+='; same nose photo family as S4; TRAIN together'
data.update(reviewedBeforeFit=True,authority='engineering optical component/source inspection; not expert or full-pixel segmentation',sourceClassIsNotPixelTruth=True,oldLabelsUnchanged=True,
    reviewedPages=list(range(14)),fullComponentPages=list(range(4)),sourceExclusions=excluded_sources,counts=dict(collections.Counter(r['class'] for r in data['rows'])),includedGroups=len({r['group'] for r in data['rows'] if r['label'] is not None}))
path=OUT/'added-components-reviewed.json';assert not path.exists();path.write_text(json.dumps(data,indent=2),'utf8')
protocol=dict(baselineSHA='085a20395c009199c5924ed9683d3f98ce771bb1',proposalFrozen=True,proposal='native-independent-stable-region-ridge-v3',addedReviewSHA256=hashlib.sha256(path.read_bytes()).hexdigest(),encoder='original ImageNet EfficientNet-B0, frozen; no skin-type head',encoderThreads=1,batch=4,
    crops='source bbox+16 reference pixels close; max(3*bbox,64 reference pixels,48 native pixels) context; square pad114, RGB224, ImageNet mean/std; enlargement is encoder sampling only',
    featureChoice='two 1280-D frozen crop features + 12 scale-aware geometry/ring/pore features',fit='one TRAIN-only standardization + L2 logistic C=1,class-balanced,p>=.5,scipy L-BFGS-B; no PCA/validation fit/threshold search',
    baseline='one expanded-TRAIN eight-geometric-descriptor logistic under identical split; preserved prior ten-TRAIN head also reported',
    acceptance='preserve prior material object hits and >=3/8 familiar validation, improve over preserved gate 6/21; each reviewed negative within prior max(2*v3,v3+.25 percentage points); no meaningful false product map; no native/half domain collapse',outsideKnownLabels='UNKNOWN',independentFinalTest=False)
(OUT/'material-protocol.json').write_text(json.dumps(protocol,indent=2),'utf8');print(json.dumps(dict(counts=data['counts'],includedGroups=data['includedGroups'])))
