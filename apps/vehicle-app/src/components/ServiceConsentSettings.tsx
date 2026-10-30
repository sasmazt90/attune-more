'use client';
import {useTranslations} from '../i18n/LanguageProvider';

import {useState} from 'react';
import {HealthService,SERVICE_REQUIREMENTS,setServiceConsent,useServiceAllowed,MENTAL_HISTORY_COPY,useMentalHistoryAllowed,setMentalHistoryConsent} from '../utils/serviceConsent';
import {HEALTH_MODULES} from '../utils/healthModules';
function ServiceRow({service}:{service:HealthService}) {
 const {text:i18nText,node:i18nNode}=useTranslations();
 const allowed=useServiceAllowed(service),[error,setError]=useState('');
 return <div className="border border-white/10 rounded-xl p-4 flex flex-wrap items-center gap-3"><div className="flex-1 min-w-48"><h3 className="font-bold">{i18nNode(HEALTH_MODULES[service].name)}</h3><p className="text-sm text-slate-300">{i18nNode(allowed?'Hizmet izni açık':'Hizmet izni verilmedi; ilgili sayfada izin verebilirsiniz.')}</p>{error&&<p role="alert">{i18nNode(error)}</p>}</div>{allowed&&<button className="min-h-11 px-4 border border-white/20 rounded-xl" onClick={()=>{try{setServiceConsent(service,null);}catch{setError('İzin değişikliği kaydedilemedi.');}}}>{i18nText("İzni kaldır")}</button>}</div>;
}
function PriorSummaryPermission(){
 const {text}=useTranslations(),allowed=useServiceAllowed('mental'),checked=useMentalHistoryAllowed();
 const [error,setError]=useState('');
 return <div className="space-y-2"><label className="flex gap-3 text-sm"><input type="checkbox" disabled={!allowed} checked={checked} onChange={e=>{try{setMentalHistoryConsent(e.target.checked);setError('');}catch{setError('İzin değişikliği kaydedilemedi.');}}}/>{text(MENTAL_HISTORY_COPY)}</label><p className="text-sm text-slate-300">{text('Seçilen özetler OpenAI tarafından işlenir. İzni kaldırmak mevcut geçmiş kayıtlarını silmez.')}</p>{error&&<p role="alert">{text(error)}</p>}</div>;
}
export function ServiceConsentSettings(){
 const {text:i18nText,node:i18nNode}=useTranslations();return <section data-service-settings className="rounded-2xl border border-white/10 bg-cockpit-surface p-6 space-y-4"><h2 className="text-xl font-bold">{i18nText("Sağlık hizmeti işleme izinleri")}</h2>{(Object.keys(SERVICE_REQUIREMENTS) as HealthService[]).map(id=><ServiceRow key={id} service={id}/>)}<PriorSummaryPermission/></section>;}
