'use client';
import {Eye,Scan,ChartNoAxesColumn} from 'lucide-react';
import {useTranslations} from '../../i18n/LanguageProvider';
import type {Eye as EyeSide} from '../../utils/spokenVision';
export function VisionJourney({phase,eye,completed}:{phase:'prepare'|'test'|'result';eye:EyeSide;completed:number}){
 const {text:t}=useTranslations(),step=phase==='prepare'?0:phase==='result'?3:eye==='RIGHT'?1:2;
 return <div className="space-y-3"><nav aria-label={t('Ölçüm aşamaları')} className="flex flex-wrap justify-between gap-3 rounded-2xl bg-slate-950/60 p-4 text-sm">{['Hazırlık','Sağ göz','Sol göz','Sonuç'].map((label,i)=>{const Icon=i===0?Scan:i===3?ChartNoAxesColumn:Eye;return <span key={label} aria-current={i===step?'step':undefined} className={`flex items-center gap-2 ${i===step?'text-togg-turquoise':'text-slate-400'}`}><Icon aria-hidden="true" size={18}/>{t(label)}</span>;})}</nav><div className="flex items-center gap-3 text-sm text-slate-300"><div role="progressbar" aria-label={t('Tamamlanan yanıtlar')} aria-valuemin={0} aria-valuemax={24} aria-valuenow={completed} className="h-2 w-full overflow-hidden rounded-full bg-slate-800"><span className="block h-full bg-togg-turquoise" style={{width:`${completed/24*100}%`}}/></div><span className="whitespace-nowrap">{completed} / 24</span></div></div>;
}
