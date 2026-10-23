'use client';
import {useTranslations} from '../../i18n/LanguageProvider';


import { AccessibleDialog } from '../AccessibleDialog';
import React, { useState } from 'react';
import { isDemoMode } from '../../utils/attuneMode';
import { SkinReminderForm } from './SkinReminderForm';
import { Lightbulb, X, Bell, ShieldCheck, UserCheck, ChevronRight } from 'lucide-react';
import { SkinRegionData } from '../../data/skinDemoFixture';

interface SkinActionsModalProps {
  region: SkinRegionData;
  onClose: () => void;
  onNavigateToCare: () => void;
}

export const SkinActionsModal: React.FC<SkinActionsModalProps> = ({
  region,
  onClose,
  onNavigateToCare
}) => {
 const {text:i18nText,node:i18nNode}=useTranslations();
  const [showReminder, setShowReminder] = useState(false);
  return (
    <AccessibleDialog title={i18nText("Önerilen Aksiyonlar")} onClose={onClose} className="relative w-full max-w-xl bg-[#0B1526] border border-slate-700/80 rounded-2xl p-6 sm:p-7 shadow-2xl space-y-6">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-togg-turquoise/10 border border-togg-turquoise/30 flex items-center justify-center text-togg-turquoise">
              <Lightbulb className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-white tracking-wide">{i18nText("Önerilen Aksiyonlar")}</h3>
              <p className="text-xs text-slate-400 mt-0.5">
                {i18nNode(region.nameTr)}{i18nText(" bölgesi analizi doğrultusunda öneriler ")}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label={i18nText("Pencereyi kapat")}
            className="w-11 h-11 shrink-0 rounded-lg flex items-center justify-center text-slate-400 hover:text-white hover:bg-slate-800/80 transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {region.routine && <div data-skin-routine className="space-y-4">
          {region.routine.length ? region.routine.map(section => <section key={section.id} data-routine-section={section.id}>
            <h4 className="text-sm font-bold text-white">{i18nText(section.title)}</h4>
            <ul className="mt-2 list-disc space-y-1.5 pl-5 text-sm leading-relaxed text-slate-300">
              {section.items.map(item => <li key={item}>{i18nText(item)}</li>)}
            </ul>
          </section>) : <p className="text-sm text-slate-400">{i18nText('Bu sonuçta kişiselleştirilmiş ürün önerisi için yeterli ölçüm yok.')}</p>}
        </div>}

        {/* Preserve reminder and specialist actions after the four routine sections. */}
        <div className="space-y-3">
          {region.actions.filter(act => region.routine === undefined || act.isCareHandoff || act.icon === 'calendar').map((act, idx) => {
            if (act.isCareHandoff) {
              return (
                <button
                  type="button"
                  key={idx}
                  onClick={() => {
                    onClose();
                    onNavigateToCare();
                  }}
                  className="w-full text-left flex items-center justify-between p-4 rounded-xl bg-gradient-to-r from-togg-turquoise/15 to-transparent border border-togg-turquoise/35 hover:border-togg-turquoise/70 transition-all cursor-pointer group shadow-lg"
                >
                  <div className="flex items-center gap-3.5">
                    <div className="w-9 h-9 rounded-lg bg-togg-turquoise/20 border border-togg-turquoise/40 text-togg-turquoise flex items-center justify-center shrink-0 group-hover:scale-105 transition-transform">
                      <UserCheck className="w-4 h-4" />
                    </div>
                    <div>
                      <h4 className="text-sm font-semibold text-white group-hover:text-togg-turquoise transition-colors">
                        {i18nNode(act.title)}
                      </h4>
                      <p className="text-xs text-slate-300 mt-0.5">
                        {i18nNode(act.description)}
                      </p>
                    </div>
                  </div>
                  <ChevronRight className="w-4 h-4 text-togg-turquoise group-hover:translate-x-1 transition-transform" />
                </button>
              );
            }

            const IconComponent = act.icon === 'calendar' ? Bell : ShieldCheck;
            const iconBg = act.icon === 'calendar' ? 'bg-sky-500/10 border-sky-500/20 text-sky-400' : 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400';

            return (
              <div
                key={idx}
                className="flex items-center justify-between p-4 rounded-xl bg-slate-950/60 border border-slate-800/80"
              >
                <div className="flex items-center gap-3.5">
                  <div className={`w-9 h-9 rounded-lg border flex items-center justify-center shrink-0 ${iconBg}`}>
                    <IconComponent className="w-4 h-4" />
                  </div>
                  <div>
                    <h4 className="text-sm font-semibold text-white">{i18nNode(act.title)}</h4>
                    <p className="text-xs text-slate-400 mt-0.5">{i18nNode(act.description)}</p>
                  </div>
                </div>
                {act.icon === 'calendar' && <button aria-expanded={showReminder} onClick={() => setShowReminder(previous => !previous)} className="text-togg-turquoise text-xs"><Bell className="w-4 h-4 inline mr-1" />{i18nText("Hatırlat")}</button>}
              </div>
            );
          })}
        </div>

        {showReminder && (isDemoMode() ? <p className="text-xs text-amber-200">{i18nText("Demo içeriği için gerçek takip planı oluşturulmaz. Kendi taramanızın ardından hatırlatma oluşturabilirsiniz.")}</p> : <SkinReminderForm />)}
        {/* Footer */}
        <div className="text-right">
          <button
            onClick={onClose}
            className="px-5 py-2 text-xs font-semibold text-slate-300 hover:text-white bg-slate-900 border border-slate-800 rounded-lg hover:bg-slate-800 transition-colors cursor-pointer"
          >{i18nText("Kapat ")}</button>
        </div>
    </AccessibleDialog>
  );
};
