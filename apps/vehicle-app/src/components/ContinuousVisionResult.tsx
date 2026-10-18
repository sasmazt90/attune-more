'use client';
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
  return <div data-orientation-result className="space-y-4">
    <h2 className="text-xl font-bold">Yön hizalama ön değerlendirmesi</h2>
    <p>{result.validTrials} geçerli deneme · {result.notVisible} göremedi</p>
    <p className="text-sm text-amber-200">Görme keskinliği bu protokolle hesaplanmadı. Göz örtülmesi kamera tarafından doğrulanmadı; mutlak mesafe ölçülmedi.</p>
    <div className="overflow-x-auto"><table className="w-full text-sm text-left"><thead><tr><th className="p-2">Koşul</th><th className="p-2">Yanıtlanan</th><th className="p-2">Göremedi</th><th className="p-2">Ortalama hata</th></tr></thead><tbody>{(['RIGHT','LEFT','BOTH'] as const).map(eye=>{
      const s=summarizeContinuousTrials(result.trials.filter(t=>t.eye===eye));
      return <tr key={eye}><th className="p-2 font-normal">{eye==='RIGHT'?'Sağ göz':eye==='LEFT'?'Sol göz':'İki göz / kontrast'}</th><td className="p-2">{s.visible}/{s.validTrials}</td><td className="p-2">{s.notVisible}</td><td className="p-2">{s.meanAngularError===null?'Açı yanıtı yok':s.meanAngularError.toFixed(1)+'°'}</td></tr>;
    })}</tbody></table></div>
    <p className="text-sm text-slate-300">Açı ortalaması yalnız yön yanıtlarından hesaplandı. Göremedi yanıtları ayrıca gösterilir; başarı sayılmaz. Teknik olarak geçersiz {result.invalidPresentations} sunum yeniden başlatıldı.</p>
    <details className="space-y-3"><summary className="min-h-11 cursor-pointer py-3 text-togg-turquoise">Denemeler ve ölçüm sınırları</summary><p>Her koşulda sekiz geçerli deneme, toplam 24. Boyut/kontrast değişimi mühendislik keşif düzenidir; klinik eşik, gözlük numarası veya yönlendirme skoru değildir. Ekran ölçeği manuel kart eşleştirmesidir; cihaz doğrulaması değildir. Mesafe yalnız başlangıca göre yüz ölçeğiyle izlendi.</p>
      {(['RIGHT','LEFT','BOTH'] as const).map(eye=><p key={eye}>{eyeInstruction(eye)}</p>)}
      <ol className="space-y-2">{result.trials.map((t,i)=><li key={i} className="text-sm">{i+1}. {t.eye==='RIGHT'?'Sağ':t.eye==='LEFT'?'Sol':'İki göz'} · {t.visibility==='not-visible'?'Göremedi':'Hata '+t.minimumCircularError?.toFixed(1)+'°'} · Boyut {t.stimulusSizeMm.toFixed(2)} mm (manuel ölçek) · Kontrast {(t.contrast*100).toFixed(1)}% · {Math.round(t.responseMs)} ms</li>)}</ol>
    </details>
  <Link className="inline-flex min-h-11 items-center rounded-xl border border-white/20 px-4" href={careHref('vision')}>Uzman seçenekleri</Link></div>;
}
