'use client';
import Link from 'next/link';
import {useTranslations} from '../i18n/LanguageProvider';
import {PRODUCT_TAGLINE} from '../utils/brand';
import {ProductWordmark} from './ProductWordmark';
export function LocalizedFooter(){
 const {text:t}=useTranslations();
 return <footer className="border-t border-cockpit-border/40 py-3 px-6 text-center text-xs text-slate-500 bg-cockpit-surface/50">
  <div className="flex flex-wrap items-center justify-center gap-x-2 gap-y-1 max-w-[1600px] mx-auto text-[11px]">
   <span className="font-semibold text-slate-300 tracking-wide"><ProductWordmark/></span><span>•</span>
   <span className="text-slate-400">{t(PRODUCT_TAGLINE)}</span><span>•</span>
   <span>{t('Tıbbi teşhis içermez; ön değerlendirme ve değişim takibi amaçlıdır.')}</span>
  </div>
  <div className="mt-2"><Link href="/privacy" className="inline-flex min-h-touch items-center px-3 text-togg-turquoise underline underline-offset-4 focus-visible:outline focus-visible:outline-2">{t('Gizlilik & İzinler')}</Link></div>
 </footer>;
}
