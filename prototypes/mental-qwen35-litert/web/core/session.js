// KOL B session core. Same code in the browser page (LiteRT-LM JS adapter) and in the host evaluation (HTTP adapter).
// Safety order per user turn: product crisis check (fixed text, model never called) -> gates -> model -> checks -> speech.
// Every await is followed by an epoch check: a cancelled or superseded turn can never speak later.
import {systemPrompt, spokenLinePrompt, groupsPrompt, FALLBACK_QUESTIONS, CANNOT_HELP, BRIDGE, LINE_RETRY, turnNote} from './prompts.js';
import {stripReasoning, replyIssues, questions, asksForMedicalHelp} from './text.js';
import {parseGroups, writtenSummary} from './summary.js';

export class MentalSession {
  /**
   * @param o.lang 'tr'|'en'|'de'
   * @param o.llm {open(system)->handle, send(handle,text,{maxTokens})->{text,firstTokenMs,totalMs,...}, cancel(handle), close(handle)}
   * @param o.crisis (text, moving) => {isCrisis, emergencyText}   (product checkCrisisTrigger + product translation)
   * @param o.validate async (line, lang, messages) => {line, status}   (product validate_spoken_summary)
   * @param o.speech optional {speak(text,{isCurrent})->Promise<{played,...}>, prepare(text)->Promise<clip>, play(clip,{isCurrent})->Promise, stop()}
   * @param o.gates () => boolean   (parked && consent && service allowed — product guards)
   * @param o.now () => ms
   */
  constructor(o) {
    Object.assign(this, {lang: o.lang, llm: o.llm, crisis: o.crisis, validate: o.validate, speech: o.speech || null,
      gates: o.gates || (() => true), now: o.now || (() => performance.now()), verify: o.verify || null});
    this.epoch = 0; this.active = false; this.failed = false; this.handle = null;
    this.user = []; this.transcript = []; this.asked = []; this.events = []; this.fallbackIndex = 0;
  }
  log(type, data = {}) { this.events.push({t: Math.round(this.now()), type, epoch: this.epoch, ...data}); }
  current(epoch) { return this.active && this.epoch === epoch && this.gates(); }

  async start() {
    this.epoch++; this.active = true; this.failed = false; this.user = []; this.transcript = []; this.asked = [];
    const epoch = this.epoch, t0 = this.now();
    // One fresh Engine per conversation (LiteRT-LM #3165: a reused Engine keeps the previous conversation's state).
    this.handle = await this.llm.open(systemPrompt(this.lang));
    if (this.epoch !== epoch) { await this.llm.close(this.handle); return false; }
    this.log('engine-ready', {ms: Math.round(this.now() - t0), engineCreateMs: this.handle.engineCreateMs});
    return true;
  }

  fallbackQuestion() {
    const list = FALLBACK_QUESTIONS[this.lang];
    for (let k = 0; k < list.length; k++) {
      const q = list[(this.fallbackIndex + k) % list.length];
      if (!this.asked.includes(q)) { this.fallbackIndex += k + 1; return q; }
    }
    return list[this.fallbackIndex++ % list.length];
  }

  /** Handles one finished user utterance. Returns a record; `spoken` is what was (or would be) spoken. */
  async userTurn(text, {moving = false} = {}) {
    const rec = {user: text, tStart: this.now()};
    if (!this.active || this.failed) return {...rec, skipped: 'inactive'};
    const crisis = this.crisis(text, moving);
    if (crisis.isCrisis) {           // existing product path: fixed text, conversation stops, no model call
      this.failed = true; this.user.push(text);
      this.transcript.push({role: 'user', text}, {role: 'assistant', text: crisis.emergencyText, crisis: true});
      this.log('crisis-route');
      if (this.speech && this.gates()) await this.speech.speak(crisis.emergencyText, {isCurrent: () => true, crisis: true});
      return {...rec, crisis: true, spoken: crisis.emergencyText, modelCalled: false};
    }
    const epoch = ++this.epoch;      // a new utterance supersedes any pending reply
    this.user.push(text); this.transcript.push({role: 'user', text});
    let r;
    try { r = await this.llm.send(this.handle, text + turnNote(this.lang, this.asked), {maxTokens: 60}); }
    catch (e) { return {...rec, error: String(e), modelCalled: true}; }
    if (!this.current(epoch) || r.cancelled) { this.log('late-reply-discarded', {text: r.text}); return {...rec, discarded: true, modelCalled: true, raw: r.text}; }
    const raw = stripReasoning(r.text);
    let issues = replyIssues(raw, this.lang, this.asked), spoken = raw, source = 'model';
    if (asksForMedicalHelp(text, this.lang) && issues.includes('advice-or-diagnosis')) { spoken = CANNOT_HELP[this.lang]; source = 'fixed-cannot-help'; }
    else if (issues.length) { spoken = this.fallbackQuestion(); source = 'fixed-fallback'; }
    for (const q of questions(spoken)) this.asked.push(q);
    this.transcript.push({role: 'assistant', text: spoken, source});
    const out = {...rec, raw, spoken, source, issues, firstTokenMs: r.firstTokenMs, modelMs: r.totalMs, bench: r.bench, contextTokens: r.contextTokens, modelCalled: true};
    if (this.speech) {
      const s = await this.speech.speak(spoken, {isCurrent: () => this.current(epoch)});
      out.speech = s;
    }
    out.tEnd = this.now();
    return out;
  }

