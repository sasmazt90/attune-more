/** AAOS closing stop cases: the pure decisions of scripts/qa/aaos/closing_stop_verdict.cjs on the player series recorded
 * in round 3 (run aaos-mental-closing-1794309651918, first 14 samples) and round 4 (run aaos-mental-closing-1794331528693)
 * and synthetic dumpsys lines. No device. */
const assert = require('node:assert/strict');
const {players, startedPiids, stopChecks, stopBound, inFlightVerdict, closingSequence, verdictCounts, playbackClock} = require('../../scripts/qa/aaos/closing_stop_verdict.cjs');

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

// Round 4 (run aaos-mental-closing-1794331528693), recorded [ms, started, dumpMs]. Consent revoked during A: the
// sampler's first request was issued 2 ms before the action and took 30 ms; the app paused the media 22 ms after the
// action. The round-4 rule read that concurrent snapshot as "not started at the action" (FAIL, kept as recorded).
const withDump = list => list.map(([ms, started, dumpMs]) => ({ms, started, dumpMs}));
const consentRound4 = withDump([[-2, [], 30], [59, [], 21], [80, [], 19], [140, [], 37], [177, [], 37], [270, [], 60]]);
const muteRound4 = withDump([[-3, ['7719'], 29], [58, ['7719'], 33], [91, [], 23], [153, [], 25]]);
// The round-4 verdict on the recorded data stays a failure under the round-4 rule.
assert.deepEqual(verdict({startedBeforeAction: {observed: true, afterStageMs: 30}, series: consentRound4, appPlayerStoppedMs: -2}), [true, false]);
// Round 5 rule: the at-action state comes from a snapshot that completed before the action; rows requested before the
// action are ignored; the stop is the completion of the first later snapshot without a started player (upper bound).
assert.deepEqual(stopBound(consentRound4), {stoppedByMs: 80, stoppedAfterMs: 0});
assert.deepEqual(stopBound(muteRound4), {stoppedByMs: 114, stoppedAfterMs: 58});
assert.deepEqual(verdict({startedBeforeAction: {observed: true}, preAction: {msBefore: 12, started: ['7743']}, series: consentRound4}), [true, true]);
// A pre-action snapshot that is too old, or shows no started player, is not evidence of playback at the action.
assert.deepEqual(verdict({startedBeforeAction: {observed: true}, preAction: {msBefore: 400, started: ['7743']}, series: consentRound4}), [true, false]);
assert.deepEqual(verdict({startedBeforeAction: {observed: true}, preAction: {msBefore: 10, started: []}, series: consentRound4}), [true, false]);
// The upper bound is what is compared: a player still started until a snapshot completing after the criterion fails.
assert.deepEqual(verdict({startedBeforeAction: {observed: true}, preAction: {msBefore: 5, started: ['1']},
  series: withDump([[0, ['1'], 30], [990, ['1'], 30], [1000, [], 30]])}), [true, false]);
// Driving: the reference is the backend acknowledgement (round 4: 18 ms).
assert.deepEqual(verdict({action: 'drive', startedBeforeAction: {observed: true}, preAction: {msBefore: 8, started: ['7823']}, reference: 18,
  series: withDump([[-2, ['7823'], 30], [60, ['7823'], 30], [190, [], 25]])}), [true, true]);
// Before start with a pre-action snapshot: not started then, never started afterwards.
assert.deepEqual(verdict({beforeStart: true, preAction: {msBefore: 6, started: []}, series: withDump([[-4, [], 40], [68, [], 37]])}), [true, true]);
assert.deepEqual(verdict({beforeStart: true, preAction: {msBefore: 6, started: ['9']}, series: withDump([[-4, [], 40]])}), [false, false]);

// In-flight requests. Round 4, tr-drive-during-C: the speech request was answered 409 by the park gate 90 ms after the
// drive (no audio); the round-4 check required "aborted and never answered" and failed; that result stays. Round 6: a 409
// passes only for driving, only for the speech request, and only with evidence (JSON answer, no audio bytes): the
// product route answers 409 solely for its backend's park gate. The round-4 row has no such evidence recorded.
const driveC = [{kind: 'tts-live', aborted: false, status: 409, answeredAfterActionMs: 90}];
assert.equal(inFlightVerdict('drive', driveC).status, 'FAIL');
assert.equal(inFlightVerdict('drive', driveC).rows[0].outcome, 'refused-409-without-park-gate-evidence');
const proven = [{kind: 'tts-live', aborted: false, status: 409, answeredAfterActionMs: 90, contentType: 'application/json', audioBytes: 0}];
assert.equal(inFlightVerdict('drive', proven, {require: ['tts-live']}).status, 'PASS');
assert.equal(inFlightVerdict('drive', proven).rows[0].outcome, 'refused-409-park-gate');
// Not for any other stop, not for the analysis request, not with audio bytes.
assert.equal(inFlightVerdict('cancel', proven).status, 'FAIL');
assert.equal(inFlightVerdict('consent', proven).status, 'FAIL');
assert.equal(inFlightVerdict('drive', [{...proven[0], kind: 'analysis-live'}]).status, 'FAIL');
assert.equal(inFlightVerdict('drive', [{...proven[0], contentType: 'audio/wav', audioBytes: 96044}]).status, 'FAIL');
assert.equal(inFlightVerdict('drive', [{kind: 'tts-live', aborted: false, status: 200, answeredAfterActionMs: 40}]).status, 'FAIL');
assert.equal(inFlightVerdict('consent', [{kind: 'analysis-live', aborted: true, status: null, answeredAfterActionMs: null}]).status, 'PASS');
assert.equal(inFlightVerdict('mute', [{kind: 'tts-live', aborted: false, status: null, answeredAfterActionMs: null}]).status, 'FAIL');
// Nothing in flight is never a pass (round 5 counted it as one): blocked, with the reason.
assert.deepEqual([inFlightVerdict('drive', []).status, inFlightVerdict('drive', []).pass, inFlightVerdict('drive', []).reason], ['BLOCKED', false, 'no-request-in-flight']);
assert.equal(inFlightVerdict('drive', [], {require: ['tts-live']}).status, 'BLOCKED');
// The speech drive test needs a speech request in flight: only the analysis in flight is blocked, not passed.
const onlyAnalysis = [{kind: 'analysis-live', aborted: true, status: null, answeredAfterActionMs: null}];
assert.deepEqual([inFlightVerdict('drive', onlyAnalysis, {require: ['tts-live']}).status, inFlightVerdict('drive', onlyAnalysis, {require: ['tts-live']}).reason],
  ['BLOCKED', 'required-request-not-in-flight']);
