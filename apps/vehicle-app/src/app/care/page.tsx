'use client';
import {localBackend} from '../../utils/localBackend';
import {safeCareBookingUrl} from '../../utils/careLinks';
import { HEALTH_MODULES,HEALTH_MODULE_IDS,HealthModule } from '../../utils/healthModules';

import { InformationButton } from '../../components/InformationButton';
import React, { useState, useEffect, useRef, useCallback, Suspense } from 'react';
import { AccessibleDialog } from '../../components/AccessibleDialog';
import { useSearchParams } from 'next/navigation';
import { useVehicle } from '../../context/VehicleContext';
import { ReferralContext } from '@packages/health-profile/types';
import {
  CalendarCheck,
  MapPin,
  Calendar,
  CheckCircle2,
  AlertCircle,
  ShieldCheck,
  ArrowRight,
  ExternalLink,
  Car,
  Filter,
  Sparkles,
  Eye,
  HeartPulse,
  AlertTriangle,
  Clock,
  ChevronRight
} from 'lucide-react';

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
}

function CareContent() {

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
  const [confirmationStep, setConfirmationStep] = useState<'SELECTING' | 'CONFIRM_MODAL' | 'BOOKED'>('SELECTING');
  const [consentApproved, setConsentApproved] = useState<boolean>(false);

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
          preferredCity: 'İstanbul',
          maxTravelTimeMin: 30,
          useBrowserAgent: true, timeZone:timezone,durationMin:duration,
          availableWindows:availableStart&&availableEnd?[{start:availableStart,end:availableEnd}]:[]
        })
      });

      if (res.ok) {
        const data = await res.json();
        if (controller.signal.aborted || generation !== searchGeneration.current) return;
        if (!['SUCCESS', 'PUBLIC_HANDOFF'].includes(data.status)) setSearchNotice('Canlı uzman uygunluğu doğrulanamadı. Branşa ait sağlayıcı aramasını açabilirsiniz.');
        setSlots((data.matchedSlots || []).filter((slot:CareSlot)=>safeCareBookingUrl(slot.bookingUrl)).map((slot:CareSlot)=>({...slot,displayTime:slot.dateTime&&Number.isFinite(Date.parse(slot.dateTime))?new Date(slot.dateTime).toLocaleString('tr-TR',{timeZone:timezone,dateStyle:'short',timeStyle:'short'}):'Saati sağlayıcıda doğrulayın'})));
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
  },[availableStart,availableEnd,duration,timezone]);

  const invalidateSearch = () => { searchGeneration.current++; activeSearch.current?.abort(); activeSearch.current = null; };
  useEffect(() => {
    if (!isParked) { invalidateSearch(); setSlots([]); setLoading(false); return; }
    const controller = new AbortController(); activeSearch.current = controller;
    const generation = ++searchGeneration.current;
    void fetchAppointments(selectedSpecialty, controller, generation);
    return () => { invalidateSearch(); controller.abort(); };
  }, [selectedSpecialty,fetchAppointments,isParked]);

  const filteredSlots = slots.filter((slot) => {
    if (filterType === 'IN_PERSON') return slot.isOnline === false;
    if (filterType === 'ONLINE') return slot.isOnline;
    return true;
  });

  const featuredSlot = filteredSlots[0];
  const secondarySlots = filteredSlots.slice(1);

  const handleSelectSlot = (slot: CareSlot) => {
    if (!isParked) return;
    setSelectedSlot(slot);
    setConsentApproved(false);
    setConfirmationStep('CONFIRM_MODAL');
  };

  const handleConfirmBooking = () => {
    if (!isParked || !consentApproved || !selectedSlot) return;
    setConfirmationStep('BOOKED');
  };

  if (!isParked) {
    return (
      <div className="max-w-4xl mx-auto py-12 text-center space-y-4">
        <ShieldCheck className="w-14 h-14 text-amber-400 mx-auto" />
        <h1 className="text-2xl font-bold">Randevu İşlemleri Kilitlendi</h1>
        <p className="text-slate-300">Ayrıntılı uzman seçimi ve randevu onayı için aracın park halinde olduğu doğrulanmalıdır.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* 1. SCREEN 08: ÜST BAŞLIK VE FİLTRE ÇUBUĞU (FIRST VIEWPORT) */}
      <section className="bg-gradient-to-br from-cockpit-surface via-[#071322] to-cockpit-bg border border-white/10 rounded-2xl p-6 md:p-7 shadow-2xl space-y-5">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1.5">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-togg-turquoise/10 border border-togg-turquoise/30 text-togg-turquoise text-[11px] font-semibold tracking-wider uppercase">
              <CalendarCheck className="w-3.5 h-3.5" />
              <span>Uzman Erişimi • Akıllı Hekim Erişimi</span>
            </div>

            <h1 className="text-2xl md:text-3xl font-extrabold text-white tracking-tight">
              Sizin için uygun uzmanlar
            </h1>

            <p className="text-sm text-slate-300">
              Branş seçin; uygunluğu sağlayıcının sayfasında doğrulayın.
            </p>
          </div>

          <div className="flex items-center gap-2 self-start md:self-auto text-xs bg-slate-950/80 px-3 py-1.5 rounded-xl border border-white/10 text-slate-300">
            <span className="w-2 h-2 rounded-full bg-emerald-400" />
            <span>Uygun Zaman • Uzman Seçenekleri</span>
          </div>
        </div>

        <div className="flex items-center gap-3"><p data-care-limits className="text-xs text-amber-200">Burada randevu oluşturulmaz.</p><InformationButton title="Uzman seçenekleri"><p>Seçtiğiniz zaman aralığı ve görüşme süresi yalnız kaynağın doğrulanmış saatleriyle eşleştirilir. Kişisel takvim ve canlı rota entegrasyonu yoktur. Ulaşım süresi örnektir. Harici sayfada uygunluğu kontrol edip randevuyu kendiniz tamamlarsınız. Paylaşım ayrı eylemde onaylanır; yönlendirme hazırlamak bilgilerinizi hekime göndermez.</p></InformationButton></div>

        {/* AKTİF SEVK BAĞLAMI BİLDİRİMİ */}
        {referralContext && (
          <div className="bg-togg-darkBlue/40 border border-togg-turquoise/40 rounded-xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
            <div className="flex items-center gap-2.5">
              <Sparkles className="w-4 h-4 text-togg-turquoise shrink-0" />
              <div className="text-slate-200">
                <span className="font-bold text-white">
                  {HEALTH_MODULES[referralContext.sourceModule.toLowerCase() as HealthModule]?.name||'Sağlık sonucu'} → {referralContext.specialty}
                </span>
                <span className="text-slate-400 mx-1.5">•</span>
                <span className="text-slate-300 text-[11px]">{referralContext.reasonSummary}</span>
              </div>
            </div>

            <button
              onClick={() => {
                localStorage.removeItem('togg_active_referral_context');
                setReferralContext(null);
              }}
              className="text-[11px] text-slate-400 hover:text-white underline shrink-0 self-end sm:self-auto"
            >
              Bağlamı Kaldır
            </button>
          </div>
        )}

        {/* BRANŞ VE GÖRÜŞME TÜRÜ FİLTRE HAPLARI */}
        <div className="flex flex-wrap items-center justify-between gap-4 pt-1 border-t border-white/10">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold text-slate-400 mr-1">Branş:</span>
            {Array.from(new Set(HEALTH_MODULE_IDS.flatMap(id=>HEALTH_MODULES[id].specialties))).map((spec) => (
              <button
                key={spec}
                onClick={() => setSelectedSpecialty(spec)}
                className={`px-4 py-2 rounded-xl text-xs font-bold transition-all min-h-touch ${
                  selectedSpecialty === spec
                    ? 'bg-togg-turquoise text-togg-darkBlue shadow-[0_0_15px_rgba(0,194,231,0.3)]'
                    : 'bg-slate-900/90 text-slate-400 hover:text-white border border-slate-800'
                }`}
              >
                {spec}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-1.5 bg-slate-950/90 p-1 rounded-xl border border-slate-800 text-xs">
            {(['ALL', 'IN_PERSON', 'ONLINE'] as const).map((type) => (
              <button
                key={type}
                onClick={() => setFilterType(type)}
                className={`px-3 py-1.5 rounded-lg font-medium transition-colors ${
                  filterType === type
                    ? 'bg-togg-turquoise/15 text-togg-turquoise border border-togg-turquoise/30 font-semibold'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                {type === 'ALL' ? 'Tümü' : type === 'IN_PERSON' ? 'Yüz Yüze' : 'Online'}
              </button>
            ))}
          </div>
        </div>
      </section>

      <div className="flex flex-wrap gap-3 items-end"><label className="text-sm">Uygun zaman başlangıcı<input type="datetime-local" value={availableStart} onChange={e=>setAvailableStart(e.target.value)} className="block mt-1 bg-slate-900 rounded-lg p-2 border border-white/20 max-w-full"/></label><label className="text-sm">Uygun zaman bitişi<input type="datetime-local" value={availableEnd} min={availableStart} onChange={e=>setAvailableEnd(e.target.value)} className="block mt-1 bg-slate-900 rounded-lg p-2 border border-white/20 max-w-full"/></label><label className="text-sm">Görüşme süresi<select value={duration} onChange={e=>setDuration(Number(e.target.value))} className="block mt-1 bg-slate-900 p-2 rounded-lg">{[30,45,60].map(v=><option key={v} value={v}>{v} dakika</option>)}</select></label><span className="text-xs text-slate-400">{timezone}</span></div>
      {loading && <p role="status" className="p-4 text-sm text-slate-300">Uzman seçenekleri hazırlanıyor…</p>}
      {searchNotice && <div role="status" className="p-4 rounded-xl border border-amber-800 text-sm text-amber-200"><p>{searchNotice}</p><button className="underline mt-2" onClick={() => { invalidateSearch(); const controller = new AbortController(); activeSearch.current = controller; const generation = ++searchGeneration.current; void fetchAppointments(selectedSpecialty, controller, generation); }}>Yeniden ara</button></div>}
      {!loading && !filteredSlots.length && <p role="status" className="p-4 text-sm">Bu filtre için uygun seçenek bulunamadı. Diğer görüşme türlerini inceleyebilirsiniz.</p>}
      {/* 2. ÖNE ÇIKAN UZMAN KARTI (FEATURED PROVIDER CARD) */}
      {featuredSlot && (
        <section className="bg-cockpit-surface border border-togg-turquoise/30 rounded-2xl p-6 md:p-8 shadow-2xl relative overflow-hidden group hover:border-togg-turquoise/60 transition-all">
          <div className="absolute top-0 right-0 w-80 h-80 bg-togg-turquoise/5 rounded-full blur-3xl pointer-events-none" />

          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6 relative z-10">
            {/* Sol: Doktor Bilgileri & Rozetler */}
            <div className="space-y-3 max-w-2xl">
              <div className="flex flex-wrap items-center gap-2">
                <span className="px-2.5 py-1 rounded-full bg-emerald-950/60 text-emerald-400 border border-emerald-800/60 text-[10px] font-semibold tracking-wider uppercase">
                  Uzman seçeneği
                </span>
                <span className="px-2.5 py-1 rounded-full bg-slate-900 text-slate-300 border border-slate-800 text-[10px] font-mono">
                  {featuredSlot.isOnline === null ? 'Uzman seçeneği' : featuredSlot.isOnline ? 'Online Görüşme' : 'Yüz Yüze Muayene'}
                </span>
                <span className="px-2 py-0.5 rounded bg-white/5 text-slate-400 text-[10px] font-mono">
                  {featuredSlot.sourceBadge}
                </span>
              </div>

              <div>
                <h2 className="text-xl md:text-2xl font-extrabold text-white group-hover:text-togg-turquoise transition-colors">
                  {featuredSlot.providerName}
                </h2>
                <div className="text-xs text-slate-400 font-medium mt-0.5">
                  {featuredSlot.title}
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-4 text-xs text-slate-300 pt-1">
                <span className="flex items-center gap-1.5">
                  <MapPin className="w-4 h-4 text-togg-turquoise" />
                  <span>{featuredSlot.clinicName} • {featuredSlot.locationLabel}</span>
                </span>

                <span className="flex items-center gap-1.5">
                  <Car className="w-4 h-4 text-togg-turquoise" />
                  <span>{featuredSlot.isOnline === true ? 'Ulaşım gerektirmez (çevrimiçi)' : featuredSlot.travelTimeMin === null ? null : `Örnek ulaşım: ${featuredSlot.travelTimeMin} dk`}</span>
                </span>

                <span className="flex items-center gap-1.5 text-emerald-400 font-medium">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  <span>{featuredSlot.calendarFits===true?'Seçtiğiniz zaman aralığına uygun':'Saat uygunluğu doğrulanmadı'}</span>
                </span>
              </div>
            </div>

            {/* Sağ: Önerilen Saat ve Birincil CTA */}
            <div className="flex lg:flex-col items-center lg:items-end justify-between gap-4 shrink-0 pt-4 lg:pt-0 border-t lg:border-t-0 border-white/10">
              <div className="text-left lg:text-right space-y-0.5">
                <div className="text-[11px] text-slate-400 uppercase tracking-wider font-mono">Listelenen Saat</div>
                <div className="text-lg md:text-xl font-bold text-white font-mono">{featuredSlot.displayTime}</div>
              </div>

              <div className="flex items-center gap-2.5">
                <button
                  onClick={() => handleSelectSlot(featuredSlot)}
                  className="py-3 px-6 rounded-xl bg-togg-turquoise hover:bg-[#33D0EE] text-togg-darkBlue font-bold text-xs flex items-center gap-2 transition-all shadow-[0_0_15px_rgba(0,194,231,0.25)] min-h-touch"
                >
                  <span>RANDEVUYU İNCELE</span>
                  <ArrowRight className="w-4 h-4" />
                </button>

                <a
                  href={safeCareBookingUrl(featuredSlot.bookingUrl)}
                  target="_blank"
                  rel="noreferrer"
                  className="p-3 rounded-xl bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-white border border-slate-800 transition-colors"
                  title="Sağlayıcı sayfasını aç"
                >
                  <ExternalLink className="w-4 h-4" />
                </a>
              </div>
            </div>
          </div>
        </section>
      )}

      {/* 3. BELOW FOLD: ALTERNATİF UZMAN SEÇENEKLERİ */}
      {secondarySlots.length > 0 && (
        <section className="space-y-3">
          <div className="text-xs font-bold text-slate-400 uppercase tracking-wider px-1">
            Diğer Uzman Seçenekleri
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {secondarySlots.map((slot) => (
              <div
                key={slot.id}
                className="bg-cockpit-surface border border-white/10 rounded-2xl p-5 flex flex-col justify-between hover:border-white/20 transition-all shadow-lg space-y-4"
              >
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-base font-bold text-white">{slot.providerName}</span>
                    <span className="text-[10px] px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-400 font-mono">
                      {slot.isOnline === null ? 'Uzman seçeneği' : slot.isOnline ? 'Online' : 'Yüz Yüze'}
                    </span>
                  </div>

                  <p className="text-[10px] text-slate-400">{slot.sourceBadge}</p>
                  <p className="text-xs text-slate-400 flex items-center gap-1.5">
                    <MapPin className="w-3.5 h-3.5 text-slate-500 shrink-0" />
                    <span>{slot.clinicName} • {slot.locationLabel}</span>
                  </p>

                  <div className="flex items-center gap-3 text-xs text-slate-300 pt-1">
                    <span className="text-togg-turquoise font-mono font-bold">{slot.displayTime}</span>
                    <span className="text-slate-600">•</span>
                    <span>{slot.isOnline === true ? 'Online' : slot.travelTimeMin === null ? null : `Örnek ulaşım: ${slot.travelTimeMin} dk`}</span>
                  </div>
                </div>

                <div className="pt-2 border-t border-white/5 flex items-center justify-end">
                  <button
                    onClick={() => handleSelectSlot(slot)}
                    className="py-2 px-4 rounded-xl bg-slate-900 hover:bg-slate-800 text-togg-turquoise border border-togg-turquoise/30 font-semibold text-xs transition-all flex items-center gap-1.5"
                  >
                    <span>İncele</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* AÇIK ONAY MODALI (CONSENT GATE) */}
      {confirmationStep === 'CONFIRM_MODAL' && selectedSlot && (
        <AccessibleDialog title="Kullanıcı Onayı ve Sevk Bağlamı" onClose={() => setConfirmationStep('SELECTING')} className="bg-cockpit-surface border border-white/20 rounded-2xl max-w-lg w-full p-6 md:p-7 space-y-5 shadow-2xl">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <div className="flex items-center gap-2 text-togg-turquoise font-bold text-base">
                <ShieldCheck className="w-5 h-5" />
                <span>Kullanıcı Onayı ve Sevk Bağlamı</span>
              </div>
              <button
                onClick={() => setConfirmationStep('SELECTING')}
                aria-label="Pencereyi kapat"
                className="w-11 shrink-0 text-slate-400 hover:text-white text-xs"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3 text-xs text-slate-300 leading-relaxed">
              <p>
                Bu adım yalnız yönlendirmeyi hazırlar. Randevu oluşturulmaz ve bilgileriniz sağlayıcıya gönderilmez.
              </p>

              <div className="bg-slate-950/80 p-3.5 rounded-xl border border-slate-800 space-y-1">
                <div className="font-bold text-white text-sm">{selectedSlot.providerName}</div>
                <div className="text-slate-400">{selectedSlot.clinicName} • {selectedSlot.locationLabel}</div>
                <div className="text-togg-turquoise font-mono font-bold pt-1">{selectedSlot.displayTime}</div>
              </div>

              {referralContext && (
                <div className="bg-togg-darkBlue/40 border border-togg-turquoise/40 p-3 rounded-xl text-[11px] text-togg-turquoise">
                  ℹ️ Randevu talebine <strong>{referralContext.specialty}</strong> ön değerlendirme özeti bu cihazda hazırlanır. Harici sayfaya otomatik aktarılmaz.
                </div>
              )}

              <label className="flex items-start gap-3 pt-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={consentApproved}
                  onChange={(e) => setConsentApproved(e.target.checked)}
                  className="mt-0.5 w-4 h-4 rounded border-slate-700 bg-slate-900 accent-togg-turquoise cursor-pointer"
                />
                <span className="text-slate-300 leading-snug">
                  Randevu bilgilerimin sağlık asistanı tarafından işlenmesini, sevk bağlamımın hekime aktarılmak üzere hazırlanmasını ve harici sağlayıcı bağlantısına yönlendirilmeyi <strong>açıkça onaylıyorum</strong>.
                </span>
              </label>
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-white/10">
              <button
                onClick={() => setConfirmationStep('SELECTING')}
                className="px-4 py-2 rounded-xl text-xs text-slate-400 hover:text-white"
              >
                Vazgeç
              </button>
              <button
                onClick={handleConfirmBooking}
                disabled={!consentApproved}
                className={`py-2.5 px-5 rounded-xl font-bold text-xs flex items-center gap-1.5 transition-all ${
                  consentApproved
                    ? 'bg-togg-turquoise hover:bg-[#33D0EE] text-togg-darkBlue cursor-pointer shadow-lg'
                    : 'bg-slate-800 text-slate-500 cursor-not-allowed'
                }`}
              >
                <span>Onayla ve Devam Et</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
        </AccessibleDialog>
      )}

      {/* BAŞARILI DEVİR EKRANI */}
      {confirmationStep === 'BOOKED' && selectedSlot && (
        <div className="bg-cockpit-surface border border-emerald-800/80 rounded-2xl p-6 md:p-8 space-y-4 text-center max-w-xl mx-auto shadow-2xl">
          <div className="w-12 h-12 bg-emerald-950 text-emerald-400 border border-emerald-700 rounded-full flex items-center justify-center mx-auto shadow-inner">
            <CheckCircle2 className="w-6 h-6" />
          </div>

          <h2 className="text-xl font-bold text-white">Randevu Yönlendirmesi Hazırlandı</h2>
          <p className="text-xs text-slate-300 leading-relaxed">
            Hekim sisteminde randevu oluşturulmadı ve bilgileriniz gönderilmedi. Harici sayfada uygunluğu kontrol edip işlemi kendiniz tamamlayabilirsiniz.
          </p>

          <div className="max-w-sm mx-auto bg-slate-950/80 border border-slate-800 p-4 rounded-xl text-xs text-left space-y-1">
            <div className="font-bold text-white">{selectedSlot.providerName}</div>
            <div className="text-slate-400">{selectedSlot.clinicName}</div>
            <div className="text-togg-turquoise font-mono">{selectedSlot.displayTime}</div>
          </div>

          <div className="flex justify-center gap-3 pt-2">
            <button
              onClick={() => {
                setConfirmationStep('SELECTING');
                setSelectedSlot(null);
              }}
              className="px-4 py-2 rounded-xl text-xs text-slate-400 hover:text-white"
            >
              Kapat
            </button>
            <a
              href={safeCareBookingUrl(selectedSlot.bookingUrl)}
              target="_blank"
              rel="noreferrer"
              className="py-2.5 px-6 rounded-xl bg-togg-turquoise hover:bg-[#33D0EE] text-togg-darkBlue font-bold text-xs flex items-center gap-1.5 shadow-md"
            >
              <span>Sağlayıcı Sayfasına Git</span>
              <ExternalLink className="w-3.5 h-3.5" />
            </a>
          </div>
        </div>
      )}
    </div>
  );
}

export default function CarePage() {
  return (
    <Suspense fallback={<div className="p-8 text-center text-slate-400 text-xs">Yükleniyor...</div>}>
      <CareContent />
    </Suspense>
  );
}
