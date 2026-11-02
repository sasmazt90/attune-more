'use strict';
// Deterministic Mental provider boundary: no paid call can leave the machine under this
// route. Tests using it are labelled mocked-provider; they prove the client state machine,
// consent gates and storage, never provider or model quality.
function shortWav(durationSec = .25, sampleRate = 16000) {
  const samples = Math.floor(durationSec * sampleRate), size = samples * 2, wav = Buffer.alloc(44 + size);
  wav.write('RIFF', 0); wav.writeUInt32LE(36 + size, 4); wav.write('WAVE', 8); wav.write('fmt ', 12); wav.writeUInt32LE(16, 16);
  wav.writeUInt16LE(1, 20); wav.writeUInt16LE(1, 22); wav.writeUInt32LE(sampleRate, 24); wav.writeUInt32LE(sampleRate * 2, 28); wav.writeUInt16LE(2, 32); wav.writeUInt16LE(16, 34);
  wav.write('data', 36); wav.writeUInt32LE(size, 40);
  return wav;
}
const CORS = {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET,POST,DELETE,OPTIONS', 'Access-Control-Allow-Headers': '*', 'Access-Control-Expose-Headers': '*', 'Cache-Control': 'no-store'};
const SUMMARY = {providerType: 'LIVE_OPENAI', summaryText: 'You reflected on needing quiet personal space, maintaining calm focus, and taking restorative breaks between stops.', spokenSummary: 'You reflected on calm focus and taking a restorative break.',
  themes: ['Stres Yönetimi', 'Odaklanma'], moodTrend: 'RELAXED', recommendations: ['Take a short breathing pause before your next trip.', 'Maintain regular rest intervals on long drives.'], relatedSessionIds: [], recurringThemes: ['Stres Yönetimi']};

async function install(target) {
  const wav = shortWav();
  const state = {analyzeMode: 'success', converseMode: 'success', analyzeCalls: 0, converseCalls: 0, delayAnalyzeMs: 0, delayConverseMs: 0, analyzeBodies: [], speechRequests: []};
  const reply = (route, status, body, type = 'application/json', headers = CORS) => route.fulfill({status, contentType: type, headers, body: type === 'application/json' ? JSON.stringify(body) : body});
  await target.route(/\/api\/mental\/(provider-status|compact-context|converse|analyze-session|speech)/, async route => {
    if (route.request().method() === 'OPTIONS') return route.fulfill({status: 204, headers: CORS});
    const pathname = new URL(route.request().url()).pathname;
    if (pathname.endsWith('/provider-status')) return reply(route, 200, {isLiveLLM: true, apiKeyConfigured: true, providerName: 'Mocked provider'});
    if (pathname.endsWith('/compact-context')) return reply(route, 200, {memory: ['User values quiet personal space and calm pacing.'], method: 'extractive-user-quotes-v1'});
    if (pathname.endsWith('/converse')) {
      state.converseCalls++;
      if (state.delayConverseMs) await new Promise(ok => setTimeout(ok, state.delayConverseMs));
      if (state.converseMode === 'fail503') return reply(route, 503, {detail: 'CONVERSE_PROVIDER_UNAVAILABLE'});
      const text = state.converseCalls % 2 ? 'Thank you for sharing that. How has your energy felt during the drive?' : 'That makes sense. Short breaks can make the day feel lighter.';
      return reply(route, 200, {reply: text, isCrisis: false, providerType: 'LIVE_OPENAI'});
    }
    if (pathname.endsWith('/speech')) return reply(route, 200, wav, 'audio/wav');
    state.analyzeCalls++;
    state.analyzeBodies.push(route.request().postDataJSON());
    if (state.delayAnalyzeMs) await new Promise(ok => setTimeout(ok, state.delayAnalyzeMs));
    if (state.analyzeMode === 'fail503') return reply(route, 503, {detail: 'SUMMARY_PROVIDER_UNAVAILABLE'});
    return reply(route, 200, SUMMARY);
  });
  await target.route(/\/api\/mental-neural-speech/, async route => {
    if (route.request().method() === 'OPTIONS') return route.fulfill({status: 204, headers: CORS});
    let body = {};
    try { body = JSON.parse(route.request().postData() || '{}'); } catch {}
    state.speechRequests.push({language: body.language, speakerProfile: body.speakerProfile});
    const locale = body.language === 'tr' ? 'tr-TR' : body.language === 'de' ? 'de-DE' : 'en-US';
    return reply(route, 200, wav, 'audio/wav', {...CORS, 'X-TTS-Source': 'chatterbox-multilingual-v3', 'X-TTS-Locale': locale, ...(body.speakerProfile ? {'X-TTS-Speaker-Profile': body.speakerProfile} : {})});
  });
  return state;
}
module.exports = {install, CORS, SUMMARY};
