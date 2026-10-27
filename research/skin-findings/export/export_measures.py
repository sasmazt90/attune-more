"""Reference distribution for the flaking value: c_flake (bare-skin flake texture, regional_skin_v3.bare_skin_features)
of the FRONT photo regions labelled flaking in the training characters (same label rule as ecz_flake2.py; test persons
excluded). A seen region's value = midrank percentile in this list. Not validated against ratings."""
import json, re, sys, hashlib, numpy as np
S = '/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
st = {p['id']: p for p in json.load(open(f'{S}/gen/state.json'))['plans'] if p['status'] == 'approved'}
test = set(open(f'{S}/gen/pilot32.txt').read().split()) | set(open(f'{S}/gen/val28.txt').read().split())
ES = ('egzama', 'sedef'); APP = {'forehead': 'forehead', 'nose': 'nose', 'chin': 'chin', 'cheek_imgL': 'rightCheek', 'cheek_imgR': 'leftCheek'}
vals, seen = [], set()
for tag in ('_k5', '_k6', '_k8', '_k9', '_k10', '_k11'):
    I = {it['id']: it for it in json.load(open(f'{S}/rf/items{tag}.json'))}
    for r in json.load(open(f'{S}/rf/feats2{tag}.json')):
        if r['region'] not in APP: continue
        key = I[r['id']]['key']; m = re.match(r'(K-\d+)', key)
        if not m or m.group(1) not in st or m.group(1) in test or 'front' not in key: continue
        p = st[m.group(1)]; app = APP[r['region']]
        if (m.group(1), app) in seen: continue
        fl = (p['regions'].get(app) == 'dry' and p.get('intensity') != 'hafif') or (p['sens'] in ES and app in p['sensRegions'])
        if fl and r['f'].get('c_flake') is not None:
            vals.append(float(r['f']['c_flake'])); seen.add((m.group(1), app))
spec = dict(id='flaking', version='skin-findings-v2-measure-20261026', measure='c_flake', pose='FRONT',
            note='percentile of the region c_flake among flaking-positive FRONT regions of training characters; not validated against ratings',
            reference=sorted(vals), n=len(vals))
s = json.dumps(spec, separators=(',', ':')); open(sys.argv[1], 'w').write(s)
print(len(vals), np.percentile(vals, [10, 50, 90]).round(3), hashlib.sha256(s.encode()).hexdigest())
