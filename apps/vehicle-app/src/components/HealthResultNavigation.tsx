'use client';
import React from 'react';
import {ChevronLeft,ChevronRight} from 'lucide-react';
import {useTranslations} from '../i18n/LanguageProvider';

/** Result regions/views always have navigation, independently of finding count. */
export function HealthResultNavigation({title,previousLabel,nextLabel,onPrevious,onNext,index,total}:{title:string;previousLabel:string;nextLabel:string;onPrevious:()=>void;onNext:()=>void;index:number;total:number}){
 const {text:t}=useTranslations();
 return <nav aria-label={t('Sonuç sayfaları')} className="flex items-center justify-between gap-3 rounded-[26px] bg-[#0f1724] p-4" data-health-result-navigation>
  <button type="button" onClick={onPrevious} aria-label={t(previousLabel)} className="min-w-[52px] min-h-[52px] rounded-2xl bg-[#1a2533] flex items-center justify-center text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-300"><ChevronLeft aria-hidden="true"/></button>
  <div className="min-w-0 text-center text-white"><span className="text-sm text-cyan-300 tabular-nums">{index+1} / {total}</span><h2 className="text-xl font-bold">{t(title)}</h2></div>
  <button type="button" onClick={onNext} aria-label={t(nextLabel)} className="min-w-[52px] min-h-[52px] rounded-2xl bg-[#1a2533] flex items-center justify-center text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-300"><ChevronRight aria-hidden="true"/></button>
 </nav>;
}
