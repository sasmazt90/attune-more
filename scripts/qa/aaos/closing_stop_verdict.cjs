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

// series: [{ms, started: [piid...]}] sampled from the action on (ms relative to the action, first row at the action).
// Returns the checks of one stop case as {what, pass, detail}; a missing precondition is a failed (blocked) check.
function stopChecks({name, action, at, beforeStart, startedBeforeAction, series, appPlayerStoppedMs, reference = 0, criterionMs = 1000, sampleMs}) {
  const atAction = series.length ? series[0].started.length > 0 : null;
  if (beforeStart) {
    const everStarted = series.some(row => row.started.length > 0);
    return [
      {what: `${name}: precondition: the app's player was not yet 'started' at the ${action}`, pass: atAction === false, detail: {atAction}},
      {what: `${name}: the app's player never entered 'started' in the ${sampleMs} ms after the ${action}`, pass: atAction === false && !everStarted,
        detail: {everStarted}},
    ];
  }
  const observed = Boolean(startedBeforeAction && startedBeforeAction.observed);
  const stopped = appPlayerStoppedMs === null || appPlayerStoppedMs === undefined ? null : appPlayerStoppedMs - reference;
  return [
    {what: `${name}: precondition: Android reported the app's player 'started' after ${at} before the ${action} (otherwise blocked: no stop time is measured)`,
      pass: observed, detail: startedBeforeAction},
    {what: `${name}: the app's player left 'started' within ${criterionMs} ms of the stop condition (proposed criterion, measured ${stopped === null ? 'n/a' : stopped} ms)`,
      pass: observed && atAction === true && stopped !== null && stopped <= criterionMs, detail: {atAction, stoppedMs: stopped}},
  ];
}

module.exports = {players, startedPiids, stopChecks};
