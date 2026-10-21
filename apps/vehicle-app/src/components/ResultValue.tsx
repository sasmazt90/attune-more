'use client';

import {useTranslations} from '../i18n/LanguageProvider';
import React from 'react';
/** Status never inherits the numeric score's large type. */
export function ResultValue({value,status,unit,format,color}:{value:number|null;status?:string;unit?:string;format?:'percent';color?:string}){
 const {text:i18nText,node:i18nNode}=useTranslations();
 return value===null||!Number.isFinite(value)||status?<span data-result-status className="block text-sm md:text-base leading-relaxed font-normal break-words min-w-0">{i18nNode(status||'Değerlendirilemiyor')}</span>:<div className="flex flex-wrap items-baseline gap-2 min-w-0"><span data-skin-score className="text-3xl font-semibold tabular-nums" style={color?{color}:undefined}>{i18nNode(Math.round(value))}{i18nNode(format==='percent'?'%':'')}</span>{unit&&<span className="text-xs text-slate-400 break-words">{i18nNode(unit)}</span>}</div>;
}
