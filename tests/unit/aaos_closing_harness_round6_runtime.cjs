/** Round 6 at the harness level: the real liveCancellation(), l3() and stopCheckRows() of
 * scripts/qa/aaos/aaos-mental-closing.cjs, taken from its source and run with recorded-style request rows and page
 * events (no device). Shows that an empty or wrong set of in-flight requests is BLOCKED (never PASS), that a 409 counts
 * only with park-gate evidence, and that a closing with a missing or substituted part is not passed. */
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path');
const ROOT = path.resolve(__dirname, '../..');
const source = fs.readFileSync(path.join(ROOT, 'scripts/qa/aaos/aaos-mental-closing.cjs'), 'utf8');
const take = (start, end) => { const a = source.indexOf(start), b = source.indexOf(end, a); assert(a >= 0 && b > a, start); return source.slice(a, b); };
const code = [take('function liveCancellation(', '// Each WebView page'), take('function stopCheckRows(', '\nasync function waitStage'),
  take('const MANIFEST_DURATIONS = ', 'async function assetParity(')].join('\n');
const {inFlightVerdict, closingSequence, stopChecks} = require(path.join(ROOT, 'scripts/qa/aaos/closing_stop_verdict.cjs'));
const harness = (plan) => new Function('plan', 'ROUND', 'TTS_MODE', 'inFlightVerdict', 'closingSequence', 'fs', 'path', 'repository',
  code + '\nreturn {liveCancellation, stopCheckRows, l3, MANIFEST_DURATIONS};')(plan, 6, 'live-api', inFlightVerdict, closingSequence, fs, path, ROOT);
const run = () => { const checks = []; const check = (what, pass) => { checks.push({what, status: pass ? 'PASS' : 'FAIL'}); return pass; };
  check.tri = (what, status) => { checks.push({what, status}); return status === 'PASS'; }; return {checks, check}; };
const actedAt = 100000;

// 1. Drive during C, catalog closing, nothing in flight (the analysis had already answered): BLOCKED, not PASS.
let plan = {requests: [{kind: 'analysis-live', id: 'c', at: actedAt - 4000, answeredAt: actedAt - 500, status: 200}]};
let h = harness(plan), t = run();
let result = h.liveCancellation({name: 'c', action: 'drive', require: ['analysis-live']}, actedAt, t.check);
assert.deepEqual(t.checks.map(c => c.status), ['BLOCKED']);
assert.equal(result.reason, 'no-request-in-flight');
// 1b. A drive case that names no requirement and has nothing in flight is still blocked (round 5 passed it).
t = run(); h.liveCancellation({name: 'c', action: 'drive'}, actedAt, t.check);
assert.deepEqual(t.checks.map(c => c.status), ['BLOCKED']);
// 1c. A non-driving case without requirement and nothing in flight records no check (nothing claimed).
t = run(); assert.equal(h.liveCancellation({name: 'c', action: 'mute'}, actedAt, t.check).note.startsWith('no live request'), true);
assert.equal(t.checks.length, 0);

// 2. Reply-speech drive test with only the analysis in flight: BLOCKED (the speech request is what it tests).
plan = {requests: [{kind: 'analysis-live', id: 'r', at: actedAt - 900, aborted: true, abortedAfterMs: 950}]};
t = run(); result = harness(plan).liveCancellation({name: 'r', action: 'drive', require: ['tts-live']}, actedAt, t.check);
assert.deepEqual([t.checks[0].status, result.reason], ['BLOCKED', 'required-request-not-in-flight']);

