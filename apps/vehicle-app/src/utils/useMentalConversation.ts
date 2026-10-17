'use client';

import { spokenText } from './spokenText';
import { streamSpeech } from './streamSpeech';

import { useEffect, useRef, useState } from 'react';
import { checkCrisisTrigger } from '@packages/safety/crisisDetector';
import { isMicrophoneAllowed, isMentalSummarySavingAllowed, isMentalTranscriptSavingAllowed, isDemoMode } from './attuneMode';
import { MentalHistoryItem, readMentalHistory, saveMentalHistory } from './mentalHistory';
import { prepareHealthRecords } from './healthRecords';
import { localBackend } from './localBackend';

export type ConversationPhase = 'ready' | 'paused' | 'permission' | 'listening' | 'preparing' | 'speaking' | 'ending' | 'completed' | 'error';
export interface ConversationMessage {
  id: string; turn: number; sender: 'USER' | 'AI'; text: string; time: string;
  timestamp?: string; completed: boolean; isCrisis?: boolean; providerBadge?: string;
}
type PendingTurn={user:ConversationMessage;prior:{role:string;content:string}[]};
const API = localBackend('/api/mental');
const LABELS: Record<string, string> = {
  'not-allowed': 'Ses girişine izin verilmedi. Tarayıcı mikrofon iznini kontrol edin.',
  'service-not-allowed': 'Konuşma tanıma servisine izin verilmiyor.',
  'audio-capture': 'Mikrofona erişilemiyor.', network: 'Konuşma tanıma servisine ulaşılamadı.',
  'language-not-supported': 'Türkçe konuşma tanıma bu ortamda desteklenmiyor.'
};

