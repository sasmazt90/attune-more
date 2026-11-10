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

// Live requests of the closing that were in flight at a stop condition. Every one must end without audio. For a
// client-side stop (cancel, mute, consent, background) that means: aborted by the page and never answered. For
// driving the API's own park gate may answer first (it polls the vehicle state every 100 ms while synthesis runs,
// kills the worker and answers 409); round 4 recorded exactly that 90 ms after the drive, before the page saw the
// motion at 232 ms. Proposed from round 5 on, for driving only: aborted, or answered 409 by the park gate. A 2xx or any
// other answer fails in every case. requests: [{kind, aborted, status, answeredAfterActionMs}].
function inFlightVerdict(action, requests) {
  const rows = requests.map(q => {
    const refused = action === 'drive' && !q.aborted && q.status === 409;
    return {...q, outcome: q.aborted && q.answeredAfterActionMs === null ? 'aborted' : refused ? 'refused-409-park-gate' : q.answeredAfterActionMs !== null ? 'answered' : 'unresolved'};
  });
  return {pass: rows.every(q => q.outcome === 'aborted' || q.outcome === 'refused-409-park-gate'), rows};
}

// Media clock check: a media element's 'playing' -> 'ended' time against its own duration. Round 4's first AAOS case
// played every element in about half its length (1.95 s for 3.84 s of audio) while the page, guest and host clocks
// agreed; the emulator's output consumed samples too fast. A closing with such an element is not a valid latency
// sample. pairs: [{elapsedMs, durationS}] -> {ok, ratios}; ratio = duration / elapsed (1.0 = real time).
function playbackClock(pairs, tolerance = 0.1) {
  const ratios = pairs.filter(p => p.durationS > 0 && p.elapsedMs > 0).map(p => Math.round(p.durationS * 1000 / p.elapsedMs * 100) / 100);
  return {ok: ratios.length > 0 && ratios.every(r => Math.abs(r - 1) <= tolerance), ratios};
}

module.exports = {players, startedPiids, stopChecks, stopBound, inFlightVerdict, playbackClock};
