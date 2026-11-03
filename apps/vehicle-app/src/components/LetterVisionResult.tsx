'use client';
import {useTranslations} from '../i18n/LanguageProvider';

import Link from 'next/link';
import {careHref} from '../utils/healthModules';
import {LETTER_RULES, LETTER_VISIBILITY_STOP, type LetterResult, performanceBySize, performanceForEye} from '../utils/spokenVision';
import {CardCarousel} from './CardCarousel';
const percent=(value:number|null)=>value===null?'Yeterli yanıt yok':`%${Math.round(value)}`;
export function LetterVisionResult({result,showReferral=true}:{result:LetterResult;showReferral?:boolean}){
 const {text:i18nText,node:i18nNode}=useTranslations();
 const stopped=result.stopReason===LETTER_VISIBILITY_STOP;
 const items=(['RIGHT','LEFT'] as const).map(eye=>{
  const summary=performanceForEye(result.trials,eye),rows=performanceBySize(result.trials,eye);
  return {id:eye,content:<article data-eye-result={eye} className="w-full min-w-0 rounded-2xl border border-white/10 bg-slate-950/60 p-4 space-y-4">
   <h3 className="text-lg font-bold">{i18nNode(eye==='RIGHT'?'Sağ göz':'Sol göz')}</h3>
   <dl data-eye-summary className="grid grid-cols-2 gap-3">{[
    ['Harf tanımlama skoru',percent(summary.letter.percentage)],['Harf yönü skoru',percent(summary.orientation.percentage)],
    ['Toplam ortalama skor',percent(summary.average)],['Geçerli yanıt sayısı',String(summary.valid)]
   ].map(([label,value])=><div key={label} className="rounded-xl border border-white/10 p-3"><dt className="text-sm font-semibold text-slate-300">{i18nNode(label)}</dt><dd className="mt-2 text-lg font-bold text-togg-turquoise">{i18nNode(value)}</dd></div>)}</dl>
   {summary.notVisible>0&&<p className="text-sm text-slate-400">{i18nText("Göremiyorum yanıtı: ")}{i18nNode(summary.notVisible)}</p>}
   {stopped&&summary.valid<LETTER_RULES.perEye&&<p data-eye-unmeasured className="text-sm text-amber-200">{i18nText("Ölçülmeyen harf: ")}{i18nNode(LETTER_RULES.perEye-summary.valid)}</p>}
   {rows.length>0&&<details><summary className="min-h-11 cursor-pointer py-3 text-sm font-semibold text-slate-300">{i18nText("Boyut bazlı sonuçlar")}</summary><div className="max-h-48 overflow-auto rounded-xl border border-white/10"><table className="w-full text-left text-xs"><thead className="sticky top-0 bg-slate-950"><tr>{['Harf boyutu','Harf yönü skoru','Harf tanımlama skoru','Toplam ortalama skor'].map(label=><th key={label} className="p-2 font-semibold">{i18nNode(label)}</th>)}</tr></thead><tbody>{rows.map(row=><tr key={row.size} className="border-t border-white/10"><td className="p-2">{i18nNode(row.widthCssPx.toFixed(1))} × {i18nNode(row.heightCssPx.toFixed(1))}</td><td className="p-2">{i18nNode(percent(row.orientation.percentage))}</td><td className="p-2">{i18nNode(percent(row.letter.percentage))}</td><td className="p-2">{i18nNode(percent(row.average))}</td></tr>)}</tbody></table></div></details>}
  </article>};
 });
 return <section data-letter-result className="min-w-0 space-y-4">{stopped&&<p role="status" data-letter-stopped className="rounded-xl border border-amber-400/40 bg-amber-950/40 p-3 text-sm text-amber-100">{i18nText("Eksik sonuç: Görev, ikinci “göremiyorum” yanıtında durdu. Skorlar yalnız verilen yanıtları kapsar. Bu klinik bir değerlendirme değildir; görmenizle ilgili endişeniz varsa bir göz uzmanına danışın.")}</p>}<CardCarousel label="Harf tanıma sonucu" items={items} itemWidthClassName="basis-[92%] md:basis-[calc(50%-6px)]"/>{showReferral&&<Link className="inline-flex min-h-11 items-center rounded-xl border border-white/20 px-4" href={careHref('vision')}>{i18nText("Uzman seçenekleri")}</Link>}</section>;
}
