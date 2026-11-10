// Prompts of the KOL B prototype. Instructions are in English (more reliable for a 2B model); output language is
// fixed per session. Kept in one place so the browser page and the host evaluation send identical text.
export const LANG = {
  tr: {name: 'Turkish', address: 'Address the user informally as "sen".', recapForm: 'a Turkish sentence ending with "söz ettin." whose topic words are in the ablative case'},
  en: {name: 'English', address: 'Address the user as "you".', recapForm: 'an English sentence starting with "You talked about"'},
  de: {name: 'German', address: 'Address the user formally with "Sie".', recapForm: 'a German sentence starting with "Sie sprachen über"'},
};

const EXAMPLE = {  // neutral examples, not from the evaluation corpus
  tr: ['Bugün işten erken çıktım.', 'Anlıyorum. Akşamın nasıl geçti?'],
  en: ['I left work early today.', 'I see. How did your evening go?'],
  de: ['Ich bin heute früher von der Arbeit gegangen.', 'Verstehe. Wie war Ihr Abend?'],
};
export function systemPrompt(lang) {
  const L = LANG[lang], [u, a] = EXAMPLE[lang];
  return [
    `You are a calm listening companion in a parked car. The user talks about their day and how they are doing. Reply in ${L.name} only. ${L.address}`,
    'Reply with a very short acknowledgement of one to three words, then one short open question (at most 12 words) about something the user just said. Do not restate, summarise or interpret what the user said.',
    'Rules:',
    '- Use only what the user said. Do not add people, causes, feelings, events, times or places the user did not mention. Keep who did what to whom exactly as the user said it. If the user says something is not the case, never say that it is. Keep past and present apart.',
    '- No judgements or comments such as "that is okay", "that sounds hard", "that is normal" or "that is good".',
    '- If the user corrects something, use the corrected version from then on.',
    '- Never give advice, diagnoses or medication names. If the user asks for medication or a diagnosis, say that you cannot help with that and that a doctor can. If the user asks about something unrelated, say that you cannot help with that here.',
    '- Each question must be about something new; never ask the same question twice, and do not keep asking how the user feels.',
    '- Plain spoken text: no lists, no emojis, no explanations.',
    `Example. User: "${u}" You: "${a}"`,
  ].join('\n');
}

const LINE_EXAMPLES = {  // neutral examples, not from the evaluation corpus
  tr: [['Trafikte çok sinirlendim. Akşam hiçbir şey yapmak istemedim.', 'Trafikteki sinirden ve akşam hiçbir şey yapmak istemediğinden söz ettin.'],
       ['Ders çalışırken odaklanamıyorum.', 'Ders çalışırken odaklanamamaktan söz ettin.']],
  en: [['Traffic made me angry. In the evening I did not want to do anything.', 'You talked about traffic making you angry and not wanting to do anything.'],
       ['I cannot focus while studying.', 'You talked about not being able to focus while studying.']],
  de: [['Der Verkehr hat mich geärgert. Abends wollte ich nichts machen.', 'Sie sprachen über Ärger im Verkehr und dass Sie abends nichts machen wollten.'],
       ['Beim Lernen kann ich mich nicht konzentrieren.', 'Sie sprachen darüber, dass Sie sich beim Lernen nicht konzentrieren können.']],
};
export const LINE_RETRY = {
  'too-many-words': 'That sentence is too long. Write it again with at most 8 words, same form.',
  'not-recap-form': 'That sentence does not have the required form. Write it again in exactly the required form.',
  default: 'That sentence was refused. Write it again using only the user\'s own words, same form, at most 8 words.',
};
export function spokenLinePrompt(lang, userMessages) {
  const L = LANG[lang];
  return [
    'The conversation is over. Do not ask anything.',
    `Write one recap sentence in ${L.name}: ${L.recapForm}`,
    'Use the user\'s own words for one or two of the main things they said. At most 10 words. Keep negations. No advice, no evaluation, no "my"/"I". Do not add any person, thing, cause, feeling or time.',
    ...LINE_EXAMPLES[lang].map(([u, a]) => `Example: the user said "${u}" -> ${a}`),
    'The user said:',
    ...userMessages.map((m, i) => `${i + 1}. ${m}`),
    'Output only the sentence.',
  ].join('\n');
}

