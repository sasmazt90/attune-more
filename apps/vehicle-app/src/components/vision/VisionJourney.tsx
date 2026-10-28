'use client';
import {Eye,Scan,ChartNoAxesColumn} from 'lucide-react';
import {useTranslations} from '../../i18n/LanguageProvider';
import type {Eye as EyeSide} from '../../utils/spokenVision';
export function VisionJourney({phase,eye,completed}:{phase:'prepare'|'test'|'result';eye:EyeSide;completed:number}){
 const {text:t}=useTranslations(),step=phase==='prepare'?0:phase==='result'?3:eye==='RIGHT'?1:2;
 return <div className="space-y-3"><nav aria-label={t('Ölçüm aşamaları')} className="flex flex-wrap justify-between gap-3 rounded-2xl bg-slate-950/60 p-4 text-sm">{['Hazırlık','Sağ göz','Sol göz','Sonuç'].map((label,i)=>{const Icon=i===0?Scan:i===3?ChartNoAxesColumn:Eye;return <span key={label} aria-current={i===step?'step':undefined} className={`flex items-center gap-2 ${i===step?'text-togg-turquoise':'text-slate-400'}`}><Icon aria-hidden="true" size={18}/>{t(label)}</span>;})}</nav><div className="flex items-center gap-3 text-sm text-slate-300"><progress aria-label={t('Tamamlanan yanıtlar')} max={24} value={completed} className="h-2 w-full accent-togg-turquoise"/><span className="whitespace-nowrap">{completed} / 24</span></div></div>;
}
