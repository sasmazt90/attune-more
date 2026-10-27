'use client';
import {apiFetch as fetch} from './localBackend';
import {getLocale,getLanguage,t} from '../i18n/core';

import {contextWindowThrough} from './mentalContextWindow';
import {serviceAllowed,useServiceAllowed} from './serviceConsent';
import {speechMuted} from './playbackMeter';
import { spokenText } from './spokenText';
import {canonicalMentalTheme} from '../i18n/mentalThemes';
import {mentalSystemSpeech} from '../i18n/systemSpeech';
import {mentalNeuralSpeech,mentalSpeechEngine} from './mentalNeuralSpeech';
import {approvedMentalTemplate} from '../i18n/approvedAudio';
import {playFixedSpeech} from './fixedFileSpeech';
import {playPreparedMental,structuredConversationEnabled,type StructuredState} from './mentalPreparedSpeech';
import {cancelQueuedSessionSpeech} from '../i18n/sessionSpeech';

import { useCallback, useEffect, useRef, useState } from 'react';
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
  'language-not-supported': 'Seçilen dilde konuşma tanıma bu ortamda desteklenmiyor.'
};

export function useMentalConversation(parked: boolean) {
  const [phase, setPhaseState] = useState<ConversationPhase>('ready');
  const phaseRef=useRef<ConversationPhase>('ready');
  const setPhase=useCallback((value:ConversationPhase)=>{phaseRef.current=value;setPhaseState(value);},[]);
  const [active, setActive] = useState(false);
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [notice, setNotice] = useState<string | null>(null);
  const [voiceNotice, setVoiceNotice] = useState<string | null>(null);
  const pendingAudioPlay=useRef<(()=>void)|null>(null);
  const [audioNeedsGesture,setAudioNeedsGesture]=useState(false);
  const [voiceState, setVoiceState] = useState('loading');
  const serviceConsent=useServiceAllowed('mental');
  const textMode=false;
  const [voiceEnabled, setVoiceEnabled] = useState(!speechMuted());
  const [cloudConsent, setCloudConsent] = useState(false);
  const [speechConsent, setSpeechConsent] = useState(false);
  const [historyConsent,setHistoryConsent]=useState(false);
  const historyPermission=useRef(false);historyPermission.current=historyConsent;
  const speechSource = mentalSpeechEngine();
  const [history, setHistory] = useState<MentalHistoryItem[]>([]);
  const [summary, setSummary] = useState<MentalHistoryItem | null>(null);
  const [provider, setProvider] = useState({ apiKeyConfigured: false, providerName: 'Yerel Kural Motoru (Demo)' });
  const runtime = useRef({ mounted: false, active: false, paused: false, pendingPause: false, pendingFinish: false, epoch: 0, turn: 0, busy: false, failed: false,
    structured:false,structuredState:null as StructuredState|null,
    memory:[] as string[], memoryThrough:0, id: '', startedAt: '', transcript: [] as ConversationMessage[], pendingTurn:null as PendingTurn|null, pendingSpeech:null as {text:string;crisis:boolean;assetIds?:string[]}|null, recognition: null as any,
    audio: null as HTMLAudioElement | null,
    audioUrl: null as string | null, streamCancel: null as (()=>void) | null, controller: null as AbortController | null,
    restart: null as ReturnType<typeof setTimeout> | null, audioEpoch: 0, voiceWaiting: false });
  const settings = useRef({ parked, textMode, voiceEnabled, cloudConsent, speechConsent, speechSource });
  settings.current = { parked, textMode, voiceEnabled, cloudConsent, speechConsent, speechSource };
  const actions = useRef({ listen: () => {}, cancel: (_reason?: string) => {}, send: (_text: string) => {}, audioOff: () => {}, pause: () => {}, consent: (_value:boolean) => {} });

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
    pendingAudioPlay.current=null;if(r.mounted)setAudioNeedsGesture(false);
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
    return r.mounted && r.epoch === epoch && r.active && settings.current.parked && settings.current.speechConsent && serviceAllowed('mental');
  }
  function resume(epoch: number) {
    if (!valid(epoch)) return;
    runtime.current.busy = false;
    if (runtime.current.pendingFinish) { runtime.current.pendingFinish = false; void finish(); return; }
    if (runtime.current.pendingPause) { pause(); return; }
    if (runtime.current.paused) { setPhase('paused'); return; }
    if (runtime.current.pendingTurn) { const pending=runtime.current.pendingTurn;void send(pending.user.text,pending);return; }
    if (runtime.current.pendingSpeech) { const pending=runtime.current.pendingSpeech;runtime.current.busy=true;void speak(pending.text,epoch,pending.crisis,pending.assetIds);return; }
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
      cancel('Sesli görüşme için mikrofon ve hizmet işleme izni gerekiyor.'); return;
    }
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) { cancel('Bu tarayıcı seçilen dilde sesli görüşmeyi desteklemiyor.'); return; }
    const recognition = new SR(); r.recognition = recognition;
    recognition.lang = getLocale(); recognition.continuous = false; recognition.interimResults = false;
    let accepted = false, failed = false;
    const current = () => valid(epoch) && r.recognition === recognition && isMicrophoneAllowed() && settings.current.speechConsent && serviceAllowed('mental');
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
      failed = true; cancel(LABELS[event.error] || 'Konuşma tanıma başarısız. Sesli görüşme durduruldu.');
    };
    recognition.onend = () => {
      if (!current()) return;
      r.recognition = null;
      if (!accepted && !failed && !r.busy) resume(epoch);
    };
    setPhase('permission');
    try { recognition.start(); } catch { cancel('Mikrofon başlatılamadı. Sesli görüşme durduruldu.'); }
  }
  async function speak(text: string, epoch: number, crisis: boolean, assetIds?:string[]) {
    const r = runtime.current;
    if (!valid(epoch)) return;
    setVoiceNotice(null);
    if (!settings.current.voiceEnabled) { r.pendingSpeech=null;if (crisis) { r.active = false; r.busy = false; setActive(false); setPhase('error'); } else resume(epoch); return; }
    r.pendingSpeech={text,crisis,assetIds};
    abortRecognition(); stopAudio();
    const audioEpoch = r.audioEpoch;
    const current = () => valid(epoch) && r.audioEpoch === audioEpoch;
    r.voiceWaiting = true;
    const end = () => { if (!current()) return; r.pendingSpeech=null;timing('ended');stopAudio(); setVoiceState('ready'); if (!crisis) resume(epoch); else { r.active = false; setActive(false); setPhase('error'); } };
    const fail = () => { if (!current()) return; timing('audio-error');cancel(crisis?t('Normal görüşme durduruldu. Acil Kriz Destek: 112 Acil Çağrı.'):'Seçilen dil veya ses kullanılamıyor. Sesli görüşme durduruldu; dil ve ses seçeneklerini kontrol edin.');setVoiceState('failed'); };
    setVoiceState('loadingSpeech');
    {
      if (!settings.current.speechConsent) { fail(); return; }
      const controller = new AbortController(); r.controller = controller;
      // Neural generation/playback own their separate finite deadlines. The
      // former 100s cap would abort measured 135–153s responses before playback.
      const deadline = crisis||mentalSpeechEngine()==='browser-system'||approvedMentalTemplate(getLanguage(),text)
        ?setTimeout(() => controller.abort(), crisis?30000:100000):undefined;
      try {
        if(r.structured&&!crisis){
          const played=await playPreparedMental(text,assetIds||[],controller.signal,()=>current()&&settings.current.voiceEnabled&&settings.current.speechConsent,audio=>{r.audio=audio;},stage=>{if(current()){timing(stage);if(stage==='playing'){setPhase('speaking');setVoiceState('speaking');}}});
          if(played)end();else fail();return;
        }
        const clip=approvedMentalTemplate(getLanguage(),text);
        if(clip){
          const audio=new Audio();r.audio=audio;audio.dataset.recordingId=clip.recordingId;
          const played=await playFixedSpeech(audio,clip,controller.signal,current,stage=>{if(current()){timing(stage);if(stage==='playing'){setPhase('speaking');setVoiceState('speaking');}}},true);
          if(played)end();else fail();return;
        }
        timing('tts-request');
        r.streamCancel=()=>controller.abort();
        const observePlaying=()=>{if(current()){timing('playing');setPhase('speaking');setVoiceState('speaking');}};
        // Emergency text is already visible and routed locally. Never wait for
        // optional neural generation, nor transmit a crisis message to it.
        if(crisis){fail();return;}
        const played=mentalSpeechEngine()==='browser-system'
          ?await mentalSystemSpeech(text,controller.signal,()=>current()&&settings.current.voiceEnabled,observePlaying)
          :await mentalNeuralSpeech(text,controller.signal,()=>current()&&settings.current.voiceEnabled&&settings.current.speechConsent,observePlaying,audio=>{r.audio=audio;},{
            requestGesture:play=>{
              if(!current())return()=>{};
              pendingAudioPlay.current=play;setAudioNeedsGesture(true);
              return()=>{if(pendingAudioPlay.current===play){pendingAudioPlay.current=null;if(r.mounted)setAudioNeedsGesture(false);}};
            },observe:stage=>timing(stage),
          });
        if(played)end();else fail();
      } catch { fail(); }
      finally { clearTimeout(deadline); if (r.controller === controller) r.controller = null; }
      return;
    }
  }

  async function updateContext(epoch:number,completed:ConversationMessage[]) {
    const r=runtime.current;
    if(r.structured)return; // One complete bounded transcript, no per-turn cloud compaction.
    const through=contextWindowThrough(completed,r.memoryThrough);
    if(through===r.memoryThrough)return;
    const controller=new AbortController();r.controller=controller;
    const deadline=setTimeout(()=>controller.abort(),30000);
    try {
      const response=await fetch(API+'/compact-context',{method:'POST',headers:{'Content-Type':'application/json'},signal:controller.signal,
        body:JSON.stringify({memory:r.memory,messages:completed.slice(r.memoryThrough,through).map(m=>({role:m.sender==='USER'?'user':'assistant',content:m.text})),cloudConsent:settings.current.cloudConsent})});
      if(!response.ok)throw Error();const data=await response.json();
      if(!r.mounted||r.epoch!==epoch||!serviceAllowed('mental'))throw Error();
      if(!Array.isArray(data.memory)||data.method!=='extractive-user-quotes-v1'||data.memory.some((q:unknown)=>typeof q!=='string'))throw Error();
      r.memory=data.memory;r.memoryThrough=through;
    }catch{throw Error('CONTEXT_UPDATE_FAILED');}
    finally{clearTimeout(deadline);if(r.controller===controller)r.controller=null;}
  }
  function append(message: ConversationMessage) {
    runtime.current.transcript = [...runtime.current.transcript, message];
    setMessages(runtime.current.transcript);
  }
  async function send(value: string, pending?:PendingTurn) {
    const r = runtime.current, epoch = r.epoch, text = value.trim();
    if (!text || !valid(epoch) || r.paused || r.busy || r.voiceWaiting || r.failed) return;
    const crisis = checkCrisisTrigger(text, !settings.current.parked);
    const finishAtBoundary=r.structured&&!pending&&!crisis.isCrisis&&(r.turn>=39||r.transcript.reduce((n,m)=>n+m.text.length,0)+text.length>100000);
    r.busy = true; abortRecognition();
    const timestamp = new Date().toISOString();
    const turn = pending?pending.user.turn:++r.turn, time = pending?pending.user.time:new Date(timestamp).toLocaleTimeString(getLocale(), { hour: '2-digit', minute: '2-digit' });
    timing('send');
    let prior = pending?pending.prior:r.transcript.filter(m => m.completed).slice(r.memoryThrough).map(m => ({ role: m.sender === 'USER' ? 'user' : 'assistant', content: m.text }));
    const user: ConversationMessage = pending?pending.user:{ id: `${r.id}-${turn}-user`, turn, sender: 'USER', text, time, timestamp, completed: false };
    if(finishAtBoundary){append({...user,completed:true});r.pendingTurn=null;r.busy=false;await finish();return;}
    r.pendingTurn={user,prior};if(!pending)append(user); setPhase('preparing'); setNotice(null);
    const controller = new AbortController(); r.controller = controller;
    let deadline:ReturnType<typeof setTimeout>|undefined;
    try {
      // Local emergency routing must not wait for optional context compaction
      // or an unavailable network/provider after a long conversation.
      if(!crisis.isCrisis)await updateContext(epoch,r.transcript.filter(m=>m.completed));
      if(!valid(epoch))return;
      prior=r.transcript.filter(m=>m.completed).slice(r.memoryThrough).map(m=>({role:m.sender==='USER'?'user':'assistant',content:m.text}));
      if(r.pendingTurn)r.pendingTurn.prior=prior;
      r.controller=controller;deadline=setTimeout(()=>controller.abort(),30000);
      let data: any;
      if (crisis.isCrisis) data = { reply: t(crisis.emergencyResponseTr||''), isCrisis: true, providerType: 'CRISIS_SAFETY_GUARD' };
      else {
        const response = await fetch(API + '/converse', { method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ userMessage: text, history: r.structured?[]:prior, memory:r.structured?[]:r.memory, sessionId: r.id, cloudConsent: settings.current.cloudConsent,...(r.structured?{engine:'structured-v1',structuredState:r.structuredState,finishAfterReply:r.turn>=39||r.transcript.reduce((n,m)=>n+m.text.length,0)>=94000}:{}) }), signal: controller.signal });
        if (!response.ok){const error=await response.json().catch(()=>({}));throw new Error(r.structured&&String(error.detail).startsWith('STRUCTURED_')?'STRUCTURED_UNAVAILABLE':'Conversation service');}
        data = await response.json();
      }
      if (!valid(epoch)) return;
      timing('chat-response');
      if (typeof data.reply !== 'string' || !data.reply.trim()) throw new Error('Invalid reply');
      if (!isDemoMode() && !['LIVE_OPENAI', 'CRISIS_SAFETY_GUARD', 'CONVERSATION_CONTROL',...(r.structured?['STRUCTURED_LOCAL']:[])].includes(data.providerType)) throw new Error('Unexpected demo reply');
      if(r.structured&&!data.isCrisis){
        if(data.providerType!=='STRUCTURED_LOCAL'||!data.structuredState||data.structuredState.language!==getLanguage()||data.structuredState.speakerProfile!=='official-default'||!Array.isArray(data.audioAssetIds))throw Error('Invalid structured reply');
        r.structuredState=data.structuredState;
      }
      r.pendingTurn=null;
      r.transcript = r.transcript.map(m => m.id === user.id ? { ...m, completed: true } : m);
      const badge = data.providerType === 'STRUCTURED_LOCAL' ? 'STRUCTURED_LOCAL' : data.providerType === 'CONVERSATION_CONTROL' ? 'CONVERSATION_CONTROL — Görüşme kontrolü' : data.providerType === 'LIVE_OPENAI' ? 'LIVE_OPENAI — OpenAI Canlı' : data.providerType === 'CRISIS_SAFETY_GUARD' ? 'Kriz Güvenlik Filtresi' : data.providerType === 'LOCAL_DEMO_FALLBACK' ? 'LOCAL_DEMO_FALLBACK — sağlayıcıya ulaşılamadı' : 'LOCAL_DEMO — Yerel Model';
      append({ id: `${r.id}-${turn}-ai`, turn, sender: 'AI', text: data.reply, time: new Date().toLocaleTimeString(getLocale(), { hour: '2-digit', minute: '2-digit' }), timestamp: new Date().toISOString(), completed: true, isCrisis: data.isCrisis, providerBadge: badge });
      if (data.providerType === 'LOCAL_DEMO_FALLBACK') setNotice('Canlı sağlayıcıya ulaşılamadı; bu yanıt yerel demo motorundan geldi.');
      if (data.isCrisis) { r.failed = true; setNotice('Normal görüşme durduruldu. Acil Kriz Destek: 112 Acil Çağrı.'); }
      r.pendingPause = !data.isCrisis && data.sessionAction === 'pause';
      r.pendingFinish = !data.isCrisis && data.sessionAction === 'finish';
      await speak(spokenText(data.reply), epoch, !!data.isCrisis,data.audioAssetIds);
    } catch (error) {
      if (!valid(epoch)) return;
      if((error as Error).message==='CONTEXT_UPDATE_FAILED'){r.busy=false;r.paused=true;setPhase('paused');setNotice('Oturum belleği güncellenemedi. Önceki bağlam korundu; Devam et ile yeniden deneyebilirsiniz.');return;}
      r.pendingTurn=null;
      r.failed = true; r.busy = false; setPhase('error');
      if((error as Error).message==='STRUCTURED_UNAVAILABLE'){setNotice(t('Hazır görüşme henüz kullanıma açık değil; içerik ve ses onayı gerekiyor.'));return;}
      append({ id: `${r.id}-${turn}-error`, turn, sender: 'AI', text: 'İyi oluş servisine bağlantı kurulamadı. Bu mesaj için değerlendirme oluşturulamadı. Lütfen daha sonra yeniden deneyin.', time, completed: false, providerBadge: 'Servis Bağlantısı Başarısız' });
      setNotice('İyi oluş servisine bağlantı kurulamadı. Görüşme başarılı kayıt olarak sayılmadı. Lütfen görüşmeyi bitirip daha sonra yeniden deneyin.');
    } finally { clearTimeout(deadline); }
  }
  function start() {
    if (!settings.current.parked || runtime.current.active || !settings.current.speechConsent || !serviceAllowed('mental')) return;
    if(structuredConversationEnabled()&&mentalSpeechEngine()!=='chatterbox-v3'){setNotice(t('Hazır görüşme için Chatterbox sesini seçin.'));return;}
    cleanup(); const r = runtime.current;
    r.epoch++; r.active = true; r.paused = false; r.pendingPause = false; r.pendingFinish = false; r.failed = false; r.busy = false; r.turn = 0; r.id = crypto.randomUUID(); r.startedAt = new Date().toISOString(); r.transcript = [];r.memory=[];r.memoryThrough=0;r.pendingTurn=null;r.pendingSpeech=null;
    r.structured=structuredConversationEnabled();r.structuredState=r.structured?{language:getLanguage(),speakerProfile:'official-default',listenOnly:false,turn:0,seed:crypto.getRandomValues(new Uint32Array(1))[0]}:null;
    settings.current.textMode = false;
    setActive(true); setMessages([]); setSummary(null); setNotice(null); setVoiceNotice(null); setVoiceState('ready'); setPhase('ready');
    listen();
  }
  async function finish() {
    const r = runtime.current;
    if (!r.active) return;
    const failed = r.failed || r.transcript.some(m => !m.completed);
    const completed = r.transcript.filter(m => m.completed);
    const epoch = ++r.epoch; r.active = false; r.busy = false; r.pendingTurn=null;r.pendingSpeech=null;cleanup(); setActive(false); setPhase('ending');
    if (failed || !completed.some(m => m.sender === 'USER')) { setPhase(failed ? 'error' : 'completed'); setNotice('Boş, iptal edilmiş veya başarısız görüşme geçmişe kaydedilmedi.'); return; }
    const controller = new AbortController(); r.controller = controller;
    let deadline:ReturnType<typeof setTimeout>|undefined;
    try {
      await updateContext(epoch,completed);
      if(!r.mounted||r.epoch!==epoch||!serviceAllowed('mental'))return;
      r.controller=controller;deadline=setTimeout(()=>controller.abort(),30000);
      const response = await fetch(API + '/analyze-session', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ memory:r.memory, messages: completed.slice(r.memoryThrough).map(m => ({ role: m.sender === 'USER' ? 'user' : 'assistant', content: m.text })), cloudConsent: settings.current.cloudConsent,
          ...(r.structured?{engine:'structured-v1',noAdvice:!!r.structuredState?.listenOnly,historyConsent:historyPermission.current,
            priorSessions:historyPermission.current&&settings.current.cloudConsent&&isMentalSummarySavingAllowed()?readMentalHistory().filter(h=>h.id!==r.id&&h.completed&&h.consented&&[2,3].includes(h.schemaVersion||0)).slice(-5).map(h=>({id:h.id,summaryText:h.summaryText.slice(0,2000),themes:h.themes.slice(0,12)})):[]}:{}) }), signal: controller.signal });
      if (!response.ok) throw new Error('Summary service');
      const data = await response.json();
      if (!r.mounted || r.epoch !== epoch || !settings.current.parked || !settings.current.speechConsent || !serviceAllowed('mental')) return;
      if (!isDemoMode() && data.providerType !== 'LIVE_OPENAI') throw new Error('Unexpected demo summary');
      if (typeof data.summaryText !== 'string' || !data.summaryText.trim() || !Array.isArray(data.themes) || !data.themes.every((t: unknown) => typeof t === 'string')) throw new Error('Invalid summary');
      if(r.structured&&(typeof data.spokenSummary!=='string'||!data.spokenSummary.trim()))throw Error('Invalid spoken summary');
      const item: MentalHistoryItem = { id: r.id, date: new Date().toISOString(), summaryText: data.summaryText, themes: data.themes.map(canonicalMentalTheme),
        moodTrend: typeof data.moodTrend === 'string' ? data.moodTrend : undefined, moodTrendSource:typeof data.moodTrend==='string'?'assistant-inferred':undefined, providerType: data.providerType, schemaVersion: 3, startedAt: r.startedAt, completedAt: new Date().toISOString(), completed: true, consented: false };
      if(r.structured){item.recommendations=data.recommendations;item.relatedSessionIds=data.relatedSessionIds;item.recurringThemes=data.recurringThemes;
        item.structuredFlow={contentVersion:'v1',speakerProfile:'official-default',seed:r.structuredState?.seed,selections:r.structuredState?.selections||[]};}
      if (!isDemoMode() && isMentalSummarySavingAllowed()) {
        // This is the last operation before storage. Consent can change during analysis.
        item.consented = true;
        if (isMentalTranscriptSavingAllowed()) { item.transcriptConsented = true; item.transcript = completed.map(m => ({ id:m.id, turn:m.turn, sender:m.sender, text:spokenText(m.text), timestamp:m.timestamp })); }
        const records = await saveMentalHistory(item, () => r.mounted && r.epoch === epoch && settings.current.parked && settings.current.speechConsent && serviceAllowed('mental'));
        if (!r.mounted || r.epoch !== epoch || !settings.current.parked || !settings.current.speechConsent || !serviceAllowed('mental')) return;
        setHistory(records); setNotice('Tamamlanan görüşmenin tek özeti kaydedildi.');
      } else setNotice('Özet hazır. Kalıcı saklama izni kapalı; geçmişe kayıt eklenmedi.');
      setSummary(item);
      if(r.structured){clearTimeout(deadline);await speakClosing(data.spokenSummary,epoch);}
      if(r.mounted&&r.epoch===epoch)setPhase('completed');
    } catch {
      if (r.mounted && r.epoch === epoch) { setPhase('error'); setNotice('Görüşme özeti oluşturulamadı veya kaydedilemedi; başarılı kayıt eklenmedi.'); }
    } finally { clearTimeout(deadline); }
  }
  async function speakClosing(text:string,epoch:number){
    const r=runtime.current,language=getLanguage(),controller=new AbortController();
    const current=()=>r.mounted&&r.epoch===epoch&&settings.current.parked&&settings.current.speechConsent&&settings.current.cloudConsent&&settings.current.voiceEnabled&&serviceAllowed('mental')&&getLanguage()===language;
    if(!current())return;
    r.controller=controller;
    try{
      const played=await mentalNeuralSpeech(text,controller.signal,current,()=>setVoiceState('speaking'),audio=>{r.audio=audio;},{speakerProfile:'official-default',observe:stage=>timing(stage),requestGesture:play=>{if(!current())return()=>{};pendingAudioPlay.current=play;setAudioNeedsGesture(true);return()=>{if(pendingAudioPlay.current===play){pendingAudioPlay.current=null;if(r.mounted)setAudioNeedsGesture(false);}};}});
      if(!played&&current())setVoiceNotice(t('Özet hazır; kapanış sesi oynatılamadı.'));
    }catch{if(current())setVoiceNotice(t('Özet hazır; kapanış sesi oynatılamadı.'));}
    finally{if(r.controller===controller)r.controller=null;if(r.epoch===epoch){stopAudio();if(r.mounted)setVoiceState('ready');}}
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
  actions.current = { listen, cancel, send, pause, consent: changeServiceConsent, audioOff: () => { setVoiceNotice(null); if (runtime.current.voiceWaiting) { const epoch = runtime.current.epoch; runtime.current.controller?.abort(); runtime.current.controller = null; runtime.current.pendingSpeech=null;stopAudio(); setVoiceState('ready'); resume(epoch); } } };
  useEffect(() => {
    const r = runtime.current; r.mounted = true;
    setHistory(readMentalHistory());
    const controller = new AbortController();
    fetch(API + '/provider-status', { signal: controller.signal }).then(res => res.json()).then(data => {
      if (r.mounted) setProvider(data);
    }).catch(() => {});
    setVoiceState('ready'); // Availability is verified by the exact Edge request.
    const revoke = () => {
      if(r.structured&&phaseRef.current==='ending'&&historyPermission.current&&!isMentalSummarySavingAllowed())actions.current.cancel(t('Geçmiş işleme izni geri çekildi.'));
      if ((r.active || phaseRef.current === 'ending') && !serviceAllowed('mental')) actions.current.cancel('Hizmet izni geri çekildi.');
      if (r.active && !isMicrophoneAllowed() && !settings.current.textMode) actions.current.cancel('Mikrofon izni geri çekildi. Sesli görüşme kapatıldı.');
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
  useEffect(()=>{const hidden=()=>{if(document.hidden&&runtime.current.active)actions.current.pause();};document.addEventListener('visibilitychange',hidden);return()=>document.removeEventListener('visibilitychange',hidden);},[]);
  useEffect(()=>{const changed=()=>{if(runtime.current.structured&&(runtime.current.active||phaseRef.current==='ending')){actions.current.cancel(t('Dil veya ses değişti. Yeni bir görüşme başlatın.'));return;}cancelQueuedSessionSpeech(runtime.current,{
    pause:()=>actions.current.pause(),
    crisis:()=>actions.current.cancel('Normal görüşme durduruldu. Acil Kriz Destek: 112 Acil Çağrı.'),
    notice:()=>setNotice('Dil veya ses değişti. Konuşma metni korundu; eski seslendirme yeniden başlatılmaz. Devam et ile sürdürebilirsiniz.'),
  });};window.addEventListener('attune-locale-media-cancel',changed);return()=>window.removeEventListener('attune-locale-media-cancel',changed);},[]);
  useEffect(()=>{actions.current.consent(serviceConsent);},[serviceConsent]);
  useEffect(()=>{const changed=()=>setVoiceEnabled(!speechMuted());window.addEventListener('attune-guidance-muted',changed);return()=>window.removeEventListener('attune-guidance-muted',changed);},[]);
  function changeCloud(value: boolean) { if (!value && (runtime.current.active || phase === 'ending')) cancel('Bulut aktarım izni geri çekildi. Görüşme kapatıldı.'); setCloudConsent(value); }
  function changeSpeech(value: boolean) { if (!value && runtime.current.active) cancel('Ses aktarım izni geri çekildi. Görüşme kapatıldı.'); setSpeechConsent(value); }
  function changeServiceConsent(value: boolean) {
    // Invalidate synchronously: a response can settle before React commits state.
    settings.current.speechConsent = value;
    settings.current.cloudConsent = value && !isDemoMode();
    if (!value) cancel('Hizmet onayı geri çekildi. Görüşme ve ses durduruldu.');
    setSpeechConsent(value); setCloudConsent(value && !isDemoMode());
  }
  return { phase, active, messages, notice, voiceNotice, voiceState, audioNeedsGesture, playPendingAudio:()=>pendingAudioPlay.current?.(), textMode, voiceEnabled, setVoiceEnabled,
    structuredMode:structuredConversationEnabled(),historyConsent,setHistoryConsent:(value:boolean)=>{historyPermission.current=value;if(!value&&phaseRef.current==='ending')cancel(t('Geçmiş işleme izni geri çekildi.'));setHistoryConsent(value);},
    serviceConsent: speechConsent, setServiceConsent: changeServiceConsent,
    cloudConsent, setCloudConsent: changeCloud, speechConsent, setSpeechConsent: changeSpeech, speechSource,
    history, summary, provider, start, finish, send, pause, continueConversation, cancelConversation: () => cancel('Görüşme başlatma iptal edildi.'), cancelSummary: () => { cancel('Özet hazırlama iptal edildi. Görüşme geçmişe kaydedilmedi.'); setPhase('ready'); } };
}