// Language-neutral topic ids mapped to the product's controlled theme keys (shared/localization/mental-themes.json).
export const TOPICS = {
  sleep: 'uyku düzeni', work: 'iş yaşamı', relationships: 'sosyal ilişkiler', tiredness: 'fiziksel yorgunluk',
  anxiety: 'kaygı ve endişe', traffic: 'trafik gerilimi', wellbeing: 'günlük iyi oluş paylaşımı',
};

const TOPIC_HINTS = 'sleep = sleep or rest at night; work = job, colleagues, meetings, school; relationships = family, friends, partner, neighbours, team; ' +
  'tiredness = being tired or low energy; anxiety = worry, fear, panic, tension, nervousness, anger; traffic = traffic, driving, commuting; ' +
  'wellbeing = things that felt good, leisure, hobbies, everyday life.';
export function groupsPrompt(userMessages) {
  return [
    'Now sort the user\'s messages into topics. The user\'s messages are:',
    ...userMessages.map((m, i) => `${i + 1}. ${m}`),
    `Allowed topics: ${TOPIC_HINTS}`,
    'Put every message into the one topic it fits best. "corrected" lists only messages that a later message explicitly corrects (for example "sorry, not X but Y"); usually it is empty.',
    'Reply with one JSON object only, exactly in this shape: {"topics":[{"topic":"work","messages":[1,3]},{"topic":"sleep","messages":[2]}],"corrected":[]}',
  ].join('\n');
}

export function verifierPrompt(userMessages, line) {
  return [
    'The user said:',
    ...userMessages.map(m => `- ${m}`),
    `Proposed recap: "${line}"`,
    'Does the recap add a person, thing, cause, feeling, event or time the user did not mention, change who did what to whom, or drop or reverse a negation? Answer with exactly one word: YES or NO.',
  ].join('\n');
}
export const VERIFIER_SYSTEM = 'You check short recaps for faithfulness to what a user said. You answer only YES or NO.';

// Fixed texts used instead of a model reply when that reply fails a check (prototype wording; not product-approved).
export const FALLBACK_QUESTIONS = {
  tr: ['Bunu biraz daha anlatmak ister misin?', 'Bu sana nasıl hissettiriyor?', 'Başka neler oldu?', 'Şu an en çok ne aklında?'],
  en: ['Would you like to tell me a bit more about that?', 'How does that feel for you?', 'What else happened?', 'What is on your mind most right now?'],
  de: ['Möchten Sie mir etwas mehr darüber erzählen?', 'Wie fühlt sich das für Sie an?', 'Was ist noch passiert?', 'Was beschäftigt Sie gerade am meisten?'],
};
export const CANNOT_HELP = {
  tr: 'Bu konuda yardımcı olamam; ilaç ve tanı için bir doktorla konuşabilirsin.',
  en: 'I cannot help with that; a doctor can talk with you about medication or a diagnosis.',
  de: 'Dabei kann ich nicht helfen; über Medikamente oder eine Diagnose kann ein Arzt mit Ihnen sprechen.',
};
export const BRIDGE = {  // spoken at the start of the closing, synthesized once with the prototype voice
  tr: 'Teşekkür ederim. Konuştuklarımızı toparlıyorum.',
  en: 'Thank you. I am putting together what we talked about.',
  de: 'Vielen Dank. Ich fasse zusammen, worüber wir gesprochen haben.',
};

// Per-turn note appended to the user's message inside the model context (never shown or spoken). Small models copy
// their previous question; naming the questions already asked reduces that.
export function turnNote(lang, asked) {
  const prev = asked.length ? ` Questions you already asked: ${asked.slice(-4).map(q => `"${q}"`).join(', ')}. Ask something different.` : '';
  return `\n\n(Note for you, not from the user: reply in ${LANG[lang].name} with a one-to-three-word acknowledgement and one new short question about this message.${prev})`;
}
