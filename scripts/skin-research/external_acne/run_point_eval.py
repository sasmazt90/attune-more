import json, hashlib, sys
from pathlib import Path
import cv2
import point_eval as P

A = Path('.'); man = json.loads((A / 'pack/manifest.json').read_text())
ext = json.loads((A / 'external-results.json').read_text())
read_mask = lambda f: cv2.imread(str(f), cv2.IMREAD_GRAYSCALE) > 0
LIC = {'step0': 'CDC production model (internal)', 'tinny-robot': 'card Apache-2.0; Ultralytics-trained -> AGPL-3.0 (checkpoint pre-dates license field)',
       'drpauloreis-onnx': 'tag Apache-2.0; ONNX metadata AGPL-3.0', 'hilmizr-m': 'none stated; Ultralytics-trained (AGPL-3.0)', 'hilmizr-s': 'none stated; Ultralytics-trained (AGPL-3.0); = Jasnk (Apache tag), counted once',
       'khaminh-11s': 'none stated; checkpoint AGPL-3.0', 'carsten12': 'none stated; checkpoint AGPL-3.0', 'tristan-gray': 'tag WTFPL; checkpoint AGPL-3.0',
       'aldinnasrun-kerascv': 'tag Apache-2.0; KerasCV (Apache-2.0); data unstated', 'dewiin-acne': 'repo MIT; checkpoint AGPL-3.0', 'dewiin-anyacne': 'repo MIT; checkpoint AGPL-3.0',
       'unzelanoor': 'none (all rights reserved); checkpoint AGPL-3.0', 'unzelanoor-app': 'none (all rights reserved); checkpoint AGPL-3.0'}

# Step0 rows from the unchanged product chain (stored), restricted to the pack photos
step0 = {}
for f in ('step0/dev.jsonl', 'step0/devext.jsonl'):
    for l in open(f):
        r = json.loads(l); step0[r['sha256']] = dict(sha=r['sha256'], final=r['final'], sec=r.get('totalSec', 0.))
entries = {'step0/product-chain': [step0[i['sha256']] for i in man]}
for k, v in ext.items(): entries[k] = v['rows']

out, checks = {}, {}
for k, rows in sorted(entries.items()):
    S, pt, roi_pp, clear_pp, gained = P.evaluate(rows, man, A / 'pack', read_mask)
    ref = (dict(hit50=17, hit30=25) if k.startswith('step0') else dict(hit50=ext[k]['score']['hit50'], hit30=ext[k]['score']['hit30']))
    checks[k] = dict(storedIoU50=ref['hit50'], recomputedIoU50=S['iou50'], storedIoU30=ref['hit30'], recomputedIoU30=S['iou30'], equal=ref['hit50'] == S['iou50'] and ref['hit30'] == S['iou30'])
    out[k] = dict(model=k.split('/')[0], mode=k.split('/')[1], license=LIC[k.split('/')[0]], summary=S, perTarget=pt, roiPerPhoto=roi_pp, clearPerPhoto=clear_pp, pointHitButIoU50Miss=gained)
    print(f"{k:28s} pt {S['point']:3d}/{S['targets']} sm {S['smallPoint']:2d}/{S['small']} md {S['mediumPoint']:3d}/{S['medium']} t25 {S['tol25']:3d} t50 {S['tol50']:3d} "
          f"iou {S['iou50']:2d}/{S['iou30']:2d} roiFP {S['roiFP']} ({S['roiFPperPhoto']}) clrFP {S['clearFP']} ({S['clearFPperPhoto']}) unk {S['unknown']:4d} dup {S['duplicates']:3d} conf {S['conflicts']} gain {len(gained):2d} t {S['medianSec']}", flush=True)
bad = {k: v for k, v in checks.items() if not v['equal']}
print('IoU parity:', 'all equal' if not bad else bad)
h = lambda f: hashlib.sha256(Path(f).read_bytes()).hexdigest()
json.dump(dict(protocolSHA256=h('/mnt/user-data/outputs/ext/acne-point-eval-protocol-20261016.json'), inputs=dict(manifest=h('pack/manifest.json'), externalResults=h('external-results.json'),
          step0Dev=h('step0/dev.jsonl'), step0Devext=h('step0/devext.jsonl')), iouParity=checks, results=out), open('point-eval-results.json', 'w'))
