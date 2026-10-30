'use client';
import {useTranslations} from '../i18n/LanguageProvider';

import {useEffect,useState} from 'react';
import {usePathname,useRouter} from 'next/navigation';
import {AccessibleDialog} from './AccessibleDialog';
import {HEALTH_MODULES} from '../utils/healthModules';
import {HealthService,SERVICE_REQUIREMENTS,setServiceConsent,useServiceAllowed,MENTAL_HISTORY_COPY} from '../utils/serviceConsent';

function ServiceGate({service,children}:{service:HealthService;children:React.ReactNode}) {
 const {text:i18nText,node:i18nNode}=useTranslations();
 const allowed=useServiceAllowed(service),router=useRouter();
 const [checked,setChecked]=useState<string[]>([]),[error,setError]=useState('');
 const [priorSummaries,setPriorSummaries]=useState(false);
 useEffect(()=>{if(!allowed){setChecked([]);setPriorSummaries(false);window.dispatchEvent(new Event('attune-guidance-cancel'));}},[allowed]);
 if(allowed)return <>{i18nNode(children)}</>;
 return <AccessibleDialog title={i18nText(`${HEALTH_MODULES[service].name} hizmet izni`)} onClose={()=>router.push('/')} className="max-w-xl w-full rounded-2xl bg-cockpit-surface border border-white/20 p-6 space-y-5">
  <h1 className="text-xl font-bold">{i18nNode(HEALTH_MODULES[service].name)}{i18nText(" hizmet izni")}</h1>
  <p className="text-sm text-slate-300">{i18nText("Devam etmeden önce aşağıdaki işlem izinlerini inceleyin. Kamera ve mikrofon yalnız Başlat eyleminizden sonra ayrıca istenir. Saklama tercihleriniz değişmez; izinleri Gizlilik & İzinler sayfasından kaldırabilirsiniz.")}</p>
  {SERVICE_REQUIREMENTS[service].map(([id,text])=><label key={id} className="flex gap-3 items-start text-sm"><input type="checkbox" className="h-5 w-5 mt-1 shrink-0" checked={checked.includes(id)} onChange={e=>setChecked(v=>e.target.checked?[...v,id]:v.filter(x=>x!==id))}/><span>{i18nNode(text)}</span></label>)}
  {service==='mental'&&<details><summary>{i18nText('Veri işleme ayrıntıları')}</summary><p className="text-sm text-slate-300">{i18nText('Konuşma metni ve özetler OpenAI tarafından işlenir. Konuşma tanıma hizmeti sesi buluta aktarabilir. Yerel ses üretimi cihazda kalır; çevrimiçi tarayıcı sesleri seçildiğinde ilgili sağlayıcı metni alabilir.')}</p></details>}
  {service==='mental'&&<div className="space-y-2"><label className="flex gap-3 items-start text-sm"><input type="checkbox" checked={priorSummaries} onChange={e=>setPriorSummaries(e.target.checked)}/><span>{i18nText(MENTAL_HISTORY_COPY)}</span></label><p className="text-sm text-slate-300">{i18nText('Seçilen özetler OpenAI tarafından işlenir. İzni kaldırmak mevcut geçmiş kayıtlarını silmez.')}</p></div>}
  {error&&<p role="alert" className="text-amber-200 text-sm">{i18nNode(error)}</p>}
  <div className="flex flex-wrap gap-3"><button className="min-h-11 px-5 rounded-xl bg-togg-turquoise text-togg-darkBlue disabled:opacity-40" disabled={!SERVICE_REQUIREMENTS[service].every(([id])=>checked.includes(id))} onClick={()=>{try{setServiceConsent(service,checked,priorSummaries);}catch{setError('İzin kaydedilemedi. İşlem başlatılmadı. Tarayıcı depolama ayarlarını kontrol edin.');}}}>{i18nText("İzin ver ve devam et")}</button><button className="min-h-11 px-4 rounded-xl border border-white/20" onClick={()=>router.push('/')}>{i18nText("Şimdi değil")}</button></div>
 </AccessibleDialog>;
}
export function HealthConsentGate({children}:{children:React.ReactNode}) {
 const {text:i18nText,node:i18nNode}=useTranslations();
 const path=usePathname(),service=(Object.keys(SERVICE_REQUIREMENTS) as HealthService[]).find(id=>HEALTH_MODULES[id].route===path);
 return service?<ServiceGate key={service} service={service}>{i18nNode(children)}</ServiceGate>:<>{i18nNode(children)}</>;
}
