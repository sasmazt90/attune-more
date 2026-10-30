'use client';
import {useSyncExternalStore} from 'react';

export const SERVICE_CONSENT_KEY='attune_health_processing_v1';
export const SERVICE_REQUIREMENTS={
 skin:[['local','Yüz görüntümün ve görünüm göstergelerimin bu cihazda geçici işlenmesine izin veriyorum.']],
 dental:[['local','Diş fotoğraflarımın bu cihazda geçici işlenmesine izin veriyorum.']],
 hearing:[['local','Kulaklık sesleri ve yanıtlarımla yerel işitme testinin yapılmasına izin veriyorum.']],
 vision:[['local','Kamera görüntüsü ve konuşma yanıtlarımın göz görevi için geçici işlenmesine izin veriyorum.'],['speech','Attune.more sesli yönergelerini ve konuşma yanıtlarım için tarayıcı/cihaz konuşma tanıma hizmetini kullanmaya izin veriyorum; tanıma hizmeti sesi buluta aktarabilir.']],
 mental:[['recognition','Sesimin tarayıcı/cihaz konuşma tanıma hizmetinde metne çevrilmesine izin veriyorum; bu hizmet sesi buluta aktarabilir.'],['conversation','Konuşma metnimin Attune.more yanıtları, geçici oturum belleği ve özet için işlenmesine izin veriyorum.'],['speech-output-v2','Yanıt metninin seçtiğim dilde yerel Attune.more sesiyle veya açıkça seçtiğim tarayıcı/cihaz sesiyle okunmasına izin veriyorum. Çevrimiçi tarayıcı sesi için ayrıca sağlayıcı izni gerekir.']]
} as const;
export type HealthService=keyof typeof SERVICE_REQUIREMENTS;
export const MENTAL_HISTORY_PERMISSION='prior-summaries-v1';
export const MENTAL_HISTORY_COPY='İsteğe bağlı: İlgili önceki görüşme özetlerimin yeni Attune.more özetinde kullanılmasına izin veriyorum. Bu izin olmadan da görüşmeye başlayabilirim.';
type ConsentDocument={version:1;services:Partial<Record<HealthService,{at:string;permissions:string[];optionalPermissions?:string[]}>>};
function readDocument():ConsentDocument {
 const raw=localStorage.getItem(SERVICE_CONSENT_KEY);
 if(raw===null)return {version:1,services:{}};
 const value=JSON.parse(raw);
 if(value?.version!==1||!value.services||typeof value.services!=='object')throw Error('CONSENT_STORAGE_INVALID');
 return value;
}
export function serviceAllowed(service:HealthService):boolean {
 try {const record=readDocument().services[service];return Array.isArray(record?.permissions)&&SERVICE_REQUIREMENTS[service].every(([id])=>record!.permissions.includes(id));}catch{return false;}
}
export function mentalHistoryAllowed():boolean {
 try{const optional=readDocument().services.mental?.optionalPermissions;return serviceAllowed('mental')&&Array.isArray(optional)&&optional.includes(MENTAL_HISTORY_PERMISSION);}catch{return false;}
}
export function setMentalHistoryConsent(allowed:boolean){
 const doc=readDocument(),record=doc.services.mental;
 if(!record||!serviceAllowed('mental'))throw Error('SERVICE_PERMISSION_REQUIRED');
 record.optionalPermissions=allowed?[MENTAL_HISTORY_PERMISSION]:[];
 writeDocument(doc);
}
function writeDocument(doc:ConsentDocument){
 const raw=JSON.stringify(doc);localStorage.setItem(SERVICE_CONSENT_KEY,raw);
 if(localStorage.getItem(SERVICE_CONSENT_KEY)!==raw)throw Error('CONSENT_WRITE_FAILED');
 window.dispatchEvent(new Event('attune-service-consent'));window.dispatchEvent(new Event('attune-privacy'));
}
export function setServiceConsent(service:HealthService,permissions:string[]|null,priorSummaries=false) {
 const doc=readDocument();
 if(permissions===null)delete doc.services[service];
 else {
  if(!SERVICE_REQUIREMENTS[service].every(([id])=>permissions.includes(id)))throw Error('EXPLICIT_PERMISSIONS_REQUIRED');
  doc.services[service]={at:new Date().toISOString(),permissions:SERVICE_REQUIREMENTS[service].map(([id])=>id),...(service==='mental'?{optionalPermissions:priorSummaries?[MENTAL_HISTORY_PERMISSION]:[]}: {})};
 }
 writeDocument(doc);
}
function subscribe(listener:()=>void) {
 window.addEventListener('storage',listener);window.addEventListener('attune-service-consent',listener);
 return ()=>{window.removeEventListener('storage',listener);window.removeEventListener('attune-service-consent',listener);};
}
export function useServiceAllowed(service:HealthService){return useSyncExternalStore(subscribe,()=>serviceAllowed(service),()=>false);}
export function useMentalHistoryAllowed(){return useSyncExternalStore(subscribe,mentalHistoryAllowed,()=>false);}
