'use client';
import {CardCarousel} from '../CardCarousel';
import {useTranslations} from '../../i18n/LanguageProvider';
import type {HealthRecord} from '../../utils/healthRecords';
/** Each card retains its own ID. Opening an older card never substitutes the latest result. */
export function HearingHistoryCards({records,parked,onOpen}:{records:HealthRecord[];parked:boolean;onOpen:(id:string)=>void}){
 const {text:t,locale}=useTranslations();
 return <div className="px-4 pb-4 min-w-0" data-hearing-history-cards><CardCarousel label="Kulak kayıtları" itemWidthClassName="basis-full" items={records.map(record=>{
  const at=Date.parse(record.timestamp||record.date||record.completedAt||'');
  return {id:record.id,content:<button type="button" disabled={!parked} aria-haspopup="dialog" onClick={()=>onOpen(record.id)} data-hearing-history-open={record.id} className="w-full min-h-28 rounded-xl border border-white/10 bg-[#0d1521] p-3 text-left disabled:opacity-40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-togg-turquoise"><time className="block text-xs text-slate-400">{Number.isFinite(at)?new Date(at).toLocaleString(locale):t('Tarih kaydı yok')}</time><span className="block mt-2 text-sm text-slate-200">{t(record.thresholds?'Saf ses testi':'Gürültüde sayı testi')}</span><span className="block mt-2 text-xs text-togg-turquoise">{t('Sonucu Aç')}</span></button>};
 })}/></div>;
}
