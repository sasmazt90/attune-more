// B5 chain test inside the prototype page: synthetic user speech (Piper, labelled) is played into a MediaStream that
// replaces the microphone, so the real-time VAD, Whisper, the session core and Piper/<audio> run exactly as in use.
// The user's speech end is known from the schedule; every stage is on the page's performance.now() clock.
import {createPiper} from '../dist/speech.js';
const VOICES = {tr: 'tr_TR-dfki-medium', en: 'en_US-kristin-medium', de: 'de_DE-kerstin-medium'};
const sleep = ms => new Promise(r => setTimeout(r, ms));
export async function run({conversation, app}) {
  const R = window.__chain = window.__result = {id: conversation.id, done: false, turns: []};
  try {
    document.getElementById('consent').checked = true;
    document.getElementById('lang').value = conversation.language;
    const ctx = new AudioContext({sampleRate: 16000}); await ctx.resume(); window.__testAudioContext = ctx;
    const dest = ctx.createMediaStreamDestination();
    const userVoice = await createPiper({voice: VOICES[conversation.language]});
    const clips = [];
    for (const text of conversation.turns) clips.push(await userVoice.synthesize(text));
    await app.start(async () => dest.stream);
    for (let i = 0; i < clips.length; i++) {
      const c = clips[i], buf = ctx.createBuffer(1, c.pcm.length, c.sampleRate); buf.copyToChannel(c.pcm, 0);
      const src = ctx.createBufferSource(); src.buffer = buf; src.connect(dest);
      const before = window.__trace.length;
      const startAt = ctx.currentTime + 0.3;
      const perfAtStart = performance.now() + 300;
      src.start(startAt);
      const speechEnd = perfAtStart + c.pcm.length / c.sampleRate * 1000;
      // wait for this turn to finish (assistant audio ended or turn done without audio)
      const deadline = performance.now() + 180000;
      while (performance.now() < deadline) {
        const t = window.__trace.slice(before);
        const done = t.find(x => x.stage === 'turn-done');
        if (done && (t.some(x => x.stage === 'ended') || !t.some(x => x.stage === 'playing') && performance.now() - done.t > 1500)) break;
        await sleep(100);
      }
      const t = window.__trace.slice(before);
      R.turns.push({index: i + 1, text: conversation.turns[i], userSpeechEndAt: Math.round(speechEnd), stages: t});
      await sleep(400);
    }
    const before = window.__trace.length;
    await app.finish();
    R.closing = {stages: window.__trace.slice(before), result: window.__closing};
  } catch (e) { R.error = String(e && (e.stack || e.message) || e); }
  R.done = true;
}
