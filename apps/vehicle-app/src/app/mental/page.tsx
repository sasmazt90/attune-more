'use client';
import {useLocaleSwitchLock} from '../../i18n/useLocaleSwitchLock';
import {canonicalMentalTheme} from '../../i18n/mentalThemes';
import {getLocale} from '../../i18n/core';
import {useTranslations} from '../../i18n/LanguageProvider';

import { PRODUCT_NAME } from '../../utils/brand';
import {HealthStartCard,HEALTH_START_ACTION} from '../../components/HealthStartCard';
import { careHref,HEALTH_MODULES } from '../../utils/healthModules';
import { useGuidance } from '../../utils/audioGuidance';

import React, { useEffect, useRef, useState } from 'react';
import { Mic, MicOff, HeartPulse } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useVehicle } from '../../context/VehicleContext';
import { useMentalConversation } from '../../utils/useMentalConversation';
import { mentalThemeStats, translateMood } from '../../utils/mentalHistory';
import { isDemoMode, STORAGE_KEYS } from '../../utils/attuneMode';
import { RecordHistory } from '../../components/RecordHistory';
import { spokenText } from '../../utils/spokenText';
import { AccessibleDialog } from '../../components/AccessibleDialog';
import { InformationButton } from '../../components/InformationButton';

const PHASES = { ready: 'Hazır', paused: 'Duraklatıldı', permission: 'Mikrofon başlatılıyor', listening: 'Dinliyor', preparing: 'Yanıt hazırlanıyor', speaking: 'Seslendiriliyor', ending: 'Bitiriliyor', completed: 'Tamamlandı', error: 'Hata' };
const COLORS = ['#00c2e7', '#a78bfa', '#fb923c', '#4ade80', '#f472b6', '#facc15'];

