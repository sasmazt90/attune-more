"""Skin finding labels: placement rules, and that selection only ever draws real data on the right photo."""
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
BOOTSTRAP = "require('./tests/unit/ts_loader.js');\n"

SCRIPT = r"""
const assert = require('assert');
const { placeCallouts } = require('./apps/vehicle-app/src/utils/skinCalloutLayout.ts');
const { sourceBoundCallouts, findingLayers, findingSnapshot, unlocatedFindings } = require('./apps/vehicle-app/src/utils/skinCalloutModel.ts');
const { FINDING_DEFS } = require('./apps/vehicle-app/src/utils/skinFindings.ts');

const overlaps = (a, b) => a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;
const item = (key, ax, ay, w = 110, h = 48) => ({ key, ax, ay, w, h, visualH: 26 });
const face = { x: 70, y: 60, w: 200, h: 280 }, keepOut = [{ x: 100, y: 130, w: 60, h: 30 }, { x: 180, y: 130, w: 60, h: 30 }, { x: 140, y: 150, w: 60, h: 80 }, { x: 125, y: 250, w: 90, h: 40 }];

// Labels stay in the photo, apart from each other, with short lines, whatever the label width.
for (const [W, H] of [[345, 392], [300, 330], [460, 533]]) {
  for (const width of [70, 110, 150, 190]) {
    const items = [item('a', 120, 100, width), item('b', 230, 200, width), item('c', 100, 240, width), item('d', 200, 110, width)];
    const { placed, fits } = placeCallouts(items, { width: W, height: H, keepOut, face });
    assert.ok(fits, `four labels fit ${W}x${H} at ${width}`);
    assert.equal(placed.length, 4);
    for (const p of placed) {
      assert.ok(p.x >= 6 && p.y >= 6 && p.x + p.w <= W - 6 && p.y + p.h <= H - 6, 'inside the photo');
      assert.ok(p.length <= Math.max(96, .4 * Math.max(W, H)), 'short line');
      const own = items.find(i => i.key === p.key);
      assert.deepEqual([p.ax, p.ay], [own.ax, own.ay], 'the anchor never moves');
      assert.ok(!(own.ax >= p.x && own.ax <= p.x + p.w && own.ay >= p.y && own.ay <= p.y + p.h), 'a label never covers its own spot');
      assert.ok(/^M[\d.]+ [\d.]+Q[\d.]+ [\d.]+ [\d.]+ [\d.]+$/.test(p.path), 'one gentle curve');
    }
    for (let i = 0; i < placed.length; i++) for (let j = i + 1; j < placed.length; j++) assert.ok(!overlaps(placed[i], placed[j]), 'labels never overlap');
  }
}
// The same input gives the same layout.
const twice = [item('a', 120, 100), item('b', 230, 200)];
assert.deepEqual(placeCallouts(twice, { width: 345, height: 392, keepOut, face }), placeCallouts(twice, { width: 345, height: 392, keepOut, face }));
// A wider, translated label is placed again without leaving the photo.
const german = placeCallouts([item('a', 300, 200, 180)], { width: 345, height: 392 });
assert.ok(german.fits && german.placed[0].x + german.placed[0].w <= 339);
// A label wider than the photo cannot sit on it.
assert.equal(placeCallouts([item('a', 50, 50, 300)], { width: 200, height: 300 }).fits, false);
// Too many labels on a small photo go to the list under it, rather than crowd the face or use long lines.
const crowd = Array.from({ length: 12 }, (_, i) => item('k' + i, 60 + (i % 4) * 25, 50 + (i % 3) * 30, 150));
assert.equal(placeCallouts(crowd, { width: 230, height: 260, keepOut, face }).fits, false);
assert.deepEqual(placeCallouts([], { width: 300, height: 300 }), { placed: [], fits: true });

// ------------------------------------------------------------- real-data rules
const id = pose => pose.toLowerCase().padEnd(64, 'a');
const landmarks = Array.from({ length: 478 }, (_, i) => ({ x: .3 + (i % 40) * .01, y: .2 + (i % 50) * .01 }));
const frame = angle => ({ angle, photoId: id(angle), width: 1000, height: 800, landmarks, dataUrl: 'data:image/png;base64,', meshes: {}, rois: [], exclusions: [], faceContour: [], contours: {}, crop: { x: 0, y: 0, width: 1000, height: 800 } });
const frames = { FRONT: frame('FRONT'), RIGHT: frame('RIGHT'), LEFT: frame('LEFT') };
const captures = Object.fromEntries(Object.keys(frames).map(a => [a, { captureId: id(a), pose: a, sourceWidth: 1000, sourceHeight: 800 }]));
const findings = [
  { id: 'darkCircles', region: 'periorbital', status: 'seen', pose: 'FRONT', severity: 53 },
  { id: 'acne', region: 'forehead', status: 'seen', pose: 'LEFT', count: 2, countPose: 'FRONT', markers: [{ x: 300, y: 200, pose: 'FRONT', type: 'papule' }, { x: 340, y: 210, pose: 'FRONT' }] },
  { id: 'acne', region: 'rightCheek', status: 'seen', pose: 'LEFT', count: 1, countPose: 'LEFT', markers: [{ x: 500, y: 400, pose: 'LEFT', type: 'papule' }] },
  { id: 'redness', region: 'leftCheek', status: 'seen', pose: 'RIGHT', areaPct: 9 },
  { id: 'spots', region: 'chin', status: 'seen', pose: 'FRONT', count: 1, countAtLeast: true },
  { id: 'mole', region: 'chin', status: 'notSeen', pose: 'FRONT' },
  { id: 'flaking', region: 'forehead', status: 'inconclusive', pose: 'FRONT' },
];
const ids = layers => layers.map(l => l.id).sort();

// Default overview: every finding located on this photo, nothing selected, nothing from another photo.
assert.deepEqual(ids(findingLayers(findings, frames.FRONT, 'overview', null)), ['acne', 'darkCircles']);
const all = sourceBoundCallouts(findings, frames.FRONT, captures, 'overview', null);
assert.deepEqual(all.map(c => c.id).sort(), ['acne', 'darkCircles'], 'one label per finding');
assert.ok(all.every(c => c.active === false), 'nothing is selected by default');
// A finding with a value but no location stays in the panel and is never drawn. Unclassified spots are not an error.
assert.deepEqual(unlocatedFindings(findings, frames.FRONT, 'overview', null).sort(), ['redness', 'spots']);
assert.equal(findingLayers([{ id: 'spots', region: 'chin', status: 'seen', pose: 'FRONT', count: 1, countAtLeast: true }], frames.FRONT, 'overview', null).length, 0);

// Selecting shows only that finding, on the photo it was measured on.
assert.equal(findingSnapshot(findings, 'overview', 'redness', frames, captures, frames.FRONT).angle, 'RIGHT');
assert.deepEqual(ids(findingLayers(findings, frames.RIGHT, 'overview', 'redness')), ['redness']);
assert.deepEqual(sourceBoundCallouts(findings, frames.RIGHT, captures, 'overview', 'redness').map(c => [c.id, c.active]), [['redness', true]]);
assert.deepEqual(ids(findingLayers(findings, frames.FRONT, 'overview', 'darkCircles')), ['darkCircles']);
assert.equal(sourceBoundCallouts(findings, frames.FRONT, captures, 'overview', 'darkCircles').length, 1);
// Deselecting returns to the same full set.
assert.deepEqual(ids(findingLayers(findings, frames.FRONT, 'overview', null)), ['acne', 'darkCircles']);

// Real coordinates, unchanged, and only this photo's markers.
const acne = findingLayers(findings, frames.FRONT, 'overview', 'acne')[0];
assert.deepEqual(acne.markers.map(m => [m.x, m.y]), [[300, 200], [340, 210]]);
assert.equal(findingLayers(findings, frames.LEFT, 'overview', 'acne')[0].markers[0].x, 500);
assert.equal(all.find(c => c.id === 'acne').anchor.x, 300);
assert.equal(findingLayers(findings, frames.FRONT, 'overview', 'acne', 'papule')[0].markers.length, 1);

// A page only shows its own regions.
assert.deepEqual(ids(findingLayers(findings, frames.FRONT, 'periorbital', null)), ['darkCircles']);
assert.deepEqual(ids(findingLayers(findings, frames.FRONT, 'forehead', null)), ['acne']);
assert.deepEqual(ids(findingLayers(findings, frames.FRONT, 'chin', null)), []);
// Another session's photo, or no landmarks, draws nothing invented.
assert.equal(sourceBoundCallouts(findings, frames.FRONT, { ...captures, FRONT: { ...captures.FRONT, captureId: 'f'.repeat(64) } }, 'overview', null).length, 0);
assert.deepEqual(ids(findingLayers(findings, { ...frames.FRONT, landmarks: undefined }, 'overview', null)), ['acne']);
// The label on the photo uses the catalog's shorter name; the card keeps the full one.
assert.equal(FINDING_DEFS.darkCircles.callout, 'Göz altı morlukları');
assert.equal(sourceBoundCallouts(findings, frames.FRONT, captures, 'periorbital', null)[0].label, 'Göz altı morlukları');
console.log('PASS');
"""


