import assert from 'node:assert/strict';
import fs from 'node:fs';
import {skinDisplayKind} from '../../apps/vehicle-app/src/utils/skinPresentation.ts';
const row = (id, unit, overrides = {}) => ({id, unit, score: 42, ...overrides});

assert.equal(skinDisplayKind(row('oil', 'percent-visible-area')), 'percent');
assert.equal(skinDisplayKind(row('oil', 'visible-highlight-area-percent')), 'percent');
assert.equal(skinDisplayKind(row('redness', 'Renk indeksi / 100')), 'index');
assert.equal(skinDisplayKind(row('tone', '', {measurement:{unit:'color-index-0-100'}})), 'index');
assert.equal(skinDisplayKind(row('lines', '', {appearance:{unit:'directional-line-index-0-100'}})), 'index');
assert.equal(skinDisplayKind(row('dry', '', {appearance:{unit:'appearance-score-0-100'}})), 'index');
assert.equal(skinDisplayKind(row('acne', '5 aday')), 'count');
assert.equal(skinDisplayKind(row('sag', '', {appearance:{type:'longitudinal_measurement',unit:'normalized-contour-ratio'}})), 'contour');

const component = fs.readFileSync(new URL('../../apps/vehicle-app/src/components/skin/SkinIndicatorValue.tsx', import.meta.url), 'utf8');
assert.match(component, /if \(kind !== 'percent'\) return <ResultValue/);
assert.match(component, /data-skin-percentage/);
console.log('PASS: only true supported-area ratios use percent bars; indices, counts and contours remain semantically distinct');
