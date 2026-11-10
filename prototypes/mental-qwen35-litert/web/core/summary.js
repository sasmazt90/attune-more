// Written closing summary: the model only sorts the user's own numbered messages into controlled topics; the text
// shown is the user's own words. Nothing the model writes is shown as a fact about the user.
import {TOPICS} from './prompts.js';

const LABELS = {
  'uyku düzeni': {tr: 'Uyku düzeni', en: 'Sleep pattern', de: 'Schlafrhythmus'},
  'iş yaşamı': {tr: 'İş yaşamı', en: 'Working life', de: 'Arbeitsleben'},
  'sosyal ilişkiler': {tr: 'Sosyal ilişkiler', en: 'Social relationships', de: 'Soziale Beziehungen'},
  'fiziksel yorgunluk': {tr: 'Fiziksel yorgunluk', en: 'Physical fatigue', de: 'Körperliche Müdigkeit'},
  'kaygı ve endişe': {tr: 'Kaygı ve endişe', en: 'Anxiety and worry', de: 'Angst und Sorgen'},
  'trafik gerilimi': {tr: 'Trafik gerilimi', en: 'Traffic stress', de: 'Verkehrsstress'},
  'günlük iyi oluş paylaşımı': {tr: 'Günlük iyi oluş paylaşımı', en: 'Daily wellbeing sharing', de: 'Austausch zum täglichen Wohlbefinden'},
};
const OTHER = {tr: 'Söylediğin diğer şeyler', en: 'Other things you said', de: 'Weiteres, das Sie gesagt haben'};
const APOLOGY = {tr: /^(pardon|özür dilerim|kusura bakma)[,.!\s]+/iu, en: /^(sorry|oh sorry|apologies)[,.!\s]+/iu, de: /^(entschuldigung|sorry|verzeihung)[,.!\s]+/iu};

export function parseGroups(raw) {
  const text = String(raw || '').replace(/<think>[\s\S]*?<\/think>/gi, '');
  const start = text.indexOf('{');
  if (start < 0) return {ok: false, error: 'no-json'};
  let depth = 0, inStr = false, esc = false;
  for (let i = start; i < text.length; i++) {          // first balanced object; trailing text ignored
    const c = text[i];
    if (inStr) { if (esc) esc = false; else if (c === '\\') esc = true; else if (c === '"') inStr = false; continue; }
    if (c === '"') inStr = true; else if (c === '{') depth++; else if (c === '}' && --depth === 0) {
      try { return {ok: true, value: JSON.parse(text.slice(start, i + 1))}; } catch { return {ok: false, error: 'bad-json'}; }
    }
  }
  return {ok: false, error: 'unclosed-json'};
}
// A correction counts only when a later message carries an explicit correction cue.
const CUE = {
  tr: /^(pardon|özür dilerim|kusura bakma|aslında|hayır|yok)\b|\bdeğil\s*,/iu,
  en: /^(sorry|apologies|actually|no,)|\bnot\b[^.]*\b(it was|but)\b|\bwasn'?t\b[^.]*\bit was\b/iu,
  de: /^(entschuldigung|verzeihung|sorry|eigentlich|nein,)|\bnicht\b[^.]*\bsondern\b/iu,
};

/** Builds the written summary. Returns {groups, replaced, issues}. Never invents text: quotes only. */
export function writtenSummary(lang, userMessages, parsed) {
  const n = userMessages.length, issues = [];
  const valid = i => Number.isInteger(i) && i >= 1 && i <= n;
  const corrected = new Set();
  const cueAfter = i => userMessages.some((m, k) => k + 1 > i && CUE[lang].test(m.trim()));
  if (parsed?.ok && Array.isArray(parsed.value.corrected)) for (const i of parsed.value.corrected) {
    if (!valid(i)) issues.push('bad-corrected-index'); else if (cueAfter(i)) corrected.add(i); else issues.push('corrected-without-cue:' + i);
  }
  // Deterministic addition: an apology at the start of a message corrects the user's previous message.
  userMessages.forEach((m, k) => { if (k > 0 && APOLOGY[lang].test(m.trim())) corrected.add(k); });
  const seen = new Set(), groups = [];
  let topics = parsed?.ok ? parsed.value.topics : [];
  if (topics && !Array.isArray(topics) && typeof topics === 'object') {   // tolerated shape: {"work":[1,2]} or {"work":[{"topic":"work","messages":[1]}]}
    issues.push('map-shape');
    topics = Object.entries(topics).flatMap(([k, v]) => Array.isArray(v) && v.every(Number.isInteger) ? [{topic: k, messages: v}] : Array.isArray(v) ? v.filter(x => x && typeof x === 'object') : []);
  }
  if (!Array.isArray(topics)) topics = [];
  if (!parsed?.ok) issues.push('groups-unavailable:' + (parsed?.error || 'none'));
  for (const t of topics) {
    const key = TOPICS[t?.topic];
    if (!key) { issues.push('unknown-topic:' + t?.topic); continue; }
    const ids = (Array.isArray(t.messages) ? t.messages : []).filter(i => { if (!valid(i)) { issues.push('bad-index'); return false; } return !seen.has(i) && !corrected.has(i); });
    ids.forEach(i => seen.add(i));
    if (!ids.length) continue;
    let g = groups.find(x => x.theme === key);
    if (!g) groups.push(g = {theme: key, label: LABELS[key][lang], quotes: []});
    for (const i of ids) g.quotes.push({turn: i, text: userMessages[i - 1].trim().replace(APOLOGY[lang], '').replace(/^\p{Ll}/u, c => c.toLocaleUpperCase(lang))});
  }
  const rest = [];
  for (let i = 1; i <= n; i++) if (!seen.has(i) && !corrected.has(i)) rest.push({turn: i, text: userMessages[i - 1].trim().replace(APOLOGY[lang], '')});
  if (rest.length) groups.push({theme: null, label: OTHER[lang], quotes: rest});
  for (const g of groups) g.quotes.sort((a, b) => a.turn - b.turn);
  return {groups, replaced: [...corrected].sort((a, b) => a - b).map(i => ({turn: i, text: userMessages[i - 1]})), issues};
}

/** Message counts per group, as counts. A percentage is not a measured share and is not produced here. */
export function groupCounts(summary) {
  return summary.groups.map(g => ({label: g.label, theme: g.theme, userMessages: g.quotes.length}));
}
