'use client';
import {apiFetch as fetch} from '../../utils/localBackend';
import {useTranslations} from '../../i18n/LanguageProvider';

import {localBackend} from '../../utils/localBackend';
import {safeCareBookingUrl} from '../../utils/careLinks';
import { HEALTH_MODULES,HEALTH_MODULE_IDS,HealthModule } from '../../utils/healthModules';

import { InformationButton } from '../../components/InformationButton';
import React, { useState, useEffect, useRef, useCallback, Suspense } from 'react';
import { AccessibleDialog } from '../../components/AccessibleDialog';
import { useSearchParams } from 'next/navigation';
import { useVehicle } from '../../context/VehicleContext';
import { ReferralContext } from '@packages/health-profile/types';
import { CareAppointments, emptyDraft } from '../../components/care/CareAppointments';
import { AppointmentDraft, CARE_REGIONS, readCareRegion, writeCareRegion } from '../../utils/careAppointments';
import { ArrowRight, CheckCircle2, Clock, ExternalLink, MapPin, ShieldCheck, Sparkles, X } from 'lucide-react';

interface CareSlot {
  id: string;
  specialty: string;
  providerName: string;
  title: string;
  clinicName: string;
  locationLabel: string;
  isOnline: boolean|null;
  dateTime?: string;
  displayTime?: string;
  travelTimeMin: number|null;
  calendarConflict: boolean|null;
  sourceBadge: string;
  matchScore: number|null;
  calendarFits?:boolean|null;
  bookingUrl?: string;
  sourceType?: string;
}
const CARE_SPECIALTIES=Array.from(new Set(HEALTH_MODULE_IDS.flatMap(id=>HEALTH_MODULES[id].specialties))) as string[];

