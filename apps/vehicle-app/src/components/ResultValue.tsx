import React from 'react';
/** Status never inherits the numeric score's large type. */
export function ResultValue({value,status,unit,format,color}:{value:number|null;status?:string;unit?:string;format?:'percent';color?:string}){
 return value===null||!Number.isFinite(value)||status?<span data-result-status className="block text-sm md:text-base leading-relaxed font-normal break-words min-w-0">{status||'Değerlendirilemiyor'}</span>:<div className="flex flex-wrap items-baseline gap-2 min-w-0"><span data-skin-score className="text-3xl font-semibold tabular-nums" style={color?{color}:undefined}>{Math.round(value)}{format==='percent'?'%':''}</span>{unit&&<span className="text-xs text-slate-400 break-words">{unit}</span>}</div>;
}
