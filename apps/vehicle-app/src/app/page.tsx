'use client';
import { HEALTH_MODULES, HEALTH_MODULE_IDS } from '../utils/healthModules';

import { HealthHistoryOverview } from '../components/HealthHistoryOverview';
import { InformationButton } from '../components/InformationButton';
import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useVehicle } from '../context/VehicleContext';
import {
  CalendarCheck,
  ArrowRight,
  AlertCircle,
} from 'lucide-react';
import { isDemoMode } from '../utils/attuneMode';

export default function CockpitDashboard() {

  const { isParked } = useVehicle();
  const [isDemo, setIsDemo] = useState<boolean>(false);

  useEffect(() => {
    const refresh = () => {
      const demo = isDemoMode(); setIsDemo(demo);
    };
    refresh(); window.addEventListener('attune-records', refresh); window.addEventListener('storage', refresh);
    return () => { window.removeEventListener('attune-records', refresh); window.removeEventListener('storage', refresh); };
  }, []);

  return (
    <div className="space-y-6">
      {/* 1. Hero Karşılama ve Durum Alanı (İlk Viewport Üst %35-40) */}
      <section className="bg-gradient-to-br from-cockpit-surface via-[#071322] to-cockpit-bg border border-white/10 rounded-2xl p-6 md:p-7 relative overflow-hidden shadow-2xl">
        <div className="absolute top-0 right-0 w-96 h-96 bg-togg-turquoise/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute -bottom-12 -left-12 w-64 h-64 bg-cyan-900/20 rounded-full blur-2xl pointer-events-none" />

        <div className="relative flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
          <div className="space-y-3 min-w-0 max-w-2xl">
            <div className="flex items-center gap-2 text-[11px] font-semibold text-togg-turquoise tracking-wider uppercase">
              <span className="w-2 h-2 rounded-full bg-togg-turquoise animate-pulse" />
              <span>Kişisel Önleyici Sağlık Kokpiti</span>
              {isDemo && (
                <span className="ml-2 text-[10px] px-2 py-0.5 rounded-full bg-cyan-950/80 border border-togg-turquoise/30 text-togg-turquoise lowercase font-mono">
                  demo veri
                </span>
              )}
            </div>

            <div className="space-y-1">
              <div className="flex items-center justify-between gap-3"><h1 className="text-3xl md:text-4xl font-extrabold tracking-tight text-white flex items-center gap-3">
                <span>ATTUNE</span>
                <span className="text-togg-turquoise">.more</span>
              </h1><InformationButton title="Attune kokpiti"><p>Kontroller yalnız park halinde kullanılabilir. Bu uygulama klinik tanı sağlamaz. Araç durumu simülasyondur; gerçek araç, rota veya donanım bağlantısı yoktur. Gerçek kayıt yoksa sonuç ve geçmiş üretilmez.</p></InformationButton></div>
              <p className="text-sm md:text-base text-slate-300 leading-relaxed">
                Park halinde göz, cilt, diş, işitme ve ruh sağlığı değerlendirmelerinizi başlatın.
              </p>
            </div>

            {/* Modül Kategorileri Bandı */}
            <div className="flex flex-wrap items-center gap-2 pt-1 text-xs text-slate-400">
              {HEALTH_MODULE_IDS.map((id, index) => (
                <React.Fragment key={id}>
                  {index > 0 && <span className="text-slate-600">•</span>}
                  <span className="px-2.5 py-1 rounded-full bg-white/5 border border-white/10 text-slate-300">
                    {HEALTH_MODULES[id].name}
                  </span>
                </React.Fragment>
              ))}
              <span className="text-slate-600">•</span>
              <span className="px-2.5 py-1 rounded-full bg-white/5 border border-white/10 text-slate-300">
                Uzman & Randevu
              </span>
            </div>
          </div>

          <InformationButton title="Attune ve araç kapsamı"><p>Park halinde kişisel sağlık ve iyi oluş ön değerlendirmesi içindir. Bu Windows demosunda gerçek araç telemetrisi bağlı değildir. Durum kontrolü header’daki Demo araç durumu bilgisinde bulunur. Klinik veya gerçek araç doğrulaması yapılmamıştır.</p></InformationButton>
        </div>

        {/* Sürüş Modu Emniyet Uyarısı (Sadece hareket halindeyken) */}
        {!isParked && (
          <div className="mt-4 bg-amber-950/50 border border-amber-800/70 rounded-xl px-4 py-2.5 flex items-center gap-3 text-amber-200 text-xs shadow-md">
            <AlertCircle className="w-4 h-4 text-amber-400 shrink-0" />
            <span>
              <strong>Güvenlik Kilidi Devrede:</strong> Değerlendirme ve görüşme işlemleri kilitlidir. Park durumu doğrulanmadan başlatılamaz.
            </span>
          </div>
        )}
      </section>

      <HealthHistoryOverview showStartActions parked={isParked} extraCard={
        <div className="w-full bg-cockpit-surface border border-white/10 rounded-2xl p-5 flex flex-col justify-between hover:border-togg-turquoise/40 transition-all duration-200 shadow-xl group">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="p-2.5 bg-togg-darkBlue/80 border border-togg-darkTurquoise/50 text-togg-turquoise rounded-xl group-hover:border-togg-turquoise/60 transition-colors">
                <CalendarCheck className="w-5 h-5" />
              </div>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-900 text-slate-400 border border-slate-800 font-mono">
                04 • UZMAN
              </span>
            </div>

            <div>
              <h2 className="text-base font-bold text-white group-hover:text-togg-turquoise transition-colors">
                Uzman & Randevu
              </h2>
              <p className="text-xs text-slate-400 mt-1 leading-relaxed">
                Uzman seçeneklerini inceleyin; randevuyu sağlayıcının sayfasında siz tamamlarsınız.
              </p>
            </div>

            {/* Sade Tek Katman İçgörü */}
            <div data-cockpit-care className="bg-slate-950/80 border border-slate-800/80 rounded-xl p-3 text-xs space-y-1">
              <p className="text-amber-400 text-[11px]">Örnek randevu</p>
              <div className="flex items-center justify-between">
                <span className="text-slate-400 text-[11px]">Örnek Branş</span>
                <span className="text-white text-xs font-semibold">Dermatoloji</span>
              </div>
              <div className="text-[11px] text-emerald-400 font-medium pt-1 border-t border-slate-900 flex items-center justify-between">
                <span>Uzm. Dr. B. Kaya (Demo Hekim)</span>
                <span>Yarın 18:20 (örnek)</span>
              </div>
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-white/5">
            <Link
              href="/care"
              className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl bg-togg-turquoise text-togg-darkBlue font-semibold text-xs hover:bg-[#33D0EE] transition-all min-h-touch shadow-md"
            >
              <span>Randevuları İncele</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        </div>
      } />

    </div>
  );
}
