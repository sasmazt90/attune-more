'use client';
import {useTranslations} from '../../i18n/LanguageProvider';

import type {ReactNode} from 'react';
import {HealthStartCard,HEALTH_START_ACTION} from '../HealthStartCard';
import {HEALTH_MODULES} from '../../utils/healthModules';
export function SkinStartView({onStart,information}:{onStart:()=>void;information?:ReactNode}){
 const {text:i18nText,node:i18nNode}=useTranslations();
 return <div className="space-y-6"><div className="flex items-center gap-2"><h1 className="text-2xl font-bold">{i18nNode(HEALTH_MODULES.skin.name)}</h1>{information}</div><HealthStartCard module="skin" actions={<button onClick={onStart} className={HEALTH_START_ACTION}>{i18nText("Analizi Başlat")}</button>}/></div>;
}