function CareContent() {
 const {locale,text:i18nText,node:i18nNode}=useTranslations();

  const { state, isParked } = useVehicle();
  const searchParams = useSearchParams();
  const paramSpecialty = searchParams.get('specialty');
  const paramFrom = searchParams.get('from');

  const [availableStart,setAvailableStart]=useState(''),[availableEnd,setAvailableEnd]=useState(''),[duration,setDuration]=useState(45);
  const timezone=Intl.DateTimeFormat().resolvedOptions().timeZone;
  const [selectedSpecialty, setSelectedSpecialty] = useState<string>(paramSpecialty || 'Dermatoloji');
  const [filterType, setFilterType] = useState<'ALL' | 'IN_PERSON' | 'ONLINE'>('ALL');
  const [slots, setSlots] = useState<CareSlot[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [searchNotice, setSearchNotice] = useState<string | null>(null);
  const searchGeneration = useRef(0);
  const activeSearch = useRef<AbortController | null>(null);

  // Ortak Sevk Bağlamı
  const [referralContext, setReferralContext] = useState<ReferralContext | null>(null);

  // Rezervasyon Onay Modalı
  const [selectedSlot, setSelectedSlot] = useState<CareSlot | null>(null);
  const [confirmationStep, setConfirmationStep] = useState<'SELECTING' | 'CONFIRM_MODAL' | 'HANDOFF'>('SELECTING');
  const [consentApproved, setConsentApproved] = useState<boolean>(false);
  const [region, setRegion] = useState<string>('');
  const [regionReady, setRegionReady] = useState<boolean>(false);
  // Opening a provider page is not a booking. Only the user can say one was made.
  const [awaitingReturn, setAwaitingReturn] = useState<CareSlot | null>(null);
  const [appointmentDraft, setAppointmentDraft] = useState<AppointmentDraft | null>(null);

  useEffect(() => { setRegion(readCareRegion()); setRegionReady(true); }, []);

  useEffect(() => {
    if (!isParked) {
      setSelectedSlot(null);
      setConsentApproved(false);
      setConfirmationStep('SELECTING');
    }
  }, [isParked]);

  useEffect(() => {
    if(paramSpecialty){setSelectedSpecialty(paramSpecialty);setReferralContext(null);return;}
    try {
      const stored = localStorage.getItem('togg_active_referral_context');
      if (stored) {
        const parsed: ReferralContext = JSON.parse(stored);
        setReferralContext(parsed);
        if (!paramSpecialty && parsed.specialty) {
          setSelectedSpecialty(parsed.specialty);
        }
      }
    } catch { /* Unreadable context is preserved, never exposed in logs. */ }
  }, [paramSpecialty]);

  const fetchAppointments = useCallback(async (specialty: string, controller: AbortController, generation: number) => {
    setLoading(true); setSlots([]); setSearchNotice(null);
    if (!region) { setLoading(false); return; }
    if (Boolean(availableStart) !== Boolean(availableEnd) || (availableStart && availableEnd <= availableStart)) {
      setSearchNotice('Uygun zaman başlangıcını ve bitişini kontrol edin.'); setLoading(false); return;
    }
    const deadline = setTimeout(() => controller.abort(), 12000);
    try {
      const res = await fetch(localBackend('/api/care/match'), {
        method: 'POST',
        signal: controller.signal,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          specialty,
          preferredCity: region,
          maxTravelTimeMin: 30,
          useBrowserAgent: true, timeZone:timezone,durationMin:duration,
          availableWindows:availableStart&&availableEnd?[{start:availableStart,end:availableEnd}]:[]
        })
      });

      if (res.ok) {
        const data = await res.json();
        if (controller.signal.aborted || generation !== searchGeneration.current) return;
        if (data.status === 'EMPTY_RESULT') setSearchNotice(`${region} için bu branşta kaynak bulunamadı. Başka bir bölge veya branş seçebilirsiniz.`);
        else if (!['SUCCESS', 'PUBLIC_HANDOFF'].includes(data.status)) setSearchNotice('Canlı uzman uygunluğu doğrulanamadı. Branşa ait sağlayıcı aramasını açabilirsiniz.');
        setSlots((data.matchedSlots || []).filter((slot:CareSlot)=>safeCareBookingUrl(slot.bookingUrl)).map((slot:CareSlot)=>({...slot,displayTime:slot.dateTime&&Number.isFinite(Date.parse(slot.dateTime))?new Date(slot.dateTime).toLocaleString(locale,{timeZone:timezone,dateStyle:'short',timeStyle:'short'}):'Saati sağlayıcıda doğrulayın'})));
      } else {
        throw new Error('API Hatası');
      }
    } catch {
      if (generation !== searchGeneration.current) return;
      setSearchNotice('Uzman arama hizmetine ulaşılamadı. Yeniden deneyebilir veya başka branş seçebilirsiniz.');
      setSlots([]);
    } finally {
      clearTimeout(deadline);
      if (generation === searchGeneration.current) setLoading(false);
    }
  },[availableStart,availableEnd,duration,timezone,locale,region]);

  const invalidateSearch = () => { searchGeneration.current++; activeSearch.current?.abort(); activeSearch.current = null; };
  useEffect(() => {
    if (!isParked) { invalidateSearch(); setSlots([]); setLoading(false); return; }
    if (!regionReady) return;
    const controller = new AbortController(); activeSearch.current = controller;
    const generation = ++searchGeneration.current;
    void fetchAppointments(selectedSpecialty, controller, generation);
    return () => { invalidateSearch(); controller.abort(); };
  }, [selectedSpecialty,fetchAppointments,isParked,regionReady]);

  const filteredSlots = slots.filter((slot) => {
    if (filterType === 'IN_PERSON') return slot.isOnline !== true;
    if (filterType === 'ONLINE') return slot.isOnline !== false;
    return true;
  });

  const handleSelectSlot = (slot: CareSlot) => {
    if (!isParked) return;
    setSelectedSlot(slot);
    setConsentApproved(false);
    setConfirmationStep('CONFIRM_MODAL');
  };

  const handleConfirmBooking = () => {
    if (!isParked || !consentApproved || !selectedSlot) return;
    setConfirmationStep('HANDOFF');
  };

  if (!isParked) {
    return (
      <div className="max-w-4xl mx-auto py-12 text-center space-y-4">
        <ShieldCheck className="w-14 h-14 text-amber-400 mx-auto" />
        <h1 className="text-2xl font-bold">{i18nText("Randevu İşlemleri Kilitlendi")}</h1>
        <p className="text-slate-300">{i18nText("Ayrıntılı uzman seçimi ve randevu onayı için aracın park halinde olduğu doğrulanmalıdır.")}</p>
      </div>
    );
  }

  const slotType = (slot: CareSlot) => slot.isOnline === null ? 'Görüşme türü sağlayıcıda seçilir' : slot.isOnline ? 'Online' : 'Yüz yüze';
  const slotTime = (slot: CareSlot) => slot.dateTime ? slot.displayTime : 'Tarih ve saat sağlayıcıda seçilir';
  const provider = awaitingReturn;

  return (
    <div className="space-y-5 short:space-y-3">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <h1 className="text-2xl font-bold tracking-tight short:text-xl">{i18nText("Uzmanlar ve randevular")}</h1>
          <p className="text-sm text-slate-300">{i18nText("Branş ve bölge seçin; uygunluğu sağlayıcının sayfasında doğrulayın.")}</p>
        </div>
        <div className="flex items-center gap-2">
          <p data-care-limits className="text-sm text-amber-200">{i18nText("Burada randevu oluşturulmaz.")}</p>
          <InformationButton title={i18nText("Uzman seçenekleri")}><p>{i18nText("Seçtiğiniz zaman aralığı ve görüşme süresi yalnız kaynağın doğrulanmış saatleriyle eşleştirilir. Kişisel takvim ve canlı rota entegrasyonu yoktur. Harici sayfada uygunluğu kontrol edip randevuyu kendiniz tamamlarsınız. Yönlendirme hazırlamak bilgilerinizi hekime göndermez.")}</p></InformationButton>
        </div>
      </header>

      {referralContext && (
        <div className="rounded-xl border border-togg-turquoise/40 bg-togg-darkBlue/40 p-3 flex flex-wrap items-center justify-between gap-3 text-sm">
          <p className="flex items-start gap-2 min-w-0">
            <Sparkles className="w-4 h-4 mt-0.5 text-togg-turquoise shrink-0" aria-hidden="true" />
            <span className="min-w-0"><strong>{i18nNode(HEALTH_MODULES[referralContext.sourceModule.toLowerCase() as HealthModule]?.name||'Sağlık sonucu')} → {i18nNode(referralContext.specialty)}</strong> <span className="text-slate-300">{i18nNode(referralContext.reasonSummary)}</span></span>
          </p>
          <button
            onClick={() => {
              localStorage.removeItem('togg_active_referral_context');
              setReferralContext(null);
            }}
            className="min-h-11 text-sm text-slate-300 underline shrink-0"
          >{i18nText("Bağlamı kaldır")}</button>
        </div>
      )}

      <section data-care-filters className="rounded-2xl border border-white/10 bg-cockpit-surface p-4 space-y-3">
        <div className="flex flex-wrap items-end gap-3">
          <label className="text-sm font-medium">{i18nText("Bölge")}
            <select data-care-region value={region} onChange={e => { setRegion(e.target.value); writeCareRegion(e.target.value); }} className="mt-1 block min-h-11 rounded-lg border border-white/20 bg-slate-900 px-3 text-base">
              <option value="">{i18nText("Bölge seçin")}</option>
              {CARE_REGIONS.map(item => <option key={item.city} value={item.city}>{i18nText(item.city)}, {i18nText(item.country)}</option>)}
            </select>
          </label>
          <div role="group" aria-label={i18nText("Görüşme türü")} className="flex items-center gap-1 rounded-xl border border-white/10 bg-slate-950/60 p-1">
            {(['ALL', 'IN_PERSON', 'ONLINE'] as const).map((type) => (
              <button
                key={type}
                aria-pressed={filterType === type}
                onClick={() => setFilterType(type)}
                className={`min-h-11 px-3 rounded-lg text-sm transition-colors ${filterType === type ? 'bg-togg-turquoise/15 text-togg-turquoise font-semibold' : 'text-slate-300'}`}
              >
                {i18nNode(type === 'ALL' ? 'Tümü' : type === 'IN_PERSON' ? 'Yüz yüze' : 'Online')}
              </button>
            ))}
          </div>
        </div>
        <div role="group" aria-label={i18nText("Branş")} className="flex flex-wrap gap-2">
          {CARE_SPECIALTIES.map((spec) => (
            <button
              key={spec}
              aria-pressed={selectedSpecialty === spec}
              onClick={() => setSelectedSpecialty(spec)}
              className={`min-h-11 px-4 rounded-xl text-sm transition-colors ${selectedSpecialty === spec ? 'bg-togg-turquoise text-togg-darkBlue font-semibold' : 'border border-white/10 bg-slate-950/60 text-slate-200'}`}
            >
              {i18nNode(spec)}
            </button>
          ))}
        </div>
        <details data-care-time-window className="text-sm">
          <summary className="min-h-11 flex items-center cursor-pointer font-medium text-slate-200">{i18nText("Zaman aralığı ve süre")}</summary>
          <div className="flex flex-wrap gap-3 items-end pt-2">
            <label>{i18nText("Uygun zaman başlangıcı")}<input type="datetime-local" value={availableStart} onChange={e=>setAvailableStart(e.target.value)} className="block mt-1 min-h-11 bg-slate-900 rounded-lg px-2 border border-white/20 max-w-full"/></label>
            <label>{i18nText("Uygun zaman bitişi")}<input type="datetime-local" value={availableEnd} min={availableStart} onChange={e=>setAvailableEnd(e.target.value)} className="block mt-1 min-h-11 bg-slate-900 rounded-lg px-2 border border-white/20 max-w-full"/></label>
            <label>{i18nText("Görüşme süresi")}<select value={duration} onChange={e=>setDuration(Number(e.target.value))} className="block mt-1 min-h-11 bg-slate-900 px-2 rounded-lg border border-white/20">{[30,45,60].map(v=><option key={v} value={v}>{i18nNode(v)}{i18nText(" dakika")}</option>)}</select></label>
            <p data-care-timezone className="text-slate-300">{i18nText("Saatler bu cihazın saat diliminde gösterilir: ")}{timezone}</p>
          </div>
        </details>
      </section>

      {provider && (
        <section data-care-return role="status" className="rounded-2xl border border-togg-turquoise/40 bg-togg-darkBlue/40 p-4 flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0 space-y-1">
            <h2 className="text-base font-semibold">{i18nText("Randevunuzu aldınız mı?")}</h2>
            <p className="text-sm text-slate-300">{i18nText("Attune.more dış sitedeki randevuları göremez. Yalnız randevunuz kesinleştiyse kaydedin.")}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button data-care-return-no onClick={() => setAwaitingReturn(null)} className="min-h-11 px-4 rounded-xl border border-white/20 text-sm">{i18nText("Henüz almadım")}</button>
            <button data-care-return-yes onClick={() => { setAppointmentDraft(emptyDraft(provider.specialty, provider.sourceType === 'PUBLIC_SEARCH_ONLY' ? '' : provider.providerName)); setAwaitingReturn(null); }} className="min-h-11 px-4 rounded-xl bg-togg-turquoise text-togg-darkBlue text-sm font-semibold">{i18nText("Evet, kaydet")}</button>
          </div>
        </section>
      )}

      <section data-care-results className="space-y-3">
        <h2 className="text-lg font-bold">{i18nText("Uzman seçenekleri")}</h2>
        {!region && regionReady && <p data-care-region-required role="status" className="text-sm text-amber-200">{i18nText("Uzman seçeneklerini görmek için bir bölge seçin.")}</p>}
        {loading && region && <p role="status" className="text-sm text-slate-300">{i18nText("Uzman seçenekleri hazırlanıyor…")}</p>}
        {searchNotice && <div role="status" className="p-3 rounded-xl border border-amber-800 text-sm text-amber-200"><p>{i18nNode(searchNotice)}</p><button className="min-h-11 underline" onClick={() => { invalidateSearch(); const controller = new AbortController(); activeSearch.current = controller; const generation = ++searchGeneration.current; void fetchAppointments(selectedSpecialty, controller, generation); }}>{i18nText("Yeniden ara")}</button></div>}
        {!loading && region && !searchNotice && !filteredSlots.length && <p role="status" className="text-sm text-slate-300">{i18nText("Bu filtre için uygun seçenek bulunamadı. Diğer görüşme türlerini inceleyebilirsiniz.")}</p>}
        {filteredSlots.length > 0 && (
          <div className="grid gap-3 md:grid-cols-2 short:grid-cols-2">
            {filteredSlots.map((slot) => (
              <article key={slot.id} data-care-slot className="rounded-2xl border border-white/10 bg-cockpit-surface p-4 flex flex-col justify-between gap-3">
                <div className="space-y-1 min-w-0">
                  <h3 className="text-lg font-bold break-words">{i18nNode(slot.providerName)}</h3>
                  <p className="text-sm text-slate-300">{i18nNode(slot.specialty)}</p>
                  <p className="flex items-center gap-1.5 text-sm text-slate-300"><MapPin className="w-4 h-4 shrink-0" aria-hidden="true"/><span>{i18nNode(slot.locationLabel)}</span></p>
                  <p className="flex items-center gap-1.5 text-sm text-slate-300"><Clock className="w-4 h-4 shrink-0" aria-hidden="true"/><span>{i18nNode(slotTime(slot))}</span></p>
                  <p className="text-sm text-slate-300">{i18nNode(slotType(slot))}</p>
                  {slot.calendarFits === true && <p className="flex items-center gap-1.5 text-sm text-emerald-300"><CheckCircle2 className="w-4 h-4 shrink-0" aria-hidden="true"/><span>{i18nText("Seçtiğiniz zaman aralığına uygun")}</span></p>}
                </div>
                <button
                  onClick={() => handleSelectSlot(slot)}
                  className="self-end min-h-11 px-5 rounded-xl bg-togg-turquoise text-togg-darkBlue text-sm font-semibold inline-flex items-center gap-2"
                >
                  <span>{i18nText("Randevuyu incele")}</span>
                  <ArrowRight className="w-4 h-4" aria-hidden="true" />
                </button>
              </article>
            ))}
          </div>
        )}
      </section>

      <CareAppointments specialties={CARE_SPECIALTIES} defaultSpecialty={selectedSpecialty} requestedDraft={appointmentDraft} onRequestHandled={() => setAppointmentDraft(null)} />

      {confirmationStep === 'CONFIRM_MODAL' && selectedSlot && (
        <AccessibleDialog title={i18nText("Yönlendirme onayı")} onClose={() => setConfirmationStep('SELECTING')} className="bg-cockpit-surface border border-white/20 rounded-2xl max-w-lg w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between gap-3">
              <h2 className="flex items-center gap-2 text-lg font-bold"><ShieldCheck className="w-5 h-5 text-togg-turquoise" aria-hidden="true" />{i18nText("Yönlendirme onayı")}</h2>
              <button onClick={() => setConfirmationStep('SELECTING')} aria-label={i18nText("Pencereyi kapat")} className="min-h-11 min-w-11 inline-flex items-center justify-center rounded-xl border border-white/20"><X className="w-5 h-5" aria-hidden="true" /></button>
            </div>
            <p className="text-sm text-slate-300">{i18nText("Bu adım yalnız yönlendirmeyi hazırlar. Randevu oluşturulmaz ve bilgileriniz sağlayıcıya gönderilmez.")}</p>
            <div className="rounded-xl border border-white/10 bg-slate-950/60 p-3 space-y-1 text-sm">
              <p className="text-base font-semibold">{i18nNode(selectedSlot.providerName)}</p>
              <p className="text-slate-300">{i18nNode(selectedSlot.specialty)} · {i18nNode(selectedSlot.locationLabel)}</p>
              <p className="text-togg-turquoise">{i18nNode(slotTime(selectedSlot))}</p>
            </div>
            {referralContext && <p className="text-sm text-slate-300"><strong>{i18nNode(referralContext.specialty)}</strong>{i18nText(" ön değerlendirme özeti bu cihazda hazırlanır. Harici sayfaya otomatik aktarılmaz.")}</p>}
            <label className="flex items-start gap-3 text-sm cursor-pointer">
              <input type="checkbox" checked={consentApproved} onChange={(e) => setConsentApproved(e.target.checked)} className="mt-0.5 h-5 w-5 shrink-0 accent-togg-turquoise" />
              <span>{i18nText("Randevu bilgilerimin Attune.more tarafından işlenmesini, sevk bağlamımın hazırlanmasını ve harici sağlayıcı sayfasına yönlendirilmeyi onaylıyorum.")}</span>
            </label>
            <div data-dialog-actions className="flex flex-wrap justify-end gap-3">
              <button onClick={() => setConfirmationStep('SELECTING')} className="min-h-11 px-4 rounded-xl border border-white/20 text-sm">{i18nText("Vazgeç")}</button>
              <button onClick={handleConfirmBooking} disabled={!consentApproved} className="min-h-11 px-5 rounded-xl bg-togg-turquoise text-togg-darkBlue text-sm font-semibold inline-flex items-center gap-2 disabled:opacity-40">
                <span>{i18nText("Onayla ve devam et")}</span>
                <ArrowRight className="w-4 h-4" aria-hidden="true" />
              </button>
            </div>
        </AccessibleDialog>
      )}

      {confirmationStep === 'HANDOFF' && selectedSlot && (
        <AccessibleDialog title={i18nText("Yönlendirme hazır")} onClose={() => { setConfirmationStep('SELECTING'); setSelectedSlot(null); }} className="bg-cockpit-surface border border-white/20 rounded-2xl max-w-lg w-full p-6 space-y-4 shadow-2xl">
          <h2 className="flex items-center gap-2 text-lg font-bold"><CheckCircle2 className="w-5 h-5 text-emerald-300" aria-hidden="true" />{i18nText("Yönlendirme hazır")}</h2>
          <p className="text-sm text-slate-300">{i18nText("Randevu henüz alınmadı. Sağlayıcı sayfasında uygunluğu kontrol edip işlemi kendiniz tamamlayın.")}</p>
          <div className="rounded-xl border border-white/10 bg-slate-950/60 p-3 space-y-1 text-sm">
            <p className="text-base font-semibold">{i18nNode(selectedSlot.providerName)}</p>
            <p className="text-slate-300">{i18nNode(selectedSlot.specialty)} · {i18nNode(selectedSlot.locationLabel)}</p>
          </div>
          <div data-dialog-actions className="flex flex-wrap justify-end gap-3">
            <button onClick={() => { setConfirmationStep('SELECTING'); setSelectedSlot(null); }} className="min-h-11 px-4 rounded-xl border border-white/20 text-sm">{i18nText("Kapat")}</button>
            <a
              data-care-open-provider
              href={safeCareBookingUrl(selectedSlot.bookingUrl)}
              target="_blank"
              rel="noreferrer"
              onClick={() => { setAwaitingReturn(selectedSlot); setConfirmationStep('SELECTING'); setSelectedSlot(null); }}
              className="min-h-11 px-5 rounded-xl bg-togg-turquoise text-togg-darkBlue text-sm font-semibold inline-flex items-center gap-2"
            >
              <span>{i18nText("Sağlayıcı sayfasını aç")}</span>
              <ExternalLink className="w-4 h-4" aria-hidden="true" />
            </a>
          </div>
        </AccessibleDialog>
      )}
    </div>
  );
}

export default function CarePage() {
 const {text:i18nText,node:i18nNode}=useTranslations();
  return (
    <Suspense fallback={<div className="p-8 text-center text-slate-400 text-xs">{i18nText("Yükleniyor...")}</div>}>
      <CareContent />
    </Suspense>
  );
}
