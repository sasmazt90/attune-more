// Deterministic checks on model text. No model call here.
export function stripReasoning(text) {
  return String(text || '').replace(/<think>[\s\S]*?<\/think>/gi, '').replace(/<\/?think>/gi, '').replace(/\s+/g, ' ').trim();
}
export function sentences(text) {
  return (text.match(/[^.!?…]+[.!?…]+|[^.!?…]+$/g) || []).map(s => s.trim()).filter(Boolean);
}
export function questions(text) { return sentences(text).filter(s => s.endsWith('?')); }
export function norm(text, lang) {
  const lower = lang === 'tr' ? text.toLocaleLowerCase('tr-TR') : text.toLowerCase();
  return lower.normalize('NFC').replace(/[^\p{L}\p{N}\s]/gu, ' ').replace(/\s+/g, ' ').trim();
}
export function similar(a, b, lang) {
  const A = new Set(norm(a, lang).split(' ')), B = new Set(norm(b, lang).split(' '));
  const inter = [...A].filter(x => B.has(x)).length;
  return inter / Math.max(1, Math.min(A.size, B.size));
}
const STOP = {
  tr: ['ve', 'bir', 'bu', 'çok', 'mi', 'mı', 'mu', 'mü', 'ne', 'için', 'ile', 'sen', 'seni', 'sana', 'senin', 'nasıl', 'değil', 'ama', 'daha', 'olarak', 'gibi', 'misin', 'musun', 'neler', 'şey'],
  en: ['the', 'and', 'you', 'your', 'is', 'are', 'to', 'of', 'a', 'that', 'it', 'what', 'how', 'do', 'with', 'about', 'this', 'for', 'was', 'have'],
  de: ['und', 'die', 'der', 'das', 'sie', 'ihnen', 'ihr', 'ist', 'nicht', 'mit', 'ein', 'eine', 'wie', 'was', 'zu', 'es', 'sich', 'auf', 'haben', 'über'],
};
export function languageOf(text) {
  const words = norm(text, 'tr').split(' ');
  const score = Object.fromEntries(Object.entries(STOP).map(([l, s]) => [l, words.filter(w => s.includes(w)).length]));
  if (/[ğışİ]/.test(text)) score.tr += 2;
  if (/[äöüß]/.test(text) && !/[ğış]/.test(text)) score.de += 1;
  return score;
}
export function languageOk(text, lang) { const s = languageOf(text); return s[lang] >= Math.max(...Object.values(s)); }
// Medication/diagnosis/advice markers in a REPLY (prototype guard; the product validator covers the closing line).
const ADVICE = {
  tr: /(ilaç\w* (al|kullan|öner)|\bmg\b|anksiyete bozukluğun|bozukluğun (var|olabilir)|teşhis|tanın (var|olabilir)|yapmalısın|etmelisin|denemelisin|öneririm|tavsiye ederim)/iu,
  en: /(you (should|could try|might want)|i (recommend|suggest)|\bmg\b|you (have|may have|might have) (an? )?(anxiety|depress|disorder)|diagnos(is|ed) (is|of)|take (some )?(medication|pills))/iu,
  de: /(sie sollten|ich empfehle|empfehle ihnen|\bmg\b|sie haben (eine|vielleicht eine) (angststörung|depression|störung)|diagnose ist|nehmen sie)/iu,
};
export function replyIssues(reply, lang, asked) {
  const issues = [];
  if (!reply) issues.push('empty');
  const s = sentences(reply), q = questions(reply);
  if (s.length > 2) issues.push('too-many-sentences');
  if (q.length > 1) issues.push('more-than-one-question');
  if (reply && norm(reply, lang).split(' ').length >= 4 && !languageOk(reply, lang)) issues.push('wrong-language');
  if (reply && !q.length) issues.push('no-question');
  if (ADVICE[lang].test(reply)) issues.push('advice-or-diagnosis');
  for (const prev of asked) for (const cur of q) if (similar(prev, cur, lang) >= 0.8) issues.push('repeated-question');
  if (/[*#•]|^\s*-\s/m.test(reply) || /\p{Extended_Pictographic}/u.test(reply)) issues.push('formatting');
  return [...new Set(issues)];
}
const REQUEST = {
  tr: /(ilaç|tanı|teşhis|bozukluğ)/iu, en: /(medication|medicine|pill|diagnos|disorder)/iu, de: /(medikament|tablette|diagnose|störung)/iu,
};
export function asksForMedicalHelp(userText, lang) { return REQUEST[lang].test(userText); }
