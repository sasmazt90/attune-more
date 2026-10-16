"""Unused-photo test scope for the frozen v1 vs v3 verifier comparison (selection only; no acne model output is produced or read).

Pool: the sealed Skin care v5 test archive rows of plan-v3 (role TEST_CROSS_SOURCE). A row is EXCLUDED, with the reason recorded, if
  1. it was inferred before: its key is in acne-v3-20261015/eval-TEST_CROSS_SOURCE-step0.jsonl (Step0 tile inference, 2026-10-15);
  2. its file sha256 is referenced by any other JSON/JSONL record under audit-results, docs or claude-progress (any manifest, package,
     ledger, inference or review record), apart from the archive-wide index files (plan-v3.json, groups.json, hash/*.ndjson);
  3. its plan-v3 research group (exact / decoded / dHash<=6 + NCC>=.92 links over all 15 local archives) contains any row outside the
     Skin care v5 archive or any row excluded by 1-2;
  4. its 64-bit dHash or flip-dHash is within Hamming 10 of any row of any other local archive (33k rows) or of any excluded test row;
  5. its Roboflow family (original file stem) occurs in another archive or in an excluded test row (augmented / cropped exports);
  6. ORB + RANSAC finds a crop / collage / rescale copy (>= 25 homography inliers) in any photo file used by our research records
     (v4/v5/v6 manifests incl. the 941 cohort and Clear, DEV-EXT, review package) or in an excluded test row.
Remaining rows are kept; near-duplicates among kept rows (dHash<=10) are merged into one evaluation group.
Person identity is unknown for all photos (no person-independence claim). Step0's original pre-training data is unknown.
Usage: unused_test_select.py dhash | orb [max_seconds] | finish
"""
import collections, glob, hashlib, json, re, sys, time, zipfile
from pathlib import Path
import numpy as np, cv2

HERE = Path(__file__).resolve().parent; CODE = HERE.parents[1]; TOGG = CODE.parent; A = CODE / 'audit-results'
DATASETS = TOGG.parent / 'Datasets' if (TOGG.parent / 'Datasets').exists() else Path.home() / 'mnt/Datasets'
V3 = A / 'acne-v3-20261015'; OUT = A / 'acne-unused-test'; TEST = 'Skin care.v5i.coco.zip'
HEX = re.compile(r'\b[0-9a-f]{64}\b')
ham = lambda a, b: bin(a ^ b).count('1')


def remap(f):
    f = str(f); i = f.find('/mnt/TOGG/')
    if i >= 0: return str(Path.home() / 'mnt') + f[i + 4:]
    i = f.find('TOGG\\')
    if i >= 0: return str(Path.home() / 'mnt' / f[i:].replace('\\', '/'))
    return f


def rows_all():
    R = []
    for f in sorted((V3 / 'hash').glob('*.ndjson')):
        for l in open(f, encoding='utf8'):
            r = json.loads(l)
            if not r.get('decodeError'): R.append(r)
    return R


def dhash_img(img):
    g = cv2.resize(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (9, 8), interpolation=cv2.INTER_AREA).astype(int)
    return int(''.join('1' if b else '0' for b in (g[:, 1:] > g[:, :-1]).ravel()), 2)


def used_files():
    """Photo files used by our research records (for the ORB crop/collage check). Cached in used-files.json."""
    c = OUT / 'used-files.json'
    if c.exists(): return {s: Path(f) for s, f in json.loads(c.read_text()).items()}
    out = {}
    for f, key in (('acne-v4-data/manifest-v4.json', 'file'), ('acne-v5-data/manifest-v5.json', 'file'), ('acne-v6-data/manifest-v6.json', 'file')):
        base = A / Path(f).parent
        for p in json.loads((A / f).read_text())['photos']: out[p['sha256']] = base / p[key]
    for p in json.loads((A / 'acne-v6/devext/manifest.json').read_text())['photos']: out[p['sha256']] = Path(remap(p['file']))
    for p in json.loads((A / 'acne-v4-data/photoselection/manifest.json').read_text()): out[p['sha256']] = A / 'acne-v4-data/photoselection' / p['photo']
    for p in json.loads((A / 'acne-v4-data/clear/manifest.json').read_text()): out[p['sha256']] = A / 'acne-v4-data/clear' / p['photo']
    for f in glob.glob(str(A / 'acne-review-package-20261016/photos/*/*')):
        if f.lower().endswith(('.jpg', '.jpeg', '.png')): out[hashlib.sha256(Path(f).read_bytes()).hexdigest()] = Path(f)
    return {s: f for s, f in out.items() if f.exists()}


