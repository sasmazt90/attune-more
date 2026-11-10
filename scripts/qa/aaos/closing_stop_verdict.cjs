'use strict';
// Pure decisions of the AAOS closing stop cases (no device access), shared by aaos-mental-closing.cjs and its unit test.
//
// A stop time is only measured from a player that Android reports as 'started' (AudioPlaybackConfiguration in
// `dumpsys audio`). The page's 'playing' event comes earlier than that state; acting on it alone produced the round-3
// result "consent revoked during A: not measurable" (no started player at the action in 3 of 3 runs).

const PLAYER_LINE = /AudioPlaybackConfiguration piid:(\d+)[^\n]*?u\/pid:\d+\/(\d+) state:(\w+)/g;

// Player ids of one process and their states, from `dumpsys audio` text.
function players(dumpsysAudio, pid) {
  return [...String(dumpsysAudio).matchAll(PLAYER_LINE)].filter(m => m[2] === String(pid)).map(m => ({piid: m[1], state: m[3]}));
}
const startedPiids = (dumpsysAudio, pid) => players(dumpsysAudio, pid).filter(p => p.state === 'started').map(p => p.piid);

// series: [{ms, started: [piid...], dumpMs}] sampled from the action on (ms relative to the action; the sampler is
// started just before the action, so its first request can run concurrently with it).
// preAction (round 5 on): {msBefore, started} = the last `dumpsys audio` snapshot that COMPLETED before the action
// (msBefore = action time - completion time). Round 4 showed why: the consent action pauses the media 22 ms after it is
// issued, while the first sampler request (issued 2 ms before the action) took 30 ms; that snapshot most likely saw the
// pause and read as "not started at the action". With preAction, the at-action state comes from a snapshot that ended
// before the action (at most maxGapMs earlier), rows requested before the action are ignored, and the stop time is the
// completion of the first snapshot requested after the action that shows no started player: an upper bound
// (stoppedByMs), never earlier than the stop. Without preAction the round-4 rule applies unchanged.
// Returns the checks of one stop case as {what, pass, detail}; a missing precondition is a failed (blocked) check.
function stopBound(series, reference = 0) {
  const after = series.filter(row => row.ms >= 0);
  const index = after.findIndex(row => !row.started.length);
  if (index < 0) return {stoppedByMs: null, stoppedAfterMs: null};
  const row = after[index];
  return {stoppedByMs: row.ms + (row.dumpMs || 0) - reference, stoppedAfterMs: Math.max(0, index ? after[index - 1].ms : 0) - reference};
}

function stopChecks({name, action, at, beforeStart, startedBeforeAction, series, appPlayerStoppedMs, reference = 0, criterionMs = 1000, sampleMs, preAction, maxGapMs = 150}) {
  const usable = preAction && preAction.msBefore >= 0 && preAction.msBefore <= maxGapMs;
  const atAction = preAction ? (usable ? preAction.started.length > 0 : null) : (series.length ? series[0].started.length > 0 : null);
  if (beforeStart) {
    const everStarted = series.some(row => row.started.length > 0);
    return [
      {what: `${name}: precondition: the app's player was not yet 'started' at the ${action}`, pass: atAction === false, detail: {atAction, preAction: preAction || null}},
      {what: `${name}: the app's player never entered 'started' in the ${sampleMs} ms after the ${action}`, pass: atAction === false && !everStarted,
        detail: {everStarted}},
    ];
  }
  const observed = Boolean(startedBeforeAction && startedBeforeAction.observed);
  if (preAction) {
    const {stoppedByMs, stoppedAfterMs} = stopBound(series, reference);
    return [
      {what: `${name}: precondition: Android reported the app's player 'started' after ${at} before the ${action} (otherwise blocked: no stop time is measured)`,
        pass: observed, detail: startedBeforeAction},
      {what: `${name}: the app's player left 'started' within ${criterionMs} ms of the stop condition (measured as an upper bound: ${stoppedByMs === null ? 'n/a' : stoppedByMs} ms)`,
        pass: observed && atAction === true && stoppedByMs !== null && stoppedByMs <= criterionMs, detail: {atAction, preAction, stoppedByMs, stoppedAfterMs}},
    ];
  }
  const stopped = appPlayerStoppedMs === null || appPlayerStoppedMs === undefined ? null : appPlayerStoppedMs - reference;
  return [
    {what: `${name}: precondition: Android reported the app's player 'started' after ${at} before the ${action} (otherwise blocked: no stop time is measured)`,
      pass: observed, detail: startedBeforeAction},
    {what: `${name}: the app's player left 'started' within ${criterionMs} ms of the stop condition (proposed criterion, measured ${stopped === null ? 'n/a' : stopped} ms)`,
      pass: observed && atAction === true && stopped !== null && stopped <= criterionMs, detail: {atAction, stoppedMs: stopped}},
  ];
}

