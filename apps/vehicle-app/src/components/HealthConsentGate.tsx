'use client';
import {useEffect,useState} from 'react';
import {usePathname,useRouter} from 'next/navigation';
import {AccessibleDialog} from './AccessibleDialog';
import {HEALTH_MODULES} from '../utils/healthModules';
import {HealthService,SERVICE_REQUIREMENTS,setServiceConsent,useServiceAllowed} from '../utils/serviceConsent';

function ServiceGate({service,children}:{service:HealthService;children:React.ReactNode}) {
 const allowed=useServiceAllowed(service),router=useRouter();
 const [checked,setChecked]=useState<string[]>([]),[error,setError]=useState('');
 useEffect(()=>{if(!allowed){setChecked([]);window.dispatchEvent(new Event('attune-guidance-cancel'));}},[allowed]);
 if(allowed)return <>{children}</>;
 return <AccessibleDialog title={`${HEALTH_MODULES[service].name} hizmet izni`} onClose={()=>router.push('/')} className="max-w-xl w-full rounded-2xl bg-cockpit-surface border border-white/20 p-6 space-y-5">
  <h1 className="text-xl font-bold">{HEALTH_MODULES[service].name} hizmet izni</h1>
  <p className="text-sm text-slate-300">Devam etmeden önce aşağıdaki işlem izinlerini inceleyin. Kamera ve mikrofon yalnız Başlat eyleminizden sonra ayrıca istenir. Saklama tercihleriniz değişmez; izinleri Gizlilik &amp; İzinler sayfasından kaldırabilirsiniz.</p>
  {SERVICE_REQUIREMENTS[service].map(([id,text])=><label key={id} className="flex gap-3 items-start text-sm"><input type="checkbox" className="h-5 w-5 mt-1 shrink-0" checked={checked.includes(id)} onChange={e=>setChecked(v=>e.target.checked?[...v,id]:v.filter(x=>x!==id))}/><span>{text}</span></label>)}
  {error&&<p role="alert" className="text-amber-200 text-sm">{error}</p>}
  <div className="flex flex-wrap gap-3"><button className="min-h-11 px-5 rounded-xl bg-togg-turquoise text-togg-darkBlue disabled:opacity-40" disabled={!SERVICE_REQUIREMENTS[service].every(([id])=>checked.includes(id))} onClick={()=>{try{setServiceConsent(service,checked);}catch{setError('İzin kaydedilemedi. İşlem başlatılmadı. Tarayıcı depolama ayarlarını kontrol edin.');}}}>İzin ver ve devam et</button><button className="min-h-11 px-4 rounded-xl border border-white/20" onClick={()=>router.push('/')}>Şimdi değil</button></div>
 </AccessibleDialog>;
}
export function HealthConsentGate({children}:{children:React.ReactNode}) {
 const path=usePathname(),service=(Object.keys(SERVICE_REQUIREMENTS) as HealthService[]).find(id=>HEALTH_MODULES[id].route===path);
 return service?<ServiceGate key={service} service={service}>{children}</ServiceGate>:<>{children}</>;
}