def test_label_layout_and_selection_rules():
    done = subprocess.run(['node', '-e', BOOTSTRAP + SCRIPT], cwd=ROOT, capture_output=True, text=True, encoding='utf8')
    assert done.returncode == 0, done.stdout + done.stderr
    assert 'PASS' in done.stdout


def test_labels_have_no_fixed_english_width_and_are_not_cut():
    source = (ROOT / 'apps/vehicle-app/src/components/skin/SkinFindingCallouts.tsx').read_text('utf8')
    assert 'truncate' not in source and 'text-overflow' not in source and 'line-clamp' not in source
    panel = (ROOT / 'apps/vehicle-app/src/components/skin/SkinFindingsPanel.tsx').read_text('utf8')
    start = panel.index('function OverviewFindingCard')
    assert 'truncate' not in panel[start:], 'a finding name on a card is never cut short'


def test_labels_use_the_frame_the_photo_is_drawn_in():
    # T-zone and Lips draw the regional replay's frame. A label placed from another crop pointed at the wrong spot.
    source = (ROOT / 'apps/vehicle-app/src/components/skin/SkinFacePanel.tsx').read_text('utf8')
    assert 'regionalReplay?.viewBox??displayCrop' in source
    assert 'crop={viewCrop}' in source and 'aspectRatio: viewCrop.width / viewCrop.height' in source


def test_findings_sit_on_a_clean_photo():
    source = (ROOT / 'apps/vehicle-app/src/components/skin/SkinFacePanel.tsx').read_text('utf8')
    assert '!selectedFinding&&!layers.length&&regionalLayers.map(' in source


def test_callout_strings_are_translated():
    catalog = json.loads((ROOT / 'shared/localization/messages.json').read_text('utf8'))
    rows = {row.get('en'): row for row in catalog.values()}
    assert rows['Dark circles']['de'] == 'Augenringe'
    assert rows['Show all findings']['de']
    assert rows['Show only this on the face']['de']
