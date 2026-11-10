/** AAOS closing stop cases: the pure decisions of scripts/qa/aaos/closing_stop_verdict.cjs on the player series recorded
 * in round 3 (run aaos-mental-closing-1794309651918, first 14 samples) and synthetic dumpsys lines. No device. */
const assert = require('node:assert/strict');
const {players, startedPiids, stopChecks} = require('../../scripts/qa/aaos/closing_stop_verdict.cjs');

const rows = list => list.map(([ms, started]) => ({ms, started}));
// Round 3, recorded: consent revoked 1.3 s after A's 'playing' event; Android never reported a started player.
const consentRound3 = rows([[-3, []], [61, []], [84, []], [140, []], [178, []], [258, []], [298, []], [382, []], [406, []], [447, []], [464, []], [502, []], [519, []], [557, []]]);
// Round 3, recorded: driving during A; player 535 started at the action, stopped 286 ms after it (backend ack at 5 ms).
const driveRound3 = rows([[-3, ['535']], [48, ['535']], [69, ['535']], [117, ['535']], [142, ['535']], [192, ['535']], [225, ['535']], [286, []], [312, []], [360, []], [379, []], [418, []], [437, []], [498, []]]);

// Parser: only the app process's players, with their states.
const dump = [
  '  AudioPlaybackConfiguration piid:399 type:android.media.AudioTrack u/pid:10123/4321 state:started attr:AudioAttributes',
  '  AudioPlaybackConfiguration piid:400 type:android.media.AudioTrack u/pid:10123/4321 state:paused attr:AudioAttributes',
  '  AudioPlaybackConfiguration piid:12 type:android.media.AudioTrack u/pid:1000/999 state:started attr:AudioAttributes',
].join('\n');
assert.deepEqual(players(dump, 4321), [{piid: '399', state: 'started'}, {piid: '400', state: 'paused'}]);
assert.deepEqual(startedPiids(dump, 4321), ['399']);
assert.deepEqual(startedPiids(dump, 1), []);

const base = {name: 'case', action: 'consent', at: 'closing-A-playing', criterionMs: 1000, sampleMs: 8000};
const verdict = args => stopChecks({...base, ...args}).map(c => c.pass);

// The round-3 situation can no longer pass or be read as a stop time: without an observed started player the
// precondition fails (blocked) and so does the stop check.
assert.deepEqual(verdict({startedBeforeAction: {observed: false, waitedMs: 5000}, series: consentRound3, appPlayerStoppedMs: -3}), [false, false]);
// Even if the harness had acted anyway, a series without a started player at the action is not a stop measurement.
assert.deepEqual(verdict({startedBeforeAction: {observed: true}, series: consentRound3, appPlayerStoppedMs: -3}), [true, false]);
// Started observed before acting, the player stops 286 ms after the backend acknowledgement reference of 5 ms: pass.
assert.deepEqual(verdict({action: 'drive', startedBeforeAction: {observed: true}, series: driveRound3, appPlayerStoppedMs: 286, reference: 5}), [true, true]);
// Started, but it keeps playing past the criterion: fail.
assert.deepEqual(verdict({startedBeforeAction: {observed: true}, series: driveRound3, appPlayerStoppedMs: 1450}), [true, false]);
// Started, never stopped in the sampled window: fail.
assert.deepEqual(verdict({startedBeforeAction: {observed: true}, series: driveRound3, appPlayerStoppedMs: null}), [true, false]);

// Before start: the player was not started at the action and never starts afterwards -> pass; any later start -> fail;
// a player already started at the action -> the precondition fails (that is the during-playback case, not this one).
assert.deepEqual(verdict({beforeStart: true, series: consentRound3}), [true, true]);
assert.deepEqual(verdict({beforeStart: true, series: rows([[-2, []], [40, []], [900, ['77']], [950, []]])}), [true, false]);
assert.deepEqual(verdict({beforeStart: true, series: driveRound3}), [false, false]);
console.log('aaos closing stop verdict: ok');