export function useMentalConversation(parked: boolean) {
  const [phase, setPhase] = useState<ConversationPhase>('ready');
  const [active, setActive] = useState(false);
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [notice, setNotice] = useState<string | null>(null);
  const [voiceNotice, setVoiceNotice] = useState<string | null>(null);
  const [voiceState, setVoiceState] = useState('loading');
  const [textMode, setTextMode] = useState(false);
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const [cloudConsent, setCloudConsent] = useState(false);
  const [speechConsent, setSpeechConsent] = useState(false);
  const speechSource = 'microsoft' as const;
  const [history, setHistory] = useState<MentalHistoryItem[]>([]);
  const [summary, setSummary] = useState<MentalHistoryItem | null>(null);
  const [provider, setProvider] = useState({ apiKeyConfigured: false, providerName: 'Yerel Kural Motoru (Demo)' });
  const runtime = useRef({ mounted: false, active: false, paused: false, pendingPause: false, pendingFinish: false, epoch: 0, turn: 0, busy: false, failed: false,
    id: '', startedAt: '', transcript: [] as ConversationMessage[], pendingTurn:null as PendingTurn|null, pendingSpeech:null as {text:string;crisis:boolean}|null, recognition: null as any,
    audio: null as HTMLAudioElement | null,
    audioUrl: null as string | null, streamCancel: null as (()=>void) | null, controller: null as AbortController | null,
    restart: null as ReturnType<typeof setTimeout> | null, audioEpoch: 0, voiceWaiting: false });
  const settings = useRef({ parked, textMode, voiceEnabled, cloudConsent, speechConsent, speechSource });
  settings.current = { parked, textMode, voiceEnabled, cloudConsent, speechConsent, speechSource };
  const actions = useRef({ listen: () => {}, cancel: (_reason?: string) => {}, send: (_text: string) => {}, audioOff: () => {} });

  // Content-free observation only: no storage or telemetry.
  function timing(stage:string,bytes?:number) { window.dispatchEvent(new CustomEvent('attune-speech-timing',{detail:{stage,atMs:performance.now(),clock:'browser-performance',turn:runtime.current.turn,bytes}})); }
  function abortRecognition() {
    const r = runtime.current;
    const recognition = r.recognition;
    r.recognition = null; // Identity gate invalidates every late native event.
    if (recognition) { try { recognition.abort(); } catch {} }
  }
  function stopAudio() {
    const r = runtime.current;
    r.audioEpoch++;
    r.streamCancel?.(); r.streamCancel = null;
    if (r.audio) { r.audio.onplaying = r.audio.onended = r.audio.onerror = null; r.audio.pause(); r.audio.removeAttribute('src'); r.audio.load(); r.audio = null; }
    if (r.audioUrl) { URL.revokeObjectURL(r.audioUrl); r.audioUrl = null; }
    r.voiceWaiting = false;timing('cleanup');
  }
  function cleanup() {
    const r = runtime.current;
    if (r.restart) clearTimeout(r.restart);
    r.restart = null;
    abortRecognition(); stopAudio(); r.controller?.abort(); r.controller = null;
  }
  function valid(epoch: number) {
    const r = runtime.current;
    return r.mounted && r.epoch === epoch && r.active && settings.current.parked && settings.current.speechConsent;
  }
  function resume(epoch: number) {
    if (!valid(epoch)) return;
    runtime.current.busy = false;
    if (runtime.current.pendingFinish) { runtime.current.pendingFinish = false; void finish(); return; }
    if (runtime.current.pendingPause) { pause(); return; }
    if (runtime.current.paused) { setPhase('paused'); return; }
    if (runtime.current.pendingTurn) { const pending=runtime.current.pendingTurn;void send(pending.user.text,pending);return; }
    if (runtime.current.pendingSpeech) { const pending=runtime.current.pendingSpeech;runtime.current.busy=true;void speak(pending.text,epoch,pending.crisis);return; }
    if (settings.current.textMode) { setPhase('ready'); return; }
    // Allow output device and recognition teardown to settle before capture starts.
    runtime.current.restart = setTimeout(() => { if (valid(epoch)) actions.current.listen(); }, 350);
  }
  function cancel(reason?: string) {
    const r = runtime.current;
    r.epoch++; r.active = false; r.busy = false; r.failed = true;
    r.pendingTurn=null;r.pendingSpeech=null;
    cleanup();
    if (r.mounted) { setActive(false); setVoiceState('ready'); setPhase(reason ? 'error' : 'ready'); if (reason) setNotice(reason); }
  }
  function listen() {
    const r = runtime.current, epoch = r.epoch;
    if (!valid(epoch) || r.paused || r.busy || r.recognition || r.voiceWaiting) return;
    if (!isMicrophoneAllowed() || !settings.current.speechConsent) {
      setTextMode(true); setPhase('ready'); setNotice(!isMicrophoneAllowed() ? 'Mikrofon kullanım izni Gizlilik ayarlarında kapalıdır. Yazarak devam edebilirsiniz.' : 'Ses aktarım izni kapalı. Yazarak devam edebilirsiniz.'); return;
    }
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) { setTextMode(true); setPhase('ready'); setNotice('Bu tarayıcı konuşma tanımayı desteklemiyor. Yazarak devam edebilirsiniz.'); return; }
    const recognition = new SR(); r.recognition = recognition;
    recognition.lang = 'tr-TR'; recognition.continuous = false; recognition.interimResults = false;
    let accepted = false, failed = false;
    const current = () => valid(epoch) && r.recognition === recognition && isMicrophoneAllowed() && settings.current.speechConsent;
    recognition.onstart = () => { if (current()) { setPhase('listening'); setNotice(null); } else abortRecognition(); };
    recognition.onresult = (event: any) => {
      if (!current() || accepted || r.busy || r.voiceWaiting) return;
      const index = event.resultIndex || 0;
      if (event.results[index]?.isFinal === false) return;
      const transcript = event.results[index]?.[0]?.transcript?.trim();
      if (!transcript) return;
      accepted = true; abortRecognition(); actions.current.send(transcript);
    };
    recognition.onerror = (event: any) => {
      if (!current()) return;
      if (event.error === 'no-speech') return;
      failed = true; abortRecognition(); setTextMode(true); setPhase('ready');
      setNotice((LABELS[event.error] || 'Konuşma tanıma başarısız.') + ' Yazarak devam edebilirsiniz.');
    };
    recognition.onend = () => {
      if (!current()) return;
      r.recognition = null;
      if (!accepted && !failed && !r.busy) resume(epoch);
    };
    setPhase('permission');
    try { recognition.start(); } catch { abortRecognition(); setTextMode(true); setPhase('ready'); setNotice('Mikrofon başlatılamadı. Yazarak devam edebilirsiniz.'); }
  }
  async function speak(text: string, epoch: number, crisis: boolean) {
    const r = runtime.current;
    if (!valid(epoch)) return;
    setVoiceNotice(null);
    if (!settings.current.voiceEnabled) { r.pendingSpeech=null;if (crisis) { r.active = false; r.busy = false; setActive(false); setPhase('error'); } else resume(epoch); return; }
    r.pendingSpeech={text,crisis};
    abortRecognition(); stopAudio();
    const audioEpoch = r.audioEpoch;
    const current = () => valid(epoch) && r.audioEpoch === audioEpoch;
    r.voiceWaiting = true;
    const end = () => { if (!current()) return; r.pendingSpeech=null;timing('ended');stopAudio(); setVoiceState('ready'); if (!crisis) resume(epoch); else { r.active = false; setActive(false); setPhase('error'); } };
    const fail = () => { if (!current()) return; r.pendingSpeech=null;timing('audio-error');stopAudio(); setVoiceState('failed'); setVoiceNotice('Microsoft tr-TR-EmelNeural seslendirmesine ulaşılamadı. Sesli yanıt başarısız. Yanıtı metin olarak okuyabilirsiniz.'); setTextMode(true); r.busy = false; setPhase('ready'); if (r.pendingFinish) { r.pendingFinish=false; void finish(); } else if (r.pendingPause) pause(); if (crisis) { r.active = false; setActive(false); setPhase('error'); } };
    setVoiceState('loadingSpeech');
    {
      if (!settings.current.speechConsent) { fail(); return; }
      const controller = new AbortController(); r.controller = controller;
      const deadline = setTimeout(() => controller.abort(), 30000);
      try {
        timing('tts-request');
        const response = await fetch(API + '/speech', { method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text, cloudConsent: true }), signal: controller.signal });
        timing('tts-headers');
        if (!response.ok) throw new Error('Microsoft exact voice unavailable');
        if (!current()) { await response.body?.cancel(); return; }
        setVoiceState('starting');
        const audio = new Audio(); r.audio = audio;
        audio.onplaying = () => { if (current()) { timing('playing');setPhase('speaking'); setVoiceState('speaking'); } };
        audio.onended = end; audio.onerror = fail;
        const output = streamSpeech(audio, response, controller.signal, current, timing);
        r.audioUrl = output.url; r.streamCancel = output.cancel;
        await output.finished;
      } catch { fail(); }
      finally { clearTimeout(deadline); if (r.controller === controller) r.controller = null; }
      return;
    }
  }

  function append(message: ConversationMessage) {
    runtime.current.transcript = [...runtime.current.transcript, message];
    setMessages(runtime.current.transcript);
  }
  async function send(value: string, pending?:PendingTurn) {
    const r = runtime.current, epoch = r.epoch, text = value.trim();
    if (!text || !valid(epoch) || r.paused || r.busy || r.voiceWaiting || r.failed) return;
    r.busy = true; abortRecognition();
    const timestamp = new Date().toISOString();
    const turn = pending?pending.user.turn:++r.turn, time = pending?pending.user.time:new Date(timestamp).toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' });
    timing('send');
    const prior = pending?pending.prior:r.transcript.filter(m => m.completed).slice(-40).map(m => ({ role: m.sender === 'USER' ? 'user' : 'assistant', content: m.text }));
    const user: ConversationMessage = pending?pending.user:{ id: `${r.id}-${turn}-user`, turn, sender: 'USER', text, time, timestamp, completed: false };
    r.pendingTurn={user,prior};if(!pending)append(user); setPhase('preparing'); setNotice(null);
    const crisis = checkCrisisTrigger(text, !settings.current.parked);
    const controller = new AbortController(); r.controller = controller;
    const deadline = setTimeout(() => controller.abort(), 30000);
    try {
      let data: any;
      if (crisis.isCrisis) data = { reply: crisis.emergencyResponseTr, isCrisis: true, providerType: 'CRISIS_SAFETY_GUARD' };
      else {
        const response = await fetch(API + '/converse', { method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ userMessage: text, history: prior, sessionId: r.id, cloudConsent: settings.current.cloudConsent }), signal: controller.signal });
        if (!response.ok) throw new Error('Conversation service');
        data = await response.json();
      }
      if (!valid(epoch)) return;
      timing('chat-response');
      if (typeof data.reply !== 'string' || !data.reply.trim()) throw new Error('Invalid reply');
      if (!isDemoMode() && !['LIVE_OPENAI', 'CRISIS_SAFETY_GUARD', 'CONVERSATION_CONTROL'].includes(data.providerType)) throw new Error('Unexpected demo reply');
      r.pendingTurn=null;
      r.transcript = r.transcript.map(m => m.id === user.id ? { ...m, completed: true } : m);
      const badge = data.providerType === 'CONVERSATION_CONTROL' ? 'CONVERSATION_CONTROL — Görüşme kontrolü' : data.providerType === 'LIVE_OPENAI' ? 'LIVE_OPENAI — OpenAI Canlı' : data.providerType === 'CRISIS_SAFETY_GUARD' ? 'Kriz Güvenlik Filtresi' : data.providerType === 'LOCAL_DEMO_FALLBACK' ? 'LOCAL_DEMO_FALLBACK — sağlayıcıya ulaşılamadı' : 'LOCAL_DEMO — Yerel Model';
      append({ id: `${r.id}-${turn}-ai`, turn, sender: 'AI', text: data.reply, time: new Date().toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' }), timestamp: new Date().toISOString(), completed: true, isCrisis: data.isCrisis, providerBadge: badge });
      if (data.providerType === 'LOCAL_DEMO_FALLBACK') setNotice('Canlı sağlayıcıya ulaşılamadı; bu yanıt yerel demo motorundan geldi.');
      if (data.isCrisis) { r.failed = true; setNotice('Normal görüşme durduruldu. Acil Kriz Destek: 112 Acil Çağrı.'); }
      r.pendingPause = !data.isCrisis && data.sessionAction === 'pause';
      r.pendingFinish = !data.isCrisis && data.sessionAction === 'finish';
      await speak(spokenText(data.reply), epoch, !!data.isCrisis);
    } catch {
      if (!valid(epoch)) return;
      r.pendingTurn=null;
      r.failed = true; r.busy = false; setPhase('error');
      append({ id: `${r.id}-${turn}-error`, turn, sender: 'AI', text: 'İyi oluş servisine bağlantı kurulamadı. Bu mesaj için değerlendirme oluşturulamadı. Lütfen daha sonra yeniden deneyin.', time, completed: false, providerBadge: 'Servis Bağlantısı Başarısız' });
      setNotice('İyi oluş servisine bağlantı kurulamadı. Görüşme başarılı kayıt olarak sayılmadı. Lütfen görüşmeyi bitirip daha sonra yeniden deneyin.');
    } finally { clearTimeout(deadline); }
  }
  function start(asText = settings.current.textMode) {
    if (!settings.current.parked || runtime.current.active || !settings.current.speechConsent) return;
    cleanup(); const r = runtime.current;
    r.epoch++; r.active = true; r.paused = false; r.pendingPause = false; r.pendingFinish = false; r.failed = false; r.busy = false; r.turn = 0; r.id = crypto.randomUUID(); r.startedAt = new Date().toISOString(); r.transcript = [];r.pendingTurn=null;r.pendingSpeech=null;
    settings.current.textMode = asText;
    setActive(true); setTextMode(asText); setMessages([]); setSummary(null); setNotice(null); setVoiceNotice(null); setVoiceState('ready'); setPhase('ready');
    if (!asText) listen();
  }
  async function finish() {
    const r = runtime.current;
    if (!r.active) return;
    const failed = r.failed || r.transcript.some(m => !m.completed);
    const completed = r.transcript.filter(m => m.completed);
    const epoch = ++r.epoch; r.active = false; r.busy = false; r.pendingTurn=null;r.pendingSpeech=null;cleanup(); setActive(false); setPhase('ending');
    if (failed || !completed.some(m => m.sender === 'USER')) { setPhase(failed ? 'error' : 'completed'); setNotice('Boş, iptal edilmiş veya başarısız görüşme geçmişe kaydedilmedi.'); return; }
    const controller = new AbortController(); r.controller = controller;
    const deadline = setTimeout(() => controller.abort(), 30000);
    try {
      const response = await fetch(API + '/analyze-session', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: completed.map(m => ({ role: m.sender === 'USER' ? 'user' : 'assistant', content: m.text })), cloudConsent: settings.current.cloudConsent }), signal: controller.signal });
      if (!response.ok) throw new Error('Summary service');
      const data = await response.json();
      if (!r.mounted || r.epoch !== epoch || !settings.current.parked || !settings.current.speechConsent) return;
      if (!isDemoMode() && data.providerType !== 'LIVE_OPENAI') throw new Error('Unexpected demo summary');
      if (typeof data.summaryText !== 'string' || !data.summaryText.trim() || !Array.isArray(data.themes) || !data.themes.every((t: unknown) => typeof t === 'string')) throw new Error('Invalid summary');
      const item: MentalHistoryItem = { id: r.id, date: new Date().toISOString(), summaryText: data.summaryText, themes: data.themes,
        moodTrend: typeof data.moodTrend === 'string' ? data.moodTrend : undefined, moodTrendSource:typeof data.moodTrend==='string'?'assistant-inferred':undefined, providerType: data.providerType, schemaVersion: 3, startedAt: r.startedAt, completedAt: new Date().toISOString(), completed: true, consented: false };
      if (!isDemoMode() && isMentalSummarySavingAllowed()) {
        // This is the last operation before storage. Consent can change during analysis.
        item.consented = true;
        if (isMentalTranscriptSavingAllowed()) { item.transcriptConsented = true; item.transcript = completed.map(m => ({ id:m.id, turn:m.turn, sender:m.sender, text:spokenText(m.text), timestamp:m.timestamp })); }
        const records = await saveMentalHistory(item, () => r.mounted && r.epoch === epoch && settings.current.parked && settings.current.speechConsent);
        if (!r.mounted || r.epoch !== epoch || !settings.current.parked || !settings.current.speechConsent) return;
        setHistory(records); setNotice('Tamamlanan görüşmenin tek özeti kaydedildi.');
      } else setNotice('Özet hazır. Kalıcı saklama izni kapalı; geçmişe kayıt eklenmedi.');
      setSummary(item); setPhase('completed');
    } catch {
      if (r.mounted && r.epoch === epoch) { setPhase('error'); setNotice('Görüşme özeti oluşturulamadı veya kaydedilemedi; başarılı kayıt eklenmedi.'); }
    } finally { clearTimeout(deadline); }
  }
  function pause() {
    const r=runtime.current;if(!r.active)return;
    r.epoch++;cleanup();r.busy=false;r.paused=true;r.pendingPause=false;
    setPhase('paused');setVoiceState('ready');setNotice('Görüşme duraklatıldı. Mikrofon dinlemiyor.');
  }
  function continueConversation() {
    const r=runtime.current;if(!r.active||!r.paused||!settings.current.parked)return;
    r.paused=false;setNotice(null);resume(r.epoch);
  }
  function switchText() {
    settings.current.textMode = true; abortRecognition(); setTextMode(true);
    if (runtime.current.active && !runtime.current.busy && !runtime.current.paused) setPhase('ready');
  }
  actions.current = { listen, cancel, send, audioOff: () => { setVoiceNotice(null); if (runtime.current.voiceWaiting) { const epoch = runtime.current.epoch; runtime.current.controller?.abort(); runtime.current.controller = null; runtime.current.pendingSpeech=null;stopAudio(); setVoiceState('ready'); resume(epoch); } } };
  useEffect(() => {
    const r = runtime.current; r.mounted = true;
    setHistory(readMentalHistory());
    const controller = new AbortController();
    fetch(API + '/provider-status', { signal: controller.signal }).then(res => res.json()).then(data => {
      if (r.mounted) setProvider(data);
    }).catch(() => {});
    setVoiceState('ready'); // Availability is verified by the exact Edge request.
    const revoke = () => {
      if (r.active && !isMicrophoneAllowed() && !settings.current.textMode) actions.current.cancel('Mikrofon izni geri çekildi. Görüşme kapatıldı; yazarak yeni görüşme başlatabilirsiniz.');
      void prepareHealthRecords('mental').then(() => {
        if (!r.mounted) return;
        const records = readMentalHistory(); setHistory(records);
        setSummary(previous => previous?.consented && !records.some(record => record.id === previous.id) ? null : previous);
      }).catch(() => { if (r.mounted) setNotice('Kayıtlı görüşmeler okunamadı; veriler değiştirilmedi.'); });
    };
    window.addEventListener('storage', revoke); window.addEventListener('attune-privacy', revoke); window.addEventListener('attune-records', revoke);
    return () => { r.mounted = false; actions.current.cancel(); controller.abort(); window.removeEventListener('storage', revoke); window.removeEventListener('attune-privacy', revoke); window.removeEventListener('attune-records', revoke); };
  }, []);
  useEffect(() => { if (!parked && (runtime.current.active || phase === 'ending')) actions.current.cancel('Sürüş geçişinde görüşme güvenle kapatıldı. Park ettiğinizde yeni görüşme başlatabilirsiniz.'); }, [parked, phase]);
  useEffect(() => { if (!voiceEnabled) actions.current.audioOff(); }, [voiceEnabled]);
  function changeCloud(value: boolean) { if (!value && (runtime.current.active || phase === 'ending')) cancel('Bulut aktarım izni geri çekildi. Görüşme kapatıldı.'); setCloudConsent(value); }
  function changeSpeech(value: boolean) { if (!value && runtime.current.active) cancel('Ses aktarım izni geri çekildi. Görüşme kapatıldı.'); setSpeechConsent(value); }
  function changeServiceConsent(value: boolean) {
    // Invalidate synchronously: a response can settle before React commits state.
    settings.current.speechConsent = value;
    settings.current.cloudConsent = value && !isDemoMode();
    if (!value) cancel('Hizmet onayı geri çekildi. Görüşme ve ses durduruldu.');
    setSpeechConsent(value); setCloudConsent(value && !isDemoMode());
  }
  return { phase, active, messages, notice, voiceNotice, voiceState, textMode, voiceEnabled, setVoiceEnabled,
    serviceConsent: speechConsent, setServiceConsent: changeServiceConsent,
    cloudConsent, setCloudConsent: changeCloud, speechConsent, setSpeechConsent: changeSpeech, speechSource,
    history, summary, provider, start, finish, send, switchText, pause, continueConversation, cancelConversation: () => cancel('Görüşme başlatma iptal edildi.'), cancelSummary: () => { cancel('Özet hazırlama iptal edildi. Görüşme geçmişe kaydedilmedi.'); setPhase('ready'); } };
}