def stage_dhash():
    OUT.mkdir(exist_ok=True); plan = json.loads((V3 / 'plan-v3.json').read_text()); gid = json.loads((V3 / 'groups.json').read_text())['groupOf']
    R = rows_all(); key = lambda r: r['archive'] + '::' + r['path']; byk = {key(r): r for r in R}
    test = [i for i in plan['items'] if i['archive'] == TEST]; assert all(i['role'] == 'TEST_CROSS_SOURCE' for i in test)
    why = {}
    inferred = {json.loads(l)['key'] for l in open(V3 / 'eval-TEST_CROSS_SOURCE-step0.jsonl')}
    for i in test:
        if i['archive'] + '::' + i['path'] in inferred: why.setdefault(i['fileSha'], []).append('1 inferred before (Step0 eval-TEST_CROSS_SOURCE, 2026-10-15)')
    tsha = {i['fileSha'] for i in test}; refs = collections.defaultdict(set)
    skip = {V3 / 'plan-v3.json', V3 / 'groups.json', V3 / 'eval-TEST_CROSS_SOURCE-step0.jsonl'}
    roots = [A, CODE / 'docs', TOGG / 'claude-progress']
    for root in roots:
        for f in root.rglob('*'):
            if f.suffix not in ('.json', '.jsonl', '.ndjson') or f in skip or (V3 / 'hash') in f.parents or OUT in f.parents: continue
            try: s = f.read_text('utf8', errors='ignore')
            except Exception: continue
            for h in set(HEX.findall(s)) & tsha: refs[h].add(str(f.relative_to(TOGG)))
    for h, fs in refs.items(): why.setdefault(h, []).append('2 referenced in ' + '; '.join(sorted(fs)[:3]))
    used_test = set(why)
    members = collections.defaultdict(list)
    for r in R: members[gid.get(key(r), 'nogroup:' + key(r))].append(r)
    for i in test:
        g = i['group']; others = [m for m in members[g] if m['archive'] != TEST]; usedm = [m for m in members[g] if m['archive'] == TEST and m['fileSha'] in used_test and m['fileSha'] != i['fileSha']]
        if others: why.setdefault(i['fileSha'], []).append(f'3 group has {len(others)} row(s) in other archives')
        if usedm: why.setdefault(i['fileSha'], []).append('3 group has an excluded test row')
    other = [r for r in R if r['archive'] != TEST]; oth = np.array([r['dh'] for r in other], dtype=np.uint64); othf = np.array([r['dhf'] for r in other], dtype=np.uint64)
    ex = [byk[i['archive'] + '::' + i['path']] for i in test if i['fileSha'] in used_test]
    fam_other = {r['family'] for r in other}; fam_used = {r['family'] for r in ex}
    pc = lambda x: np.unpackbits(x.view(np.uint8).reshape(-1, 8), axis=1).sum(1)
    for i in test:
        r = byk[i['archive'] + '::' + i['path']]; d = np.uint64(r['dh'])
        dmin = int(min(pc(oth ^ d).min(), pc(othf ^ d).min()))
        if dmin <= 10: why.setdefault(i['fileSha'], []).append(f'4 dHash {dmin} to another archive row')
        if i['fileSha'] not in used_test and ex:
            de = min(min(ham(r['dh'], e['dh']), ham(r['dh'], e['dhf'])) for e in ex)
            if de <= 10: why.setdefault(i['fileSha'], []).append(f'4 dHash {de} to an excluded test row')
        if r['family'] in fam_other: why.setdefault(i['fileSha'], []).append('5 Roboflow family also in another archive')
        elif r['family'] in fam_used and i['fileSha'] not in used_test: why.setdefault(i['fileSha'], []).append('5 Roboflow family shared with an excluded test row')
    rec = dict(test=[dict(sha256=i['fileSha'], path=i['path'], group=i['group'], family=byk[i['archive'] + '::' + i['path']]['family'], w=i['w'], h=i['h']) for i in test],
               why={k: v for k, v in why.items()}, dhashOtherRows=len(other))
    (OUT / 'stage-dhash.json').write_text(json.dumps(rec, indent=1))
    print(len(test), 'test rows;', len(why), 'excluded so far;', collections.Counter(w[0][0] for w in why.values()))


