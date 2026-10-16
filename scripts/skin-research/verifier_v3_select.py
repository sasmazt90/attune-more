"""Verifier v3, step 1: list every TRAIN candidate that is a v1 positive and has NOT been reviewed in v2 (expected 373), fixed BEFORE
review. No sampling: the whole remainder is reviewed. Review ids S001.. in sha256(seed|v3review|photo|idx) order (blind sheets).
Writes audit-results/acne-verifier-v3/review-list.json and docs/acne-verifier-v3-review-list-20261016.json (photo-free)."""
import hashlib, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent; CODE = HERE.parents[1]
sys.path[:0] = [str(HERE)]
import verifier_v2_select as S2

SEED = 20261016; H = lambda *a: hashlib.sha256('|'.join(map(str, a)).encode()).hexdigest()


def main():
    v1 = json.loads((CODE / 'audit-results/acne-verifier/labels.json').read_text())['rows']
    rl2 = json.loads((CODE / 'audit-results/acne-verifier-v2/review-list.json').read_text())['items']
    done = {(i['photo'], i['idx']) for i in rl2}; at, tert = S2.photo_attrs()
    todo = [r for r in v1 if r['label'] == 1 and (r['photo'], r['idx']) not in done]
    assert len(todo) == 433 - sum(1 for i in rl2 if i['pool'] == 'pos') == 373, len(todo)
    items = [dict(photo=r['photo'], idx=r['idx'], box=r['box'], score=r['score'], v1Label=r['label'], v1Reason=r['reason'],
                  pose=at[r['photo']]['pose'], fwPx=at[r['photo']]['fwPx'], scaleTertile=at[r['photo']]['scaleTertile']) for r in todo]
    items.sort(key=lambda r: H(SEED, 'v3review', r['photo'], r['idx']))
    for i, r in enumerate(items): r['rid'] = f'S{i + 1:03d}'
    rec = dict(seed=SEED, rule='all v1 positives (within r of a kept box centre) not in the v2 review list', n=len(items), photos=len({r['photo'] for r in items}),
               byPose={p: sum(1 for r in items if r['pose'] == p) for p in ('FRONT', 'LEFT', 'RIGHT')}, byScaleTertile={t: sum(1 for r in items if r['scaleTertile'] == t) for t in range(3)},
               items=items, v2ReviewListSha256=hashlib.sha256((CODE / 'audit-results/acne-verifier-v2/review-list.json').read_bytes()).hexdigest())
    o = CODE / 'audit-results/acne-verifier-v3'; o.mkdir(exist_ok=True); s = json.dumps(rec, indent=1)
    (o / 'review-list.json').write_text(s); (CODE / 'docs/acne-verifier-v3-review-list-20261016.json').write_text(s)
    print({k: v for k, v in rec.items() if k != 'items'})


if __name__ == '__main__': main()