  /** Cancel (user tap, new utterance, PARK lost, consent withdrawn, page hidden): nothing pending may play later. */
  cancel(reason = 'cancel') {
    this.epoch++; this.log('cancel', {reason});
    try { this.llm.cancel(this.handle); } catch {}
    this.speech?.stop();
  }

  async end(reason = 'end') { this.cancel(reason); this.active = false; if (this.handle) await this.llm.close(this.handle); this.handle = null; }

  /** Closing: bridge clip now; personal line first (validated), written groups afterwards. */
  async finish({verify = !!this.verify} = {}) {
    const epoch = ++this.epoch, T = {trigger: this.now()}, res = {T};
    const userMessages = [...this.user];
    if (this.failed || !userMessages.length) { await this.end('no-summary'); return {...res, summary: null, reason: this.failed ? 'crisis-or-failed' : 'empty'}; }
    this.active = true;
    let bridgeDone = Promise.resolve();
    if (this.speech) { T.bridgeRequested = this.now(); bridgeDone = this.speech.speak(BRIDGE[this.lang], {isCurrent: () => this.current(epoch), prepared: true}).then(s => { T.bridgeEnd = this.now(); res.bridge = s; }); }
    // 1. Personal line.
    const line1 = await this.llm.send(this.handle, spokenLinePrompt(this.lang, userMessages), {maxTokens: 40});
    T.lineText = this.now();
    if (!this.current(epoch)) return {...res, aborted: true};
    const messages = userMessages.map(content => ({role: 'user', content}));
    let candidate = stripReasoning(line1.text).replace(/^["“„«]|["”»]$/g, '').trim();
    let v = await this.validate(candidate, this.lang, messages);
    res.line = {candidate, status: v.status, firstTokenMs: line1.firstTokenMs, modelMs: line1.totalMs};
    if (!v.line) {                   // one bounded retry with the validator's reason; never a third attempt
      const line2 = await this.llm.send(this.handle, LINE_RETRY[v.status] || LINE_RETRY.default, {maxTokens: 40});
      T.lineRetryText = this.now();
      if (!this.current(epoch)) return {...res, aborted: true};
      const c2 = stripReasoning(line2.text).replace(/^["“„«]|["”»]$/g, '').trim();
      v = await this.validate(c2, this.lang, messages);
      Object.assign(res.line, {retryCandidate: c2, retryStatus: v.status, retryMs: line2.totalMs});
    }
    if (v.line && verify) {          // optional on-device grounding check (same conversation, one word)
      const q = await this.verify(this.handle, userMessages, v.line);
      res.line.verifier = q.answer; T.verifierDone = this.now();
      if (q.answer !== 'NO') v = {line: null, status: 'verifier-' + q.answer};
    }
    res.line.accepted = v.line; res.line.finalStatus = v.status;
    let personal = Promise.resolve();
    if (v.line && this.speech) {
      const clip = await this.speech.prepare(v.line); T.lineAudioReady = this.now();
      personal = bridgeDone.then(async () => { if (!this.current(epoch)) return; T.lineAudioStart = this.now(); res.lineSpeech = await this.speech.play(clip, {isCurrent: () => this.current(epoch)}); T.lineAudioEnd = this.now(); });
    }
    // 2. Written groups (starts after the personal line's audio is synthesized: no compute race with it).
    const g = await this.llm.send(this.handle, groupsPrompt(userMessages), {maxTokens: 160});
    T.groupsText = this.now();
    if (!this.current(epoch)) return {...res, aborted: true};
    res.groupsRaw = g.text; res.groupsModelMs = g.totalMs;
    res.summary = writtenSummary(this.lang, userMessages, parseGroups(g.text));
    await Promise.all([bridgeDone, personal]);
    T.done = this.now();
    this.active = false; await this.llm.close(this.handle); this.handle = null;
    return res;
  }
}
