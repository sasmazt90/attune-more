'use client';

import {useTranslations} from '../i18n/LanguageProvider';
import Image from 'next/image';
import type {ReactNode} from 'react';
import {Camera,Eye,Headphones,HeartPulse,Mic,Scan,Sun,Volume2} from 'lucide-react';
export type PreparationModule='skin'|'vision'|'dental'|'hearing'|'mental';
export const HEALTH_START_CARD='bg-[#0c1424]/90 border border-slate-800/90 rounded-3xl p-6 md:p-8 shadow-2xl w-full';
export const HEALTH_START_ACTION='min-h-11 w-full sm:w-auto px-8 py-3.5 rounded-full bg-[#00d2eb] hover:bg-[#00e5ff] text-slate-950 font-bold text-base shadow-[0_0_25px_rgba(0,210,235,0.4)] transition-colors disabled:opacity-40 disabled:cursor-not-allowed uppercase tracking-wider';
export const HEALTH_START_SECONDARY='min-h-11 w-full sm:w-auto px-6 py-3.5 rounded-full border border-togg-turquoise/40 text-togg-turquoise font-bold disabled:opacity-40';
const CONTENT={
 skin:{title:'Cilt Analizi',description:'Gözlüğünüzü çıkarın. Kameraya doğru bakın ve başınızı sabit tutun.',alt:'Başı ve omuzları tam görünen doğal portrede temsili cilt hazırlık ağı',items:[[Eye,'Yüz hizasını koruyun'],[Sun,'İyi ışık koşulu sağlayın'],[Scan,'Net görüntü elde edin']]},
 dental:{title:'Diş Analizi',description:'Kamera görünümlerini izleyebilir veya diş fotoğrafı yükleyebilirsiniz.',alt:'Dik başlı doğal gülümsemede, görünen diş eğrisini izleyen temsili hazırlık ağı',items:[[Camera,'Ön, sağ, sol ve rahat kapanış görünümü'],[Sun,'Dişleriniz iyi ışıkta net görünsün'],[Scan,'Ağzınıza cisim sokmadan rahatça gülümseyin']]},
 hearing:{title:'İşitme Testi',description:'Kulaklığınızı takın; ses ayarını rahat bir düzeyde tutun.',alt:'Başının tamamı görünen doğal portrede kulağa yönelen temsili ses dalgaları',items:[[Headphones,'Stereo kulaklığınızı takın'],[Volume2,'Sessiz bir ortamda rahat ses ayarını koruyun'],[Scan,'Saf ses ve gürültüde sayı testlerini izleyin']]},
 vision:{title:'Göz Testi',description:'İki gözünüz açık başlayın. Sonra belirtilen gözü kapatın veya örtün.',alt:'Başı tam görünen doğal portrede ekrandaki harf görevini temsil eden sade öğeler',items:[[Eye,'Açık gözünüzle ekrandaki harfe bakın'],[Scan,'Harfi ve yönünü istediğiniz sırada söyleyin'],[Mic,'Harfi doğrudan veya bir kelimeyle kodlayın'],[Volume2,'Yönerge bittikten sonra “Dinliyor” yazısını bekleyip yanıtlayın']]},
 mental:{title:'Görüşme Seansı',description:'',alt:'Başı tam görünen sakin doğal portrede sesli görüşmeyi temsil eden sade dalga',items:[[Mic,'Sesli akış ile sohbete başlayabilirsiniz.'],[Volume2,'Seansa ara verip, devam edebilirsiniz.'],[HeartPulse,'Seans bitirildiğinde temaları analiz edebilirsiniz.']]}
} as const;
/** Preparation only; active, result and history renderers stay separate. */
export function HealthStartCard({module,actions,framed=true,footer}:{module:PreparationModule;actions?:ReactNode;framed?:boolean;footer?:ReactNode}){
 const {text:i18nText,node:i18nNode}=useTranslations();
 const c=CONTENT[module];
 return <div className={framed?HEALTH_START_CARD:undefined} data-health-start={module}>
  <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
   <div className="lg:col-span-6 flex justify-center min-w-0"><div className="relative w-full max-w-[360px] aspect-[3/4] rounded-2xl overflow-hidden" data-health-portrait={module}><Image src={`/assets/${module}-preparation-approved-v3.png`} alt={i18nText(c.alt)} fill sizes="(min-width: 1024px) 360px, (max-width: 480px) 80vw, 360px" className="object-contain" priority/></div></div>
   <div className="lg:col-span-6 space-y-6 max-w-md min-w-0">
    <div className="space-y-1.5"><h2 className="text-3xl font-extrabold text-white tracking-tight">{i18nNode(c.title)}</h2>{c.description&&<p className="text-sm text-slate-300 leading-relaxed">{i18nNode(c.description)}</p>}</div>
    <div className="space-y-3.5 pt-1">{c.items.map(([Icon,text])=><div key={text} className="flex items-center gap-3 text-sm text-slate-200"><div className="w-8 h-8 rounded-full bg-togg-turquoise/15 border border-togg-turquoise/30 flex items-center justify-center text-togg-turquoise shrink-0"><Icon className="w-4 h-4"/></div><span>{i18nNode(text)}</span></div>)}</div>
    {actions&&<div className="flex flex-wrap gap-3 pt-2" data-health-start-actions>{i18nNode(actions)}</div>}{i18nNode(footer)}
   </div>
  </div>
 </div>;
}
