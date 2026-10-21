'use client';
import {useTranslations} from '../i18n/LanguageProvider';

import Link from 'next/link';
import {careHref} from '../utils/healthModules';
import { ContinuousTrial, summarizeContinuousTrials, eyeInstruction } from '../utils/continuousVision';
export interface OrientationResult {
  id:string; date:string; protocolVersion:'landolt-orientation-guided-v2'; trials:ContinuousTrial[];
  validTrials:number; visible:number; notVisible:number; meanAngularError:number|null; acuityStatus:string;
  invalidPresentations:number; screenCalibration:unknown; distanceMethod:'relative-face-scale-only';
  eyeOcclusionVerification:'not-camera-verified-user-instruction'; [key:string]:unknown;
}
export function ContinuousVisionResult({result}:{result:OrientationResult}) {
 const {text:i18nText,node:i18nNode}=useTranslations();
  return <div data-orientation-result className="space-y-4">
    <h2 className="text-xl font-bold">{i18nText("Yön hizalama ön değerlendirmesi")}</h2>
    <p>{i18nNode(result.validTrials)}{i18nText(" geçerli deneme · ")}{i18nNode(result.notVisible)}{i18nText(" göremedi")}</p>
    <p className="text-sm text-amber-200">{i18nText("Görme keskinliği bu protokolle hesaplanmadı. Göz örtülmesi kamera tarafından doğrulanmadı; mutlak mesafe ölçülmedi.")}</p>
    <div className="overflow-x-auto"><table className="w-full text-sm text-left"><thead><tr><th className="p-2">{i18nText("Koşul")}</th><th className="p-2">{i18nText("Yanıtlanan")}</th><th className="p-2">{i18nText("Göremedi")}</th><th className="p-2">{i18nText("Ortalama hata")}</th></tr></thead><tbody>{(['RIGHT','LEFT','BOTH'] as const).map(eye=>{
      const s=summarizeContinuousTrials(result.trials.filter(t=>t.eye===eye));
      return <tr key={eye}><th className="p-2 font-normal">{i18nNode(eye==='RIGHT'?'Sağ göz':eye==='LEFT'?'Sol göz':'İki göz / kontrast')}</th><td className="p-2">{i18nNode(s.visible)}/{i18nNode(s.validTrials)}</td><td className="p-2">{i18nNode(s.notVisible)}</td><td className="p-2">{i18nNode(s.meanAngularError===null?'Açı yanıtı yok':s.meanAngularError.toFixed(1)+'°')}</td></tr>;
    })}</tbody></table></div>
    <p className="text-sm text-slate-300">{i18nText("Açı ortalaması yalnız yön yanıtlarından hesaplandı. Göremedi yanıtları ayrıca gösterilir; başarı sayılmaz. Teknik olarak geçersiz ")}{i18nNode(result.invalidPresentations)}{i18nText(" sunum yeniden başlatıldı.")}</p>
    <details className="space-y-3"><summary className="min-h-11 cursor-pointer py-3 text-togg-turquoise">{i18nText("Denemeler ve ölçüm sınırları")}</summary><p>{i18nText("Her koşulda sekiz geçerli deneme, toplam 24. Boyut/kontrast değişimi mühendislik keşif düzenidir; klinik eşik, gözlük numarası veya yönlendirme skoru değildir. Ekran ölçeği manuel kart eşleştirmesidir; cihaz doğrulaması değildir. Mesafe yalnız başlangıca göre yüz ölçeğiyle izlendi.")}</p>
      {(['RIGHT','LEFT','BOTH'] as const).map(eye=><p key={eye}>{i18nNode(eyeInstruction(eye))}</p>)}
      <ol className="space-y-2">{result.trials.map((t,i)=><li key={i} className="text-sm">{i18nNode(i+1)}. {i18nNode(t.eye==='RIGHT'?'Sağ':t.eye==='LEFT'?'Sol':'İki göz')} · {i18nNode(t.visibility==='not-visible'?'Göremedi':'Hata '+t.minimumCircularError?.toFixed(1)+'°')}{i18nText(" · Boyut ")}{i18nNode(t.stimulusSizeMm.toFixed(2))}{i18nText(" mm (manuel ölçek) · Kontrast ")}{i18nNode((t.contrast*100).toFixed(1))}% · {i18nNode(Math.round(t.responseMs))}{i18nText(" ms")}</li>)}</ol>
    </details>
  <Link className="inline-flex min-h-11 items-center rounded-xl border border-white/20 px-4" href={careHref('vision')}>{i18nText("Uzman seçenekleri")}</Link></div>;
}
