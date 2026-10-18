"""Build a public receipt from completed local evidence; never fit or activate."""
import base64
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'audit-results/dry-sag-component-followup-20261013'
BASELINE = '492949747554bd06ce06bb5ac2994949e54f4deb'
BUILD = 'S4upFfAkW8XUxxoM25UK5'


def read(path):
    return json.loads(path.read_text('utf8'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


protocol = read(OUT / 'protocol.json')
labels = read(OUT / 'object-labels.json')
features = read(OUT / 'component-features-reviewed.json')
model = read(OUT / 'component-gate-model.json')
fit = read(OUT / 'component-fit-receipt.json')
evaluation = read(OUT / 'component-evaluation-receipt.json')
selection = read(OUT / 'selection-receipt.json')
sources = read(OUT / 'unseen-face-selection.json')
review = read(OUT / 'unseen-face-visual-review.json')
side = read(OUT / 'side-runtime-receipt.json')
assert labels['protocolSHA256'] == model['protocolSHA256'] == evaluation['protocolSHA256'] == digest(OUT / 'protocol.json')
assert model['reviewedFeaturesSHA256'] == digest(OUT / 'component-features-reviewed.json')
assert fit['modelSHA256'] == evaluation['modelSHA256'] == digest(OUT / 'component-gate-model.json')
assert not model['accepted'] and not evaluation['productionActivated']

# Preserve the old fixed controls and their group boundaries. No person IDs exist;
# neither this check nor the small visual annotations imply subject independence.
controls = labels['controls']
assert len(controls) == 16
assert not {r['group'] for r in controls if r['split'] == 'train'} & {r['group'] for r in controls if r['split'] == 'validation'}
phashes = []
for row in controls:
    assert digest(Path(row['sourcePath'])) == row['sourceSHA256']
    gray = cv2.imread(row['sourcePath'], cv2.IMREAD_GRAYSCALE)
    dct = cv2.dct(cv2.resize(gray, (32, 32)).astype('float32'))[:8, :8].flatten()[1:]
    phashes.append(dct > np.median(dct))
distances = [int(np.sum(phashes[a] != phashes[b])) for a in range(8) for b in range(8, 16)]
assert features['reviewedBeforeFit'] and all(r['reviewed'] for r in features['rows'])
assert sum(r['label'] is None for r in features['rows']) == fit['unknownComponents']
assert fit['trainComponents'] == sum(r['label'] is not None and r['split'] == 'train' for r in features['rows'])

domains = []
for kind in sorted({r['kind'] for r in evaluation['rows']}):
    for scale in (1., .5):
        rows = [s for r in evaluation['rows'] if r['kind'] == kind for s in r['resolutionComparisons'] if s['sourceResolutionFactor'] == scale]
        objects = [o for s in rows for o in s['materialObjects'] if o['label'] == 'visible-material']
        domains.append(dict(kind=kind, sourceResolutionFactor=scale,
                            visibleMaterialObjects=len(objects),
                            objectHits={k: sum(o['fields'][k]['objectHit'] for o in objects) for k in ('v3OpticalFunction', 'unchangedNativeProposal', 'componentGate')},
                            reviewedNegativeActiveSourcePixels={k: sum(s['reviewedNegative'][k]['activeSourcePixels'] for s in rows) for k in ('v3OpticalFunction', 'unchangedNativeProposal', 'componentGate')}))

product = []
for row in evaluation['productComparisons']:
    assert all(row['unchangedOtherMethods'].values()) and row['sameRegionalDenominators']
    assert all(v['outsideValidMask'] == 0 and v['photoMatches'] for v in row['maps'].values())
    product.append(dict(sourcePayload=row['sourcePayload'], photoId=row['photoId'],
                        dryScores={k: dict(baseline=v['value'], isolatedCandidate=row['candidate'][k]['value']) for k, v in row['baseline'].items() if k.endswith(':dry')},
                        maps=row['maps'], unchangedOtherMethods=row['unchangedOtherMethods'], sameRegionalDenominators=row['sameRegionalDenominators']))

camera = []
for file in sorted((ROOT / 'output/playwright' / OUT.name).glob('*/camera-receipt.json')):
    row = read(file)
    assert row['buildId'] == BUILD and row['automaticScanCompleted'] and row['realMediaPipe']
    assert row['requestCount'] == row['responseCount'] == 1 and row['hostedCalls'] == 0
    assert row['historyBytesUnchanged'] and row['real200Accepted'] and not row['pageErrors']
    for views in (row['resultViews'], row['historyViews']):
        assert {v['view'] for v in views} == {'overview', 'forehead', 'nose', 'chin', 'periorbital', 'leftCheek', 'rightCheek'}
        assert all(v['photoId'] == row['capturePixelSHA256'] for v in views)
        assert all(label['matches'] for v in views for label in v['labels'])
    camera.append({**row, 'evidencePath': str(file.relative_to(ROOT)), 'receiptSHA256': digest(file)})

# Reproduce the existing expression decision on the actual captured landmarks.
payload = read(OUT / 'product/9bab7ab2/9bab7ab2-automatic-payload.json')
bgr = cv2.imdecode(np.frombuffer(base64.b64decode(payload['photo'].split(',')[1]), np.uint8), cv2.IMREAD_COLOR)
p = np.array([[v['x'] * bgr.shape[1], v['y'] * bgr.shape[0]] for v in payload['landmarks']])
axis = p[263] - p[33]; axis /= np.linalg.norm(axis)
vertical = np.array([-axis[1], axis[0]])
if vertical[1] < 0:
    vertical *= -1
mouth = max(float(np.linalg.norm(p[61] - p[291])), 1)
opening = float(np.linalg.norm(p[13] - p[14]) / mouth)
smile = float((((p[61] + p[291]) / 2 - (p[13] + p[14]) / 2) @ vertical) / mouth)
expression = dict(sourceSHA256=camera[0]['sourceSHA256'], mouthOpening=opening, verticalSmileRatio=smile,
                  existingThresholds=dict(maxMouthOpening=.10, minSmileRatio=-.07),
                  lowerFaceGateRejected=opening > .10 or smile < -.07,
                  explanation='Closed mouth is insufficient: the existing vertical mouth-corner smile ratio rejects this payload. No pose or expression gate changed.')
assert expression['lowerFaceGateRejected']

assert len(sources) == len(review['records']) == 96
assert len({r['group'] for r in sources}) == 96
for row in sources:
    assert digest(Path(row['absolutePath'])) == row['sha256']
assert selection['remainingUnreviewedGroups'] == 1994
# These are local audit artifacts, with no source photos or persistent user DBs.
artifacts = []
for file in sorted(OUT.glob('*.json')):
    artifacts.append(dict(path=str(file.relative_to(ROOT)), bytes=file.stat().st_size, sha256=digest(file)))
unchanged = subprocess.check_output(['git', 'diff', BASELINE, '--', 'services', 'apps', 'packages', 'shared', 'models', 'config'], cwd=ROOT)
assert not unchanged, 'Production source/config must remain on the preserved delivery'
receipt = dict(baselineSHA=BASELINE, preservedBUILD_ID=BUILD,
               scope='One component trial and 96 previously unseen face groups; old population reviews not repeated',
               protocol=protocol, protocolSHA256=digest(OUT / 'protocol.json'),
               objectLabels=labels, splitCheck=dict(groupDisjoint=True, fullSourcePHashMinimumCrossSplitDistance=min(distances),
                                                   pHashBits=63, knownPersonIdsAvailable=False, personIndependentClaim=False,
                                                   caution='Large pHash distance is not proof of different persons; fixed source/group split retained.'),
               reviewedProposalComponents=features['rows'], fit=fit,
               materialObjectChecks=evaluation['objects'], negativeSupport=evaluation['negativeSupport'],
               validation={**evaluation['validation'], 'positivePreservationVacuous': evaluation['validation']['v3HitObjects'] == evaluation['validation']['proposalHitObjects'] == 0},
               allMaterialObjects=evaluation['allMaterialObjects'], domainAndResolutionComparisons=domains,
               productComparisons=product, faceSelection=selection,
               selectedSourceRegistry=[{k:r[k] for k in ('censusIndex','sha256','group','path','rights','selectionRank')} for r in sources],
               visualReview=review, camera=camera, existingExpressionGate=expression, sideRuntime=side,
               sourceReviewStatusCounts=dict(Counter(r['status'] for r in review['records'])),
               productionSourceUnchanged=not unchanged, productionActivated=False,
               pixelDice=None, pixelPrecision=None, clinicalSeverity=False,
               decision=evaluation['decision'], artifactInventory=artifacts,
               remainingObstacles=['19/21 native material objects have no adequate unchanged proposal; a post-proposal gate cannot restore them.',
                                   'Validation has no object hit and only one positive proposal component. Reducing negative area alone is insufficient.',
                                   'No verified strong neutral chin target from the finite new source selection; 1994 groups remain unreviewed.',
                                   'Frozen corrected AG acne delivery not supplied; no AG integration performed.'])
target = ROOT / 'docs/dry-sag-component-evidence-20261013.json'
target.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', 'utf8')
print(json.dumps(dict(publicReceipt=str(target.relative_to(ROOT)), bytes=target.stat().st_size,
                      sha256=digest(target), validation=receipt['validation'], productionActivated=False)))
