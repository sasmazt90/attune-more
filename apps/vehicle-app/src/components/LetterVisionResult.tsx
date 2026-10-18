'use client';
import Link from 'next/link';
import {careHref} from '../utils/healthModules';
import {type LetterResult, performanceBySize, performanceForEye} from '../utils/spokenVision';
import {CardCarousel} from './CardCarousel';
const percent=(value:number|null)=>value===null?'Yeterli yanıt yok':`%${Math.round(value)}`;
export function LetterVisionResult({result,showReferral=true}:{result:LetterResult;showReferral?:boolean}){
 const items=(['RIGHT','LEFT'] as const).map(eye=>{
  const summary=performanceForEye(result.trials,eye),rows=performanceBySize(result.trials,eye);
  return {id:eye,content:<article data-eye-result={eye} className="w-full min-w-0 rounded-2xl border border-white/10 bg-slate-950/60 p-4 space-y-4">
   <h3 className="text-lg font-bold">{eye==='RIGHT'?'Sağ göz':'Sol göz'}</h3>
   <dl data-eye-summary className="grid grid-cols-2 gap-3">{[
    ['Harf tanımlama skoru',percent(summary.letter.percentage)],['Harf yönü skoru',percent(summary.orientation.percentage)],
    ['Toplam ortalama skor',percent(summary.average)],['Geçerli yanıt sayısı',String(summary.valid)]
   ].map(([label,value])=><div key={label} className="rounded-xl border border-white/10 p-3"><dt className="text-sm font-semibold text-slate-300">{label}</dt><dd className="mt-2 text-lg font-bold text-togg-turquoise">{value}</dd></div>)}</dl>
   {summary.notVisible>0&&<p className="text-sm text-slate-400">Göremiyorum yanıtı: {summary.notVisible}</p>}
   {rows.length>0&&<details><summary className="min-h-11 cursor-pointer py-3 text-sm font-semibold text-slate-300">Boyut bazlı sonuçlar</summary><div className="max-h-48 overflow-auto rounded-xl border border-white/10"><table className="w-full text-left text-xs"><thead className="sticky top-0 bg-slate-950"><tr>{['Harf boyutu','Harf yönü skoru','Harf tanımlama skoru','Toplam ortalama skor'].map(label=><th key={label} className="p-2 font-semibold">{label}</th>)}</tr></thead><tbody>{rows.map(row=><tr key={row.size} className="border-t border-white/10"><td className="p-2">{row.widthCssPx.toFixed(1)} × {row.heightCssPx.toFixed(1)}</td><td className="p-2">{percent(row.orientation.percentage)}</td><td className="p-2">{percent(row.letter.percentage)}</td><td className="p-2">{percent(row.average)}</td></tr>)}</tbody></table></div></details>}
  </article>};
 });
 return <section data-letter-result className="min-w-0 space-y-4"><CardCarousel label="Harf tanıma sonucu" items={items} itemWidthClassName="basis-[92%] md:basis-[calc(50%-6px)]"/>{showReferral&&<Link className="inline-flex min-h-11 items-center rounded-xl border border-white/20 px-4" href={careHref('vision')}>Uzman seçenekleri</Link>}</section>;
}
