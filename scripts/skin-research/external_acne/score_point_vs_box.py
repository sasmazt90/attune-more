"""Score pre-filter / box filter / point filter on the unchanged common scope (108 targets, r = 0.03 fw) and Clear photos.
Old-path parity: box filter results must equal the committed numbers (Step0 71/96/48, Dewiin 75/45/3, tristan-gray 71/58/1,
carsten12 43/16/0) before the point path is reported."""
import json, sys
from pathlib import Path
import numpy as np, cv2
import relabel_compare as RC, common_scope_compare as CS

ROWS = ['step0', 'dewiin-anyacne/tiles', 'tristan-gray/tiles', 'carsten12/tiles']
EXPECT = {'step0': (71, 96, 48), 'dewiin-anyacne/tiles': (75, 45, 3), 'tristan-gray/tiles': (71, 58, 1), 'carsten12/tiles': (43, 16, 0)}
CL = ['false', 'duplicate', 'onUncertain', 'onOther', 'nearOutOfScopeTarget', 'unreviewedInOval', 'nonSkin', 'unreviewedPhoto']


def key(b): return tuple(round(float(v), 3) for v in b[:4])


def main(W, F):
    W = Path(W); FR = json.load(open(F)); P = FR['photos']
    L1 = json.load(open(W / 'acne-point-relabel-layer1-20261016.json'))['photos']; man = {m['sha256'][:12]: m for m in json.load(open(W / 'pack/manifest.json'))}
    lm = {}
    for f in ('lm-dev.jsonl', 'lm-devext.jsonl'):
        for l in open(W / f): r = json.loads(l); lm[r['sha256'][:12]] = r
    masks = {ph: cv2.imread(str(W / 'layer1/masks' / f'{ph}.png'), cv2.IMREAD_GRAYSCALE) > 0 for ph in L1}
    ovals = {ph: RC.oval_mask(lm[ph], lm[ph]['width'], lm[ph]['height']) for ph in L1}
    assert all(P[ph]['step0']['boxParity'] for ph in L1)
    stages = {}
    for k in ROWS:
        stages[k] = {'before': {ph: [b[:4] for b in P[ph][k]['before']] for ph in L1},
                     'box': {ph: [a['box'][:4] for a in P[ph][k]['boxAccepted']] for ph in L1},
                     'point': {ph: [a['box'][:4] for a in P[ph][k]['pointAccepted']] for ph in L1}}
    res = {k: {s: {ph: CS.classify(L1[ph], v[ph], masks[ph], ovals[ph], 0.03 * L1[ph]['faceWidthPx']) for ph in L1} for s, v in st.items()} for k, st in stages.items()}
    photos = sorted(L1); base = {(p, h) for p in photos for h in res['step0']['box'][p]['hitIds']}
    table = {}
    for k in ROWS:
        for s in ('before', 'box', 'point'):
            R = res[k][s]; ids = {(p, h) for p in photos for h in R[p]['hitIds']}
            table[f'{k} | {s}'] = dict(found=len(ids), of=sum(len(R[p]['inScope']) for p in photos), points=sum(len(R[p]['classes']) for p in photos),
                                       **{c: sum(R[p]['classes'].count(c) for p in photos) for c in CL},
                                       vsStep0Box=dict(gained=sorted(f'{a}#{b}' for a, b in ids - base), lost=sorted(f'{a}#{b}' for a, b in base - ids)),
                                       bySet={s2: sum(len(R[p]['hitIds']) for p in photos if man[p]['set'] == s2) for s2 in ('dev', 'devext')})
        t = table[f'{k} | box']; got = (t['found'], t['false'], t['duplicate'])
        assert got == EXPECT[k], ('OLD_PATH_PARITY', k, got, EXPECT[k])
    # box -> point changes: targets and per-prediction decision changes with old/new reasons
    changes = {}
    for k in ROWS:
        tb = {(p, h) for p in photos for h in res[k]['box'][p]['hitIds']}; tp = {(p, h) for p in photos for h in res[k]['point'][p]['hitIds']}
        dec = []
        for ph in photos:
            boxacc = {key(a['box']): a for a in P[ph][k]['boxAccepted']}; boxrej = {key(r['box']): r for r in P[ph][k]['boxRejected']}
            ptacc = {key(a['box']): a for a in P[ph][k]['pointAccepted']}; ptrej = {key(r['box']): r for r in P[ph][k]['pointRejected']}
            cls_b = dict(zip([key(a['box']) for a in P[ph][k]['boxAccepted']], res[k]['box'][ph]['classes']))
            cls_p = dict(zip([key(a['box']) for a in P[ph][k]['pointAccepted']], res[k]['point'][ph]['classes']))
            for b in P[ph][k]['before']:
                kb = key(b); ob = kb in boxacc; np_ = kb in ptacc
                if ob != np_ or (ob and np_ and boxacc[kb]['region'] != ptacc[kb]['region']):
                    dec.append(dict(photo=ph, box=[round(v, 1) for v in b[:4]], sidePx=round(max(b[2] - b[0], b[3] - b[1]), 1),
                                    old=('accept:' + boxacc[kb]['region'] + ':' + boxacc[kb]['reason']) if ob else 'reject:' + boxrej[kb]['reason'],
                                    new=('accept:' + ptacc[kb]['region'] + ':' + ptacc[kb]['reason']) if np_ else 'reject:' + ptrej[kb]['reason'],
                                    evalOld=cls_b.get(kb), evalNew=cls_p.get(kb)))
        changes[k] = dict(targetsGained=sorted(f'{a}#{b}' for a, b in tp - tb), targetsLost=sorted(f'{a}#{b}' for a, b in tb - tp), decisions=dec)
    clear = {}
    negs = [ph for ph, v in P.items() if v['kind'] == 'negative-photo']
    for k in ROWS[1:]:
        c = {}
        for s, src in (('before', 'before'), ('box', 'boxAccepted'), ('point', 'pointAccepted')):
            n = f = 0
            for ph in negs:
                m = cv2.imread(str(W / 'pack' / man[ph]['negMask']), cv2.IMREAD_GRAYSCALE) > 0
                bx = [x if s == 'before' else x['box'] for x in P[ph][k][src]]; n += len(bx)
                f += sum(1 for b in bx if RC.inside(m, ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)))
            c[s] = dict(points=n, false=f)
        clear[k] = dict(photos=len(negs), **c)
    return dict(table=table, changes=changes, clear=clear, inputs=FR['hashes'], pointFilterVersion=FR['pointFilterVersion'],
                perPhoto={k: {s: {p: dict(found=len(res[k][s][p]['hitIds']), false=res[k][s][p]['classes'].count('false')) for p in photos} for s in res[k]} for k in ROWS},
                perPhotoClasses=res)


if __name__ == '__main__':
    o = main(sys.argv[1], sys.argv[2]); json.dump(o, open(sys.argv[3], 'w'))
    for k, t in o['table'].items(): print(f"{k:34s} {t['found']}/{t['of']} F {t['false']} D {t['duplicate']} U {t['onUncertain']} nonSkin {t['nonSkin']} unrev {t['unreviewedInOval']}/{t['unreviewedPhoto']} +{len(t['vsStep0Box']['gained'])}/-{len(t['vsStep0Box']['lost'])} {t['bySet']}")
    for k, c in o['changes'].items():
        import collections
        print(k, 'gained', c['targetsGained'], 'lost', c['targetsLost'], len(c['decisions']), collections.Counter((d['old'].split(':')[0] + ':' + d['old'].split(':')[-1].split('(')[0], d['new'].split(':')[0] + ':' + d['new'].split(':')[-1].split('(')[0]) for d in c['decisions']).most_common(8))
    print(o['clear'])