// Live requests that were in flight at a stop condition. Every one must end without audio. For a client-side stop
// (cancel, mute, consent, background) that means: aborted by the page and never answered. For driving the API's own
// park gate may answer first (it polls the vehicle state every 100 ms while synthesis runs, kills the worker and answers
// 409). requests: [{kind, aborted, status, answeredAfterActionMs, contentType, audioBytes}].
//
// Round 6: three outcomes. 'BLOCKED' when nothing was tested: no request in flight, or none of the kinds the case
// requires (`require`, e.g. ['tts-live'] for the speech drive test, ['analysis-live'] for the catalog closing). An empty
// list never passes (round 5 counted inFlightVerdict('drive', []) as a pass). A failure stays a failure even when a
// required kind is missing. A 409 is accepted only for driving, only for the speech request, and only with evidence that
// the park gate produced it: the product route answers 409 solely when its backend's park/authentication gate refused
// (a client cancellation is 499 there), and the answer carried no audio (JSON, no bytes of audio). A 409 without that
// evidence fails.
function inFlightVerdict(action, requests, {require = []} = {}) {
  const rows = requests.map(q => {
    const parkGate = action === 'drive' && q.kind === 'tts-live' && !q.aborted && q.status === 409
      && /^application\/json/.test(q.contentType || '') && q.audioBytes === 0;
    const outcome = q.aborted && (q.answeredAfterActionMs === null || q.answeredAfterActionMs === undefined) ? 'aborted'
      : parkGate ? 'refused-409-park-gate'
      : q.answeredAfterActionMs !== null && q.answeredAfterActionMs !== undefined ? (q.status === 409 ? 'refused-409-without-park-gate-evidence' : 'answered')
      : 'unresolved';
    return {...q, outcome};
  });
  const missing = require.filter(kind => !rows.some(q => q.kind === kind));
  const failed = rows.filter(q => !['aborted', 'refused-409-park-gate'].includes(q.outcome));
  const status = failed.length ? 'FAIL' : !rows.length || missing.length ? 'BLOCKED' : 'PASS';
  const reason = failed.length ? 'request-ended-otherwise' : !rows.length ? 'no-request-in-flight' : missing.length ? 'required-request-not-in-flight' : null;
  return {status, pass: status === 'PASS', reason, missing, rows};
}

