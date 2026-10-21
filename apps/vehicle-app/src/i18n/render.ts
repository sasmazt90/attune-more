import {ReactNode} from 'react';
import {t,Language,getLanguage,LOCALES} from './core';
/** Localize generated display values only; React elements and input values retain identity. */
export function localizedNode(value:ReactNode,language?:Language):ReactNode {
 const selected=language||getLanguage();
 if(typeof value==='number'&&Number.isFinite(value))return new Intl.NumberFormat(LOCALES[selected],{useGrouping:false,maximumSignificantDigits:21}).format(value);
 if(typeof value==='string'){
  if(selected!=='en'&&/^-?\d+\.\d+$/.test(value))return value.replace('.',',');
  return t(value,selected);
 }
 if(Array.isArray(value))return value.map(child=>localizedNode(child,language));
 return value;
}