def orb_desc(img, orb):
    s = 640 / max(img.shape[:2]); img = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) if s < 1 else img
    k, d = orb.detectAndCompute(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), None); return np.float32([p.pt for p in k]) if k else np.zeros((0, 2), np.float32), d


def stage_orb(max_seconds):
    st = json.loads((OUT / 'stage-dhash.json').read_text()); orb = cv2.ORB_create(500); t0 = time.monotonic()
    refc = OUT / 'orb-refs.npz'; cache = OUT / 'orb-cache'; cache.mkdir(exist_ok=True)
    if not refc.exists():
        refs = used_files(); z = zipfile.ZipFile(DATASETS / TEST)
        todo = [('file:' + s, f) for s, f in sorted(refs.items())] + [('usedtest:' + t['sha256'], t['path']) for t in st['test']
                if t['sha256'] in st['why'] and any(w.startswith(('1', '2')) for w in st['why'][t['sha256']])]
        for name, f in todo:
            c = cache / (hashlib.sha1(name.encode()).hexdigest() + '.npz')
            if c.exists(): continue
            if time.monotonic() - t0 > max_seconds: print('partial refs', len(list(cache.glob('*.npz'))), '/', len(todo)); return
            img = cv2.imread(str(f)) if name.startswith('file:') else cv2.imdecode(np.frombuffer(z.read(f), np.uint8), cv2.IMREAD_COLOR)
            p, d = orb_desc(img, orb) if img is not None else (np.zeros((0, 2), np.float32), None)
            np.savez(c, P=p, D=d if d is not None else np.zeros((0, 32), np.uint8))
        P, D, I, names = [], [], [], []
        for name, f in todo:
            c = np.load(cache / (hashlib.sha1(name.encode()).hexdigest() + '.npz'))
            if len(c['D']) == 0: continue
            P.append(c['P']); D.append(c['D']); I += [len(names)] * len(c['D']); names.append(name)
        tmp = OUT / 'orb-refs.tmp.npz'; np.savez_compressed(tmp, P=np.concatenate(P), D=np.concatenate(D), I=np.array(I), names=np.array(names)); tmp.replace(refc); print('refs', len(names)); return
    R = np.load(refc); P, D, I, names = R['P'], R['D'], R['I'], R['names']; bf = cv2.BFMatcher(cv2.NORM_HAMMING)
    res_f = OUT / 'orb-results.jsonl'; done = {json.loads(l)['sha256'] for l in open(res_f)} if res_f.exists() else set(); z = zipfile.ZipFile(DATASETS / TEST)
    with open(res_f, 'a') as fo:
        for t in st['test']:
            if t['sha256'] in done or t['sha256'] in st['why']: continue
            if time.monotonic() - t0 > max_seconds: print('partial'); return
            img = cv2.imdecode(np.frombuffer(z.read(t['path']), np.uint8), cv2.IMREAD_COLOR); p, d = orb_desc(img, orb); best = (0, None)
            if d is not None and len(d) >= 10:
                best2 = [[] for _ in range(len(d))]                                    # descriptor set > OpenCV single-train limit: chunked
                for c0 in range(0, len(D), 200000):
                    for qi, mm_ in enumerate(bf.knnMatch(d, D[c0:c0 + 200000], k=2)):
                        best2[qi] += [(x.distance, c0 + x.trainIdx) for x in mm_]
                m = []
                for qi, b in enumerate(best2):
                    b.sort()
                    if len(b) >= 2 and b[0][0] < .75 * b[1][0]: m.append(cv2.DMatch(qi, int(b[0][1]), 0, float(b[0][0])))
                cnt = collections.Counter(int(I[a.trainIdx]) for a in m)
                for ref, c in cnt.most_common(3):
                    if c < 15: break
                    mm = [a for a in m if I[a.trainIdx] == ref]; src = np.float32([p[a.queryIdx] for a in mm]); dst = np.float32([P[a.trainIdx] for a in mm])
                    H, inl = cv2.findHomography(src, dst, cv2.RANSAC, 5.0)
                    n = int(inl.sum()) if inl is not None else 0
                    if n > best[0]: best = (n, str(names[ref]))
            fo.write(json.dumps(dict(sha256=t['sha256'], inliers=best[0], ref=best[1])) + '\n'); fo.flush()
    print('complete')


