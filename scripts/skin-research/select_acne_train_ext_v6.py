"""Acne v6 limited TRAIN extension: choose at most 100 more v4-TRAIN positive photos for assistant engineering review.

Pool = manifest-v4 photos with kind positive-photo and role TRAIN (v3 role TRAIN only, acne cohort; never the 941 UNKNOWN cohort),
minus the 65-photo v5 core, minus every photo (and research group) listed in the v3 product evaluation file (Scope B, controls, held-out 20,
reviewed negatives, and - conservatively - its 40 TRAIN-probe rows), minus every RESERVED_V2_EVAL / TEST / VALIDATION group. Product suitability is decided ONLY from pixels and the
product contract (decode limits, MediaPipe, replayed gates with eyewear UNKNOWN, product tile budget) - no model output is read.
Selection is deterministic and model-free: round-robin over (source archive, face-brightness tercile) strata; inside a stratum photos
with explicit confounder boxes (mole/freckle/pigmentation/pores/dark spot) and small source boxes come first, then SHA-256 order.

Phases: pool | landmarks | replay | select
"""
import argparse, collections, hashlib, json, subprocess, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent; CODE = HERE.parents[1]; sys.path[:0] = [str(HERE)]
import eval_acne_v5_independent as v5
A = CODE / 'audit-results'; OUT = A / 'acne-v6/trainext'; D4 = A / 'acne-v4-data'


def excluded():
    plan = json.loads((A / 'acne-v3-20261015/plan-v3.json').read_text()); role, grp = {}, {}
    for i in plan['items']: role.setdefault(i['fileSha'], set()).add(i['role']); grp[i['fileSha']] = i['group']
    failed = {json.loads(l)['sha256'] for l in (A / 'acne-v3-20261015/evaluation-v3prod-step0.jsonl').read_text().splitlines()}
    bad_groups = {grp[s] for s in failed if s in grp} | {grp[s] for s, r in role.items() if r - {'TRAIN'}}
    core = {p['sha256'] for p in json.loads((A / 'acne-v5-data/manifest-v5.json').read_text())['photos'] if p['kind'] == 'positive-photo'}
    other941 = {r['sha256'] for r in json.loads((D4 / 'photoselection/manifest.json').read_text()) if r['cohort'] != 'acne'}
    return role, grp, failed, bad_groups, core, other941


def pool():
    role, grp, failed, bad_groups, core, other941 = excluded()
    m = json.loads((D4 / 'manifest-v4.json').read_text()); P = []; why = collections.Counter()
    for p in m['photos']:
        if p['kind'] != 'positive-photo' or p['role'] != 'TRAIN': continue
        s = p['sha256']
        if s in core: why['core'] += 1; continue
        if s in failed: why['failed-product-eval photo'] += 1; continue
        if s in other941: why['941 cohort'] += 1; continue
        if role.get(s) != {'TRAIN'}: why['v3 role not TRAIN-only'] += 1; continue
        if grp.get(s) in bad_groups: why['group shared with eval/reserved/validation'] += 1; continue
        P.append(p)
    return P, why


def main(phase):
    OUT.mkdir(parents=True, exist_ok=True); P, why = pool()
    old = {json.loads(l)['sha256']: json.loads(l) for l in (A / 'acne-data-v2-20261015/replay.jsonl').read_text().splitlines()}
    if phase == 'pool':
        print(len(P), dict(why)); return
    if phase == 'landmarks':
        items = [dict(sha256=p['sha256'], path=str(D4 / p['file'])) for p in P if p['sha256'] not in old]
        (OUT / 'items.json').write_text(json.dumps(items))
        subprocess.run([str(Path.home() / 'envmp/bin/python'), str(HERE / 'acne_landmarks_v2.py'), '--task', str(v5.TASK), '--items', str(OUT / 'items.json'),
                        '--out', str(OUT / 'landmarks.jsonl')], check=True); return
    if phase == 'replay':
        v5.setup(); import prepare_acne_data_v2 as prep
        prep.run_replay(CODE, OUT / 'landmarks.jsonl', {p['sha256']: D4 / p['file'] for p in P}, v5.TOGG, OUT / 'replay.jsonl'); return
    if phase == 'select':
        v5.setup(); import cv2
        new = {json.loads(l)['sha256']: json.loads(l) for l in (OUT / 'replay.jsonl').read_text().splitlines()} if (OUT / 'replay.jsonl').exists() else {}
        rows = []; status = collections.Counter()
        for p in P:
            s = p['sha256']; rp = new.get(s) or old.get(s); src = 'v6-trainext' if s in new else 'acne-data-v2'
            if rp is None: status['no replay'] += 1; continue
            bgr = cv2.imread(str(D4 / p['file'])); pl = v5.plan(bgr, rp)
            ok = pl['status'].startswith('replay-pass') and bool(rp.get('snapshot')); status[pl['status'] + ('' if rp.get('snapshot') or not pl['rects'] else ' / no-snapshot')] += 1
            if not ok: continue
            pts = np.array([[q['x'] * bgr.shape[1], q['y'] * bgr.shape[0]] for q in rp['landmarks']], np.int32); hull = cv2.convexHull(pts)
            fm = np.zeros(bgr.shape[:2], np.uint8); cv2.fillConvexPoly(fm, hull, 255); L = float(np.median(cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)[..., 0][fm > 0]))
            sides = [max(b['box'][2] - b['box'][0], b['box'][3] - b['box'][1]) for b in p['positive']]
            rows.append(dict(sha256=s, file=str(D4 / p['file']), replaySource=src, sourceArchive=p['sourceArchive'], researchGroup=p['researchGroup'], faceL=L,
                             confounders=len(p.get('negativeBoxes', [])), smallBoxes=sum(1 for x in sides if x < 16), sourcePositive=len(p['positive'])))
        if rows:
            t = np.quantile([r['faceL'] for r in rows], [1 / 3, 2 / 3])
            for r in rows: r['brightness'] = int(r['faceL'] > t[0]) + int(r['faceL'] > t[1])
        strata = collections.defaultdict(list)
        for r in rows: strata[(r['sourceArchive'], r['brightness'])].append(r)
        for k in strata: strata[k].sort(key=lambda r: (-(r['confounders'] > 0), -(r['smallBoxes'] > 0), r['sha256']))
        pick, seen_groups = [], set(); keys = sorted(strata)
        while len(pick) < 100 and any(strata[k] for k in keys):
            for k in keys:
                while strata[k]:
                    r = strata[k].pop(0)
                    if r['researchGroup'] in seen_groups: continue          # one photo per research group: wider coverage
                    pick.append(r); seen_groups.add(r['researchGroup']); break
                if len(pick) >= 100: break
        res = dict(rule=__doc__, poolExclusions=dict(why), poolSize=len(P), productStatus=dict(status), productSuitable=len(rows), selected=pick,
                   bySource=dict(collections.Counter(r['sourceArchive'] for r in pick)), byBrightness=dict(collections.Counter(r['brightness'] for r in pick)))
        (OUT / 'selection.json').write_text(json.dumps(res, indent=1))
        print(json.dumps({k: v for k, v in res.items() if k not in ('selected', 'rule')}))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('phase'); main(ap.parse_args().phase)
