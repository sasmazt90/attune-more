'use client';
import {useTranslations} from '../../i18n/LanguageProvider';
import {ResultValue} from '../ResultValue';
import styles from './hearing.module.css';

type DigitTrial={digits?:number[];answer?:number[];snr?:number;correct?:boolean;repeated?:boolean};
export type DinRecord={id?:string;value?:number|null;validTrials?:number;digitAccuracy?:number|null;tripletAccuracy?:number|null;repeated?:number;history?:DigitTrial[];methodVersion?:string;timestamp?:string};

const finite=(value:unknown):value is number=>typeof value==='number'&&Number.isFinite(value);
const isTrial=(row:DigitTrial)=>Array.isArray(row?.digits)&&Array.isArray(row?.answer);

/** Same reading for the live result and the saved record. Counts come from the stored trials. */
export function dinScores(record:DinRecord){
 const trials=Array.isArray(record.history)?record.history.filter(row=>isTrial(row)&&!row.repeated):[];
 if(trials.length){
  const correct=trials.reduce((n,row)=>n+row.digits!.filter((digit,i)=>digit===row.answer![i]).length,0);
  return {digits:correct,digitTotal:trials.length*3,triplets:trials.filter(row=>row.correct).length,trials:trials.length,rows:trials};
 }
 const count=finite(record.validTrials)?record.validTrials:0;
 return {digits:finite(record.digitAccuracy)?Math.round(record.digitAccuracy*count*3):null,digitTotal:count*3,triplets:finite(record.tripletAccuracy)?Math.round(record.tripletAccuracy*count):null,trials:count,rows:[] as DigitTrial[]};
}

export function HearingDinResult({record,previous}:{record:DinRecord;previous?:DinRecord}){
 const {text:t,node,locale}=useTranslations();
 const score=dinScores(record),number=(value:number)=>new Intl.NumberFormat(locale,{maximumFractionDigits:1,signDisplay:'exceptZero'}).format(value);
 const comparable=previous&&!('thresholds' in previous&&(previous as {thresholds?:unknown}).thresholds)&&previous.methodVersion===record.methodVersion&&finite(previous.value)&&finite(record.value);
 const cards:[string,string][]=[
  ['Doğru sayı',score.digits===null?'—':`${score.digits}/${score.digitTotal}`],
  ['Tam üçlü',score.triplets===null?'—':`${score.triplets}/${score.trials}`],
  ['Geçerli deneme',`${score.trials}`],
 ];
 return <div className="space-y-3" data-din-result data-hearing-result-record={record.id}>
  <div className="grid gap-3 md:grid-cols-2 short:grid-cols-2 items-stretch">
   <section className="rounded-2xl border border-white/10 p-4 space-y-2" data-din-threshold>
    <h3 className="font-bold">{t('Gürültüde sayı anlama sonucu')}</h3>
    <ResultValue value={record.value??null} status={record.value===null||record.value===undefined?'Kararlı eşik bulunamadı':undefined} unit="dB SNR"/>
    <p className="text-sm text-slate-300">{t('Daha düşük değer, gürültü içinde sayıları daha iyi ayırt ettiğinizi gösterir.')}</p>
    {comparable&&<p data-din-comparison className="text-sm text-slate-300">{t('Önceki test: ')}{number(previous!.value as number)}{t(' dB SNR · fark ')}{number((record.value as number)-(previous!.value as number))}{t(' dB')}</p>}
   </section>
   <div className="grid grid-cols-3 gap-2" data-din-scorecards>
    {cards.map(([title,value])=><div key={title} className="rounded-2xl border border-white/10 p-3 space-y-1"><h3 className="text-sm font-semibold">{t(title)}</h3><p className="text-2xl font-bold tabular-nums">{value}</p></div>)}
   </div>
  </div>
  <p className={styles.small} data-hearing-limits>{t('Bu görev tarama amaçlıdır; klinik bir işitme eşiği değildir. Cihaz ve kulaklık kalibre edilmemiştir.')}</p>
  {score.rows.length>0&&<details data-din-trials className="rounded-2xl border border-white/10 p-3">
   <summary className="min-h-11 flex items-center cursor-pointer text-sm font-semibold">{t('Deneme ayrıntıları')}</summary>
   <div className="overflow-x-auto"><table className="w-full text-sm tabular-nums">
    <thead><tr className="text-left text-slate-300"><th className="py-1 pr-3 font-medium">#</th><th className="py-1 pr-3 font-medium">{t('Çalan sayılar')}</th><th className="py-1 pr-3 font-medium">{t('Yanıtınız')}</th><th className="py-1 pr-3 font-medium">{t('dB SNR')}</th><th className="py-1 font-medium">{t('Sonuç')}</th></tr></thead>
    <tbody>{score.rows.map((row,i)=><tr key={i} data-din-trial={i+1} className="border-t border-white/5"><td className="py-1 pr-3">{i+1}</td><td className="py-1 pr-3">{row.digits!.join(' ')}</td><td className="py-1 pr-3">{row.answer!.join(' ')}</td><td className="py-1 pr-3">{finite(row.snr)?number(row.snr):'—'}</td><td className="py-1">{node(row.correct?'Doğru':'Yanlış')}</td></tr>)}</tbody>
   </table></div>
  </details>}
 </div>;
}