def stage_finish():
    st = json.loads((OUT / 'stage-dhash.json').read_text()); why = dict(st['why'])
    orb = {json.loads(l)['sha256']: json.loads(l) for l in open(OUT / 'orb-results.jsonl')}
    for t in st['test']:
        o = orb.get(t['sha256'])
        if t['sha256'] in why: continue
        assert o is not None, 'ORB_INCOMPLETE'
        if o['inliers'] >= 25: why[t['sha256']] = [f"6 ORB/RANSAC copy ({o['inliers']} inliers) of {o['ref']}"]
    kept = [t for t in st['test'] if t['sha256'] not in why]
    R = {r['fileSha']: r for r in rows_all() if r['archive'] == TEST}; parent = {t['sha256']: t['sha256'] for t in kept}
    def find(a):
        while parent[a] != a: parent[a] = parent[parent[a]]; a = parent[a]
        return a
    for i, a in enumerate(kept):
        for b in kept[i + 1:]:
            ra, rb = R[a['sha256']], R[b['sha256']]
            if min(ham(ra['dh'], rb['dh']), ham(ra['dh'], rb['dhf'])) <= 10 or a['group'] == b['group'] or a['family'] == b['family']: parent[find(a['sha256'])] = find(b['sha256'])
    for t in kept: t['evalGroup'] = find(t['sha256'])[:12]; t['sourceAcneBoxes'] = len([x for x in R[t['sha256']]['anns'] if 'acne' in x['cls'].lower()])
    rec = dict(version='acne-unused-test-scope-1', rule=__doc__, pool=dict(archive=TEST, rows=len(st['test'])), excluded={s: w for s, w in why.items()},
               excludedByFirstReason=dict(collections.Counter(w[0][:1] for w in why.values())), kept=kept, keptGroups=len({t['evalGroup'] for t in kept}),
               personIdentity='unknown for every photo: no person-independence claim', step0PretrainingData='unknown (Step0 is a ready-made checkpoint): overlap with its pre-training data cannot be ruled out',
               sourceLabels='publisher labels are not used as truth; this scope is labelled anew before inference')
    (OUT / 'scope.json').write_text(json.dumps(rec, indent=1))
    print(json.dumps({k: v for k, v in rec.items() if k not in ('kept', 'excluded', 'rule')}, indent=1))


if __name__ == '__main__':
    {'dhash': lambda: stage_dhash(), 'orb': lambda: stage_orb(float(sys.argv[2]) if len(sys.argv) > 2 else 150), 'finish': lambda: stage_finish()}[sys.argv[1]]()
