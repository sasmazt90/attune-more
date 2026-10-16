"""Freeze layer-1 review (before opening source labels or model points): one photo-free JSON with all points, coverage
records, mask hashes and declared deviations; prints its sha256."""
import json, hashlib, glob
from pathlib import Path
R = Path(__file__).parent; h = lambda b: hashlib.sha256(b).hexdigest()
stats = json.load(open(R / 'masks/stats.json')); photos = {}
for f in sorted(glob.glob(str(R / 'labels/*.json'))):
    L = json.load(open(f)); ph = L['photo']
    photos[ph] = dict(sha256=L['sha256'], faceWidthPx=L['faceWidthPx'], mergeRadiusPx=L['mergeRadiusPx'], coverage=L['coverage'],
                      mask=dict(file=f'masks/{ph}.png', sha256=h((R / f'masks/{ph}.png').read_bytes()), **stats[ph]),
                      points=[{k: p[k] for k in ('id', 'x', 'y', 'cat', 'note', 'tiles', 'n')} for p in L['points']], rawMarks=L['rawMarks'])
cnt = {}
for v in photos.values():
    for p in v['points']: cnt[p['cat']] = cnt.get(p['cat'], 0) + 1
doc = dict(name='acne-point-relabel-layer1', protocol='acne-point-relabel-protocol-1 (docs/acne-point-relabel-protocol-20261016.json)',
           nature='AI (assistant) engineering review of the same 28 DEV photos after earlier model results were known; NOT blind, NOT independent, NOT expert-verified',
           frozenBefore='source boxes and model points were not opened or drawn during this review',
           coordinates='source px of the pack image', counts=dict(photos=len(photos), byCategory=cnt,
           photosWithReviewedMask=sum(v['mask']['maskPx'] > 0 for v in photos.values()), reviewedMaskPx=sum(v['mask']['maskPx'] for v in photos.values())),
           declaredDeviations=[
               'collage (6dcf4d7ab398, 7b425c76a80f, eeb843cadf66) and close-up/padded (29069058884f) photos: landmark face oval does not describe the reviewed skin -> EMPTY reviewed mask (no negative claims); their TARGET points still count',
               'blurred/noisy photos d79fcee141ca and c1ae0b437492: all tiles not_reviewable -> EMPTY reviewed mask',
               'marks with sheet number 0 were read directly in source px from label-free full-image or zoom grids (zoom.py, same renderer, no labels/predictions) instead of the 2x2 tile sheets: used for the 640-px devext photos, cb5ca5ca9a33, 9334509b3ae3, b4ec4968102b, 5aa51f53f86c, c1ae0b437492',
               'self-check overlays (qa/) drew only my own layer-1 points; one stray UNCERTAIN mark on 933e40d730e0 placed on hair was removed before freezing'],
           photos=photos)
b = json.dumps(doc, indent=1, sort_keys=True).encode(); (R / 'layer1.json').write_bytes(b); print(h(b), cnt, doc['counts'])