// Round 6 (L3): the four parts of a complete closing (A, B, C, then the personal line P), each with its own evidence.
// parts: [{part, expectedS}] in playing order, expectedS = the part's own WAV duration (manifest) or, for a generated
// line, the decoded duration of its own response; stages: [{stage, pm}] (page timeline); media: [{type, el, pm, duration}]
// (media events, same clock). A part needs exactly one 'playing' and one 'ended' stage, each matched within matchMs by a
// media event of the closing element (the element that played A): a sound on another element can never stand in for a
// missing part. Missing evidence (stage, media event or duration) blocks the closing: it is reported, never filtered
// away into a pass. Elapsed playing->ended must be within +-tolerance of the part's own duration, the element must
// report that duration (the right recording), and each part must start only after the previous one ended.
function closingSequence({parts, stages, media, tolerance = 0.1, matchMs = 80, durationMatchS = 0.05}) {
  const prefix = {A: 'closing-A-', B: 'closing-B-', C: 'closing-C-', P: 'closing-summary-'};
  const blocked = [], failed = [], rows = [];
  let element = null, previousEnd = null;
  for (const {part, expectedS} of parts) {
    const row = {part, expectedS: expectedS ?? null};
    rows.push(row);
    const plays = stages.filter(s => s.stage === prefix[part] + 'playing'), ends = stages.filter(s => s.stage === prefix[part] + 'ended');
    row.stageCounts = {playing: plays.length, ended: ends.length};
    if (plays.length > 1 || ends.length > 1) { failed.push(`${part}:repeated`); continue; }
    if (!plays.length || !ends.length) { blocked.push(`${part}:no-${plays.length ? 'ended' : 'playing'}-stage`); continue; }
    const near = (type, at) => media.filter(m => m.type === type && Math.abs(m.pm - at) <= matchMs && (element === null || m.el === element))
      .sort((a, b) => Math.abs(a.pm - at) - Math.abs(b.pm - at))[0];
    const playing = near('playing', plays[0].pm);
    if (playing && element === null) element = playing.el;
    const ended = near('ended', ends[0].pm);
    if (!playing || !ended) { blocked.push(`${part}:no-${playing ? 'ended' : 'playing'}-media-event-on-the-closing-element`); continue; }
    row.element = playing.el;
    row.elapsedMs = Math.round(ended.pm - playing.pm);
    // The element's own duration of this part, from its 'ended' event or, when the page reset the source before the
    // harness listener ran (round 6, first part), from its 'playing' event. Neither: blocked, never a failure or a pass.
    row.elementDurationS = ended.duration ?? playing.duration ?? null;
    row.elementDurationFrom = ended.duration != null ? 'ended' : playing.duration != null ? 'playing' : null;
    if (!(expectedS > 0)) { blocked.push(`${part}:no-duration`); continue; }
    row.ratio = Math.round(row.elapsedMs / 1000 / expectedS * 100) / 100;
    if (Math.abs(row.elapsedMs / 1000 - expectedS) > tolerance * expectedS) failed.push(`${part}:elapsed-outside-${Math.round(tolerance * 100)}%`);
    if (row.elementDurationS === null) blocked.push(`${part}:no-element-duration`);
    else if (Math.abs(row.elementDurationS - expectedS) > durationMatchS) failed.push(`${part}:not-the-expected-recording`);
    if (previousEnd !== null && playing.pm < previousEnd) failed.push(`${part}:overlaps-the-previous-part`);
    previousEnd = ended.pm;
  }
  const status = failed.length ? 'FAIL' : blocked.length ? 'BLOCKED' : 'PASS';
  return {status, pass: status === 'PASS', failed, blocked, rows, element};
}

// Counts of a run's checks by outcome. A check without a status is PASS or FAIL from its boolean; 'NOT_APPLICABLE'
// never counts as a pass. The run is FAIL if anything failed, else BLOCKED if anything was blocked, else PASS.
function verdictCounts(checks) {
  const counts = {PASS: 0, FAIL: 0, BLOCKED: 0, NOT_APPLICABLE: 0};
  for (const c of checks) counts[c.status || (c.pass ? 'PASS' : 'FAIL')]++;
  const status = counts.FAIL ? 'FAIL' : counts.BLOCKED ? 'BLOCKED' : counts.PASS ? 'PASS' : 'BLOCKED';
  return {counts, status};
}

// Media clock check: a media element's 'playing' -> 'ended' time against its own duration. Round 4's first AAOS case
// played every element in about half its length (1.95 s for 3.84 s of audio) while the page, guest and host clocks
// agreed; the emulator's output consumed samples too fast. A closing with such an element is not a valid latency
// sample. pairs: [{elapsedMs, durationS}] -> {ok, ratios}; ratio = duration / elapsed (1.0 = real time).
function playbackClock(pairs, tolerance = 0.1) {
  const ratios = pairs.filter(p => p.durationS > 0 && p.elapsedMs > 0).map(p => Math.round(p.durationS * 1000 / p.elapsedMs * 100) / 100);
  return {ok: ratios.length > 0 && ratios.every(r => Math.abs(r - 1) <= tolerance), ratios};
}

module.exports = {players, startedPiids, stopChecks, stopBound, inFlightVerdict, closingSequence, verdictCounts, playbackClock};
