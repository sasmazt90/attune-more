"""Product preflight for the fixed unused-test scope (no acne model is run): extract the kept photos from the archive (hash-checked,
local only), local MediaPipe landmarks with the product face_landmarker.task, frontend replay, product photo_input plan status.
Then pick ONE evaluated photo per evaluation group (lowest sha256 among replay-pass photos), as fixed in the protocol.
Usage: unused_test_preflight.py extract | landmarks | replay | status"""
import hashlib, json, subprocess, sys, zipfile
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent; CODE = HERE.parents[1]; TOGG = CODE.parent
sys.path[:0] = [str(HERE)]
import unused_test_select as S

O = CODE / 'audit-results/acne-unused-test'; PH = O / 'photos'
EXTRA = {'0034b55b2f58ea46d3d17a9d5ee630117c60171be4cbc13236e63fbbfb36a8c4': '6b suspected ORB copy (24 inliers to an excluded test row), excluded before any output'}
TASK = TOGG / 'attune-live-test/audit-results/skin-capabilities-20261008/scin/face_landmarker.task'


def kept():
    s = json.loads((O / 'scope.json').read_text()); return [t for t in s['kept'] if t['sha256'] not in EXTRA]


def main(stage):
    K = kept(); PH.mkdir(exist_ok=True); items = {t['sha256']: PH / (t['sha256'][:16] + '.jpg') for t in K}
    if stage == 'extract':
        z = zipfile.ZipFile(S.DATASETS / S.TEST)
        for t in K:
            raw = z.read(t['path']); assert hashlib.sha256(raw).hexdigest() == t['sha256']; items[t['sha256']].write_bytes(raw)
        print(len(K), 'extracted')
    elif stage == 'landmarks':
        (O / 'items.json').write_text(json.dumps([dict(sha256=s, path=str(p)) for s, p in items.items()]))
        subprocess.run([str(Path.home() / 'envmp/bin/python'), str(HERE / 'acne_landmarks_v2.py'), '--task', str(TASK), '--items', str(O / 'items.json'), '--out', str(O / 'landmarks.jsonl')], check=True)
    elif stage == 'replay':
        import eval_acne_v5_independent as v5; v5.setup(); import prepare_acne_data_v2 as prep
        prep.run_replay(CODE, O / 'landmarks.jsonl', items, TOGG, O / 'replay.jsonl')
    elif stage == 'status':
        import eval_acne_v5_independent as v5, cv2; v5.setup()
        rp = {}
        for l in open(O / 'replay.jsonl'): r = json.loads(l); rp[r['sha256']] = r
        st = {}
        for t in K:
            r = rp.get(t['sha256'])
            if r is None: st[t['sha256']] = dict(status='no-replay-row'); continue
            pl = v5.plan(cv2.imread(str(items[t['sha256']])), r)
            st[t['sha256']] = dict(status=pl['status'], tiles=len(pl['rects']), pose=r.get('matchedAngle'), reasons=r.get('reasons'))
        groups = {}
        for t in K: groups.setdefault(t['evalGroup'], []).append(t['sha256'])
        chosen = {}
        for g, ss in sorted(groups.items()):
            ok = sorted(s for s in ss if st[s]['status'].startswith('replay-pass'))
            chosen[g] = ok[0] if ok else None
        import collections
        rec = dict(rule='one evaluated photo per evaluation group: lowest sha256 among replay-pass photos (protocol)', extraExclusion=EXTRA, status=st,
                   statusCounts=dict(collections.Counter(v['status'] for v in st.values())), groups=len(groups), evaluated=sorted(s for s in chosen.values() if s),
                   groupsWithoutEligiblePhoto=sorted(g for g, s in chosen.items() if s is None),
                   evaluatedPose=dict(collections.Counter(st[s]['pose'] for s in chosen.values() if s)))
        (O / 'eligibility.json').write_text(json.dumps(rec, indent=1))
        print(json.dumps({k: v for k, v in rec.items() if k not in ('status', 'evaluated', 'groupsWithoutEligiblePhoto')}, indent=1), len(rec['evaluated']), 'evaluated')


if __name__ == '__main__': main(sys.argv[1])