// A failure is not hidden behind a missing requirement.
assert.equal(inFlightVerdict('drive', [{kind: 'analysis-live', aborted: false, status: 200, answeredAfterActionMs: 30}], {require: ['tts-live']}).status, 'FAIL');
// The catalog closing: the analysis must be in flight and end aborted.
assert.equal(inFlightVerdict('drive', onlyAnalysis, {require: ['analysis-live']}).status, 'PASS');

// L3: four parts, each with its own stage and media evidence on the closing element, within 10 % of its own duration.
const seq = ({drop = [], el = {}, dur = {}, durEl = {}, extraStages = [], shift = {}} = {}) => {
  const parts = [['A', 2.0], ['B', 2.5], ['C', 3.0], ['P', 3.4]];
  const stages = [], media = [];
  let t = 1000;
  for (const [part, s] of parts) {
    const prefix = part === 'P' ? 'closing-summary-' : `closing-${part}-`, length = (dur[part] ?? s) * 1000, start = t + (shift[part] || 0);
    if (!drop.includes(part + ':playing')) stages.push({stage: prefix + 'playing', pm: start + 2});
    if (!drop.includes(part + ':ended')) stages.push({stage: prefix + 'ended', pm: start + length + 2});
    if (!drop.includes(part + ':media')) media.push({type: 'playing', el: el[part] ?? 1, pm: start, duration: durEl[part] ?? s}, {type: 'ended', el: el[part] ?? 1, pm: start + length, duration: durEl[part] ?? s});
    t = start + length + 127;
  }
  return {parts: parts.map(([part, expectedS]) => ({part, expectedS})), stages: [...stages, ...extraStages], media};
};
assert.equal(closingSequence(seq()).status, 'PASS');
assert.deepEqual(closingSequence(seq()).rows.map(r => r.ratio), [1, 1, 1, 1]);
// Missing part or evidence: blocked, never a pass from the remaining parts.
assert.deepEqual([closingSequence(seq({drop: ['P:playing', 'P:ended', 'P:media']})).status, closingSequence(seq({drop: ['P:playing', 'P:ended', 'P:media']})).blocked], ['BLOCKED', ['P:no-playing-stage']]);
assert.equal(closingSequence(seq({drop: ['B:ended']})).status, 'BLOCKED');
assert.equal(closingSequence(seq({drop: ['C:media']})).status, 'BLOCKED');
assert.equal(closingSequence({...seq(), parts: seq().parts.map(p => p.part === 'P' ? {part: 'P', expectedS: null} : p)}).status, 'BLOCKED');
// Another element's sound cannot stand in for the personal part.
const other = seq({el: {P: 9}});
assert.deepEqual([closingSequence(other).status, closingSequence(other).blocked], ['BLOCKED', ['P:no-playing-media-event-on-the-closing-element']]);
// Elapsed outside 10 % (the round-4 2x clock), a different recording, an overlap, a repeated part: failed.
assert.deepEqual(closingSequence(seq({dur: {C: 1.5}})).failed, ['C:elapsed-outside-10%']);
assert.deepEqual(closingSequence(seq({durEl: {P: 2.1}})).failed, ['P:not-the-expected-recording']);
assert.deepEqual(closingSequence(seq({shift: {B: -600}})).failed, ['B:overlaps-the-previous-part']);
assert.deepEqual(closingSequence(seq({extraStages: [{stage: 'closing-summary-playing', pm: 99999}]})).failed, ['P:repeated']);
// Run summary: not applicable never counts as a pass; any failure fails, any blocked blocks.
assert.deepEqual(verdictCounts([{pass: true}, {status: 'NOT_APPLICABLE', pass: false}]), {counts: {PASS: 1, FAIL: 0, BLOCKED: 0, NOT_APPLICABLE: 1}, status: 'PASS'});
assert.equal(verdictCounts([{pass: true}, {status: 'BLOCKED', pass: false}]).status, 'BLOCKED');
assert.equal(verdictCounts([{pass: false}, {status: 'BLOCKED', pass: false}]).status, 'FAIL');
assert.equal(verdictCounts([{status: 'NOT_APPLICABLE', pass: false}]).status, 'BLOCKED');

// Media clock. Round 4, first case: personal line 1.949 s for 3.84 s of audio (ratio 1.97); second case 3.12 s for 3.12 s.
assert.deepEqual(playbackClock([{elapsedMs: 1949, durationS: 3.84}]), {ok: false, ratios: [1.97]});
assert.deepEqual(playbackClock([{elapsedMs: 3121, durationS: 3.12}, {elapsedMs: 2424, durationS: 2.48}]), {ok: true, ratios: [1, 1.02]});
assert.deepEqual(playbackClock([]), {ok: false, ratios: []});
console.log('aaos closing stop verdict: ok');