export default function MentalPage() {
 const {text:i18nText,node:i18nNode}=useTranslations();
  const { isParked } = useVehicle();
  const router = useRouter();
  const c = useMentalConversation(isParked);
  useLocaleSwitchLock('mental',(c.active&&c.phase!=='paused')||c.phase==='ending');
  const guidance=useGuidance('mental',isParked&&c.voiceEnabled);
  useEffect(()=>{if(!c.active&&isParked&&c.voiceEnabled&&['ready','completed'].includes(c.phase))guidance.phase(c.phase,c.phase==='completed'?'mental-complete':'mental-entry');else guidance.cancel();},[guidance,c.phase,c.active,c.voiceEnabled,isParked]);
  const [completionOpen, setCompletionOpen] = useState(false);
  useEffect(() => { if (c.phase === 'completed') setCompletionOpen(true); else setCompletionOpen(false); }, [c.phase]);
  const [theme, setTheme] = useState<string | null>(null);
  const [demo, setDemo] = useState(false);
  useEffect(() => setDemo(isDemoMode()), []);
  const transcript = useRef<HTMLDivElement>(null);
  const follow = useRef(true);
  const stats = mentalThemeStats(c.history);
  useEffect(() => {
    if (follow.current && transcript.current) transcript.current.scrollTop = transcript.current.scrollHeight;
  }, [c.messages, c.phase]);
  const referral = () => {
    const demo = isDemoMode();
    try { localStorage.setItem(demo ? STORAGE_KEYS.DEMO_REFERRAL : STORAGE_KEYS.REFERRAL_CONTEXT, JSON.stringify({
      sourceModule: 'MENTAL', specialty: 'Klinik Psikoloji', reasonSummary: 'Kullanıcının klinik psikolog seçeneklerini inceleme talebi.',
      timestamp: new Date().toISOString(), isDemo: demo, metricsSummary: { recurringThemes: [...new Set(c.history.flatMap(h => h.themes.map(canonicalMentalTheme)))] }
    })); } catch {}
    router.push(careHref('mental') + (demo ? '&demo=1' : ''));
  };
  let angle = 0;
  const gradient = stats.rows.map((row, i) => { const start = angle; angle += row.percent * 3.6; return `${COLORS[i % COLORS.length]} ${start}deg ${angle}deg`; }).join(', ');

  const conversationTranscript = <div ref={transcript} data-conversation-transcript className="max-h-[28rem] overflow-y-auto space-y-3" onScroll={() => { const el = transcript.current; if (el) follow.current = el.scrollHeight - el.scrollTop - el.clientHeight < 60; }}>
        {!c.messages.length && <p className="text-sm text-slate-400">{i18nText("Görüşmeyi başlattığınızda sesli konuşabilirsiniz.")}</p>}
        {c.messages.map((m, i) => <article key={m.id} data-chat-author={m.sender} data-chat-position={i} data-turn={m.turn} className={`rounded-xl border p-3 text-sm ${m.isCrisis ? 'border-rose-500 bg-rose-950' : m.sender === 'USER' ? 'border-togg-turquoise/30 bg-togg-darkBlue' : 'border-white/10 bg-slate-950'}`}><p className="text-xs text-slate-400">{i18nNode(m.sender === 'USER' ? 'Siz' : PRODUCT_NAME)} · {i18nNode(m.timestamp&&Number.isFinite(Date.parse(m.timestamp))?new Date(m.timestamp).toLocaleTimeString(getLocale(),{hour:'2-digit',minute:'2-digit'}):m.time)}</p><p className="mt-1 whitespace-pre-line break-words">{spokenText(m.text)}</p><span data-provider-kind={m.providerBadge?.split(" ")[0]} /></article>)}
  </div>;

  return <div className={c.phase==='ready'?'space-y-6 max-w-5xl mx-auto':'grid grid-cols-1 lg:grid-cols-2 gap-6 items-start'}>
    {c.phase==='ready'&&<div className="flex items-center gap-2"><h1 className="text-2xl font-bold">{i18nNode(HEALTH_MODULES.mental.name)}</h1><InformationButton title={i18nText(HEALTH_MODULES.mental.name)}><p>{i18nText("Park halinde sesli görüşebilirsiniz. Bu hizmet klinik tanı veya acil yardım hizmeti değildir.")}</p></InformationButton></div>}
    <section className={c.phase==='ready'?undefined:'bg-cockpit-surface border border-white/10 rounded-2xl p-6 space-y-5'}>
      {demo && <p className="text-amber-200">{i18nText("Demo / Örnek içerik — gerçek görüşme geçmişiniz değildir.")}</p>}
      {c.phase==='ready'?<HealthStartCard module="mental" actions={<button onClick={()=>{guidance.cancel();return c.start();}} disabled={!isParked||!c.serviceConsent} className={HEALTH_START_ACTION}><span className="flex items-center gap-2 justify-center"><Mic className="h-5 w-5"/>{i18nText("Görüşmeyi Başlat")}</span></button>}/>:<>
      <div className="flex items-center gap-2 text-togg-turquoise"><HeartPulse /><span>{i18nNode(HEALTH_MODULES.mental.name)}</span></div>
      <div className="flex items-center gap-2"><h1 className="text-2xl font-bold">{i18nText("Bugün nasıl hissediyorsunuz?")}</h1><InformationButton title={i18nText(HEALTH_MODULES.mental.name)}><p>{i18nText("Park halinde sesli konuşabilirsiniz. Bu hizmet klinik tanı ve acil yardım hizmeti değildir. Sesli yanıt yapay zekâ tarafından üretilir.")}</p></InformationButton></div>
      <p className="text-sm text-slate-300">{i18nText("Park halinde sesli görüşebilirsiniz. Bu hizmet klinik tanı veya acil yardım hizmeti değildir.")}</p>
      <div className="flex gap-3">
        <button onClick={() => {guidance.cancel();return c.active ? c.phase === 'permission' && !c.messages.length ? c.cancelConversation() : void c.finish() : c.start();}} disabled={!isParked || c.phase === 'ending' || (!c.active && !c.serviceConsent)} className="flex-1 bg-togg-turquoise text-togg-darkBlue font-bold p-4 rounded-xl disabled:bg-slate-800 disabled:text-slate-400 disabled:cursor-not-allowed flex gap-2 justify-center items-center">{c.active ? <MicOff /> : <Mic />}<span>{i18nNode(c.active ? c.phase === 'permission' && !c.messages.length ? 'Başlatmayı iptal et' : 'Görüşmeyi Bitir' : 'Görüşmeyi Başlat')}</span></button>
      </div>
      </>}
      {c.active && <button onClick={c.phase==='paused'?c.continueConversation:c.pause} className="min-h-11 px-4 rounded-xl border border-white/20">{i18nNode(c.phase==='paused'?'Devam et':'Duraklat')}</button>}
      <div data-conversation-phase={c.phase} data-voice-state={c.voiceState} aria-label={c.phase==='speaking'?i18nText('Sesli yanıt oynatılıyor'):undefined} aria-live="polite">
        {!['ready','completed','speaking'].includes(c.phase) && <p className="text-sm text-togg-turquoise">{i18nNode(c.phase === 'preparing' && ['loadingSpeech','starting'].includes(c.voiceState) ? 'Ses hazırlanıyor' : PHASES[c.phase])}</p>}
        {c.voiceState === 'failed' && <p className="text-xs text-amber-200">{i18nText("Sesli yanıt başarısız")}</p>}
      </div>
      {c.phase === 'ending' && <button onClick={c.cancelSummary} className="block w-fit text-sm px-3 py-2 rounded-xl border border-togg-turquoise text-togg-turquoise">{i18nText("Özet hazırlamayı iptal et")}</button>}
      {c.voiceNotice && <p role="status" className="text-xs text-amber-200">{i18nNode(c.voiceNotice)}</p>}
      {c.audioNeedsGesture && <button data-neural-play-response onClick={c.playPendingAudio} disabled={!isParked||(!c.active&&c.phase!=='ending')||!c.speechConsent} className="min-h-11 px-4 py-3 rounded-xl bg-togg-turquoise text-togg-darkBlue font-bold disabled:opacity-50">{i18nText('Sesli yanıtı oynat')}</button>}
      {c.notice && c.phase !== 'completed' && <p role="status" className="text-sm text-amber-200">{i18nNode(c.notice)}</p>}
      {!isParked && <p className="text-amber-200">{i18nText("Sürüş sırasında görüşme kapalıdır. Lütfen dikkatinizi yola verin.")}</p>}
      <p className="text-xs">{i18nText("Acil Kriz Destek: ")}<strong>{i18nText("112 Acil Çağrı")}</strong></p>
    </section>
    {c.structuredMode&&c.summary&&isParked&&<section data-mental-current-summary className="bg-cockpit-surface border border-white/10 rounded-2xl p-6 space-y-3"><h2 className="font-bold">{i18nText('Özet')}</h2><p>{c.summary.summaryText}</p>{!!c.summary.recommendations?.length&&<ul className="list-disc pl-5">{c.summary.recommendations.map((recommendation,index)=><li key={index}>{recommendation}</li>)}</ul>}</section>}
    {!c.active && c.messages.some(m => m.sender === 'AI' && m.isCrisis) && <section role="alert" aria-label={i18nText("Acil destek yanıtı")} className="rounded-2xl border border-rose-500 bg-rose-950 p-6"><h2 className="font-bold mb-3">{i18nText("Acil destek")}</h2>{c.messages.filter(m => m.sender === 'AI' && m.isCrisis).slice(-1).map(m => <article key={m.id} data-chat-author="AI" data-turn={m.turn}><p className="text-xs text-rose-200">{i18nNode(PRODUCT_NAME)} · {i18nNode(m.timestamp&&Number.isFinite(Date.parse(m.timestamp))?new Date(m.timestamp).toLocaleTimeString(getLocale(),{hour:'2-digit',minute:'2-digit'}):m.time)}</p><p className="whitespace-pre-line break-words mt-2">{spokenText(m.text)}</p></article>)}</section>}
    {c.active && isParked && <section data-live-transcript className="bg-cockpit-surface border border-white/10 rounded-2xl p-6 space-y-5"><h2 className="font-bold">{i18nText("Görüşme Akışı")}</h2>{i18nNode(conversationTranscript)}<button onClick={referral} className="text-togg-turquoise font-bold text-sm">{i18nText("PSİKOLOG SEÇENEKLERİNİ GÖR")}</button></section>}
    {!c.active && isParked && !demo && <section data-mental-history className="bg-cockpit-surface border border-white/10 rounded-2xl p-6 space-y-5">
      <div className="flex items-center gap-2"><h2 className="font-bold">{i18nText("Seans temaları")}</h2><InformationButton title={i18nText("Seans temaları")}><p>{i18nText("Bu grafik tanı veya ölçülmüş stres düzeyi değildir; tamamlanmış ve saklama izinli görüşmelerdeki tema paylarını gösterir. Çok temalı görüşmeler her farklı temaya bir kez katkı verir; yüzdeler toplamı 100 olacak şekilde yuvarlanır. Tamamlanma ve izin bilgisi doğrulanamayan eski kayıtlar grafiğe katılmaz.")}</p></InformationButton></div>

      {!stats.mentions ? <p>{i18nText("Henüz tema verisi yok.")}</p> : <>
        <div className="flex flex-wrap gap-4 items-center"><div role="img" aria-label={i18nText("Görüşme tema payları")} className="w-32 h-32 shrink-0 rounded-full" style={{ background: `conic-gradient(${gradient})` }} /><div className="space-y-2">{stats.rows.map((r, i) => <button key={r.theme} onClick={() => setTheme(r.theme)} aria-pressed={theme === r.theme} className="block text-xs text-left rounded-lg px-2 py-1 hover:bg-white/5"><span style={{ color: COLORS[i % COLORS.length] }}>● </span>{i18nNode(r.theme)}: %{i18nNode(r.percent)} ({i18nNode(r.count)}/{i18nNode(stats.mentions)}{i18nText(" tema kaydı)")}</button>)}</div></div>
        <p className="text-xs">{i18nNode(stats.sessions)}{i18nText(" tamamlanmış izinli görüşme · ")}{i18nNode(stats.mentions)}{i18nText(" tema kaydı.")}</p>
        {theme && <div data-selected-theme><h3 className="font-bold">{i18nNode(theme)}</h3>{c.history.filter(h => [2,3].includes(h.schemaVersion || 0) && h.completed && h.consented && h.themes.some(value=>canonicalMentalTheme(value)===theme)).map(h => <p className="text-sm mt-2" key={h.id}>{translateMood(h.summaryText)}</p>)}</div>}
      </>}

      {c.active && <p className="text-xs text-slate-400">{i18nText("Bu görüşme bitmeden yeni özet veya geçmiş kaydı oluşturulmaz.")}</p>}

      <button onClick={referral} className="text-togg-turquoise font-bold text-sm">{i18nText("PSİKOLOG SEÇENEKLERİNİ GÖR")}</button>
    </section>}

    {!demo && <section data-mental-record-panel className="lg:col-span-2 min-w-0 bg-cockpit-surface border border-white/10 rounded-2xl p-6"><RecordHistory category="mental" parked={isParked} /></section>}
    {completionOpen && <AccessibleDialog title={i18nText("Görüşme tamamlandı")} onClose={() => setCompletionOpen(false)} className="max-w-lg w-full rounded-2xl bg-cockpit-surface border border-white/20 p-6 space-y-4"><h2 className="font-bold text-xl">{i18nText("Görüşme tamamlandı")}</h2><p role="status">{i18nNode(c.notice)}</p><button onClick={() => setCompletionOpen(false)} className="min-h-11 rounded-xl bg-togg-turquoise text-togg-darkBlue px-6">{i18nText("Tamam")}</button></AccessibleDialog>}
  </div>;
}
