'use client';
import React from 'react';
import {ChevronLeft,ChevronRight} from 'lucide-react';
import {useTranslations} from '../i18n/LanguageProvider';

export function ResultArrow({direction,label,onClick}:{direction:'previous'|'next';label:string;onClick:()=>void}){
 const {text:t}=useTranslations();
 const Icon=direction==='previous'?ChevronLeft:ChevronRight;
 return <button type="button" onClick={onClick} aria-label={t(label)} className="shrink-0 min-w-[48px] min-h-[48px] sm:min-w-[52px] sm:min-h-[52px] rounded-2xl bg-[#1a2533] hover:bg-[#223043] flex items-center justify-center text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-300"><Icon aria-hidden="true" className="w-6 h-6"/></button>;
}

/** Result regions always have navigation, independently of finding count. The arrows sit either side of the photo;
 * the tabs and the card already name the page, so they carry no title of their own. */
export function HealthPhotoNavigation({previousLabel,nextLabel,onPrevious,onNext,children}:{previousLabel:string;nextLabel:string;onPrevious:()=>void;onNext:()=>void;children:React.ReactNode}){
 const {text:t}=useTranslations();
 return <div role="group" aria-label={t('Sonuç sayfaları')} className="flex w-full items-center justify-center gap-1.5 sm:gap-2" data-health-result-navigation>
  <ResultArrow direction="previous" label={previousLabel} onClick={onPrevious}/>
  <div className="min-w-0 flex-1 flex justify-center">{children}</div>
  <ResultArrow direction="next" label={nextLabel} onClick={onNext}/>
 </div>;
}