// 3. Speech in flight, answered 409 after the drive: PASS only with the park-gate evidence (JSON, no audio bytes).
const speech = extra => ({requests: [{kind: 'tts-live', id: 's', reply: true, at: actedAt - 2500, answeredAt: actedAt + 90, status: 409, ...extra}]});
t = run(); harness(speech({contentType: 'application/json', audioBytes: 0})).liveCancellation({name: 's', action: 'drive', require: ['tts-live']}, actedAt, t.check);
assert.equal(t.checks[0].status, 'PASS');
t = run(); harness(speech({})).liveCancellation({name: 's', action: 'drive', require: ['tts-live']}, actedAt, t.check);
assert.equal(t.checks[0].status, 'FAIL', 'a 409 without evidence is not accepted');
t = run(); harness(speech({status: 200, contentType: 'audio/wav', audioBytes: 90000})).liveCancellation({name: 's', action: 'drive', require: ['tts-live']}, actedAt, t.check);
assert.equal(t.checks[0].status, 'FAIL', 'audio delivered after the drive fails');
t = run(); harness(speech({contentType: 'application/json', audioBytes: 0})).liveCancellation({name: 's', action: 'cancel', require: ['tts-live']}, actedAt, t.check);
assert.equal(t.checks[0].status, 'FAIL', 'the 409 rule is for driving only');
// 3b. Aborted by the page during the test hold of the analysis: PASS for the catalog drive case.
t = run(); harness({requests: [{kind: 'analysis-live', id: 'h', at: actedAt - 6000, aborted: true, abortedAfterMs: 6200, heldMs: 3000}]})
  .liveCancellation({name: 'h', action: 'drive', require: ['analysis-live']}, actedAt, t.check);
assert.equal(t.checks[0].status, 'PASS');

// 4. Stop checks: an unmet precondition (no started player before the action) is BLOCKED, not a measured failure.
t = run(); harness({requests: []}).stopCheckRows(stopChecks({name: 'x', action: 'consent', at: 'closing-A-playing', startedBeforeAction: {observed: false},
  series: [{ms: 10, started: [], dumpMs: 20}], preAction: undefined, sampleMs: 8000}), t.check);
assert.deepEqual(t.checks.map(c => c.status), ['BLOCKED', 'BLOCKED']);
t = run(); harness({requests: []}).stopCheckRows(stopChecks({name: 'x', action: 'consent', at: 'closing-A-playing', startedBeforeAction: {observed: true},
  series: [{ms: 10, started: ['5'], dumpMs: 20}, {ms: 1500, started: ['5'], dumpMs: 20}], preAction: {msBefore: 10, started: ['5']}, sampleMs: 8000}), t.check);
assert.deepEqual(t.checks.map(c => c.status), ['PASS', 'FAIL']);

// 5. L3 through l3(): the parts' durations come from the recordings the closing fetched (manifest), the evidence from
// the page events. A complete, correct closing passes; a missing personal part or one played on another element is
// blocked; a part played at twice the speed fails.
const abc = JSON.parse(fs.readFileSync(path.join(ROOT, 'apps/vehicle-app/public/audio/mental/closing-abc/v1/manifest.json'), 'utf8')).entries;
const pick = (group, i) => abc.filter(e => e.language === 'en' && e.group === group)[i];
const clips = [pick('A', 0), pick('B', 1), pick('C', 2)];
const events = ({personal = {el: 1, seconds: 3.2}, speed = {}} = {}) => {
  const out = clips.map(c => ({kind: 'asset', url: c.audioPath}));
  let t = 1000;
  const part = (prefix, seconds, el, rate = 1) => {
    out.push({kind: 'stage', stage: prefix + 'playing', pm: t + 1}, {kind: 'media', type: 'playing', el, pm: t, duration: seconds});
    t += seconds * 1000 / rate;
    out.push({kind: 'stage', stage: prefix + 'ended', pm: t + 1}, {kind: 'media', type: 'ended', el, pm: t, duration: seconds});
    t += 127;
  };
  clips.forEach(c => part(`closing-${c.group}-`, c.durationMs / 1000, 1, speed[c.group] || 1));
  if (personal) part('closing-summary-', personal.seconds, personal.el);
  return out;
};
const generated = {requests: [{kind: 'tts-live', closing: true, audioSeconds: 3.2}]};
h = harness({requests: []});
assert.equal(h.l3(generated, events()).status, 'PASS');
assert.equal(h.l3(generated, events()).personalSource, 'generated');
assert.equal(h.l3(generated, events({personal: null})).status, 'BLOCKED', 'missing personal part');
assert.equal(h.l3(generated, events({personal: {el: 7, seconds: 3.2}})).status, 'BLOCKED', 'another element cannot stand in');
assert.equal(h.l3({requests: []}, events()).status, 'BLOCKED', 'no duration for the personal part');
assert.equal(h.l3(generated, events({speed: {B: 2}})).status, 'FAIL', 'B at 2x');
console.log('PASS round-6 harness level: empty or wrong in-flight sets are BLOCKED, 409 only with park-gate evidence and only for driving, unmet stop preconditions BLOCKED, L3 needs all four parts with their own evidence and durations (no device)');
