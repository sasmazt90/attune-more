'use client';

import {useTranslations} from '../i18n/LanguageProvider';
import type {ReactNode} from 'react';
import {HealthStartCard} from './HealthStartCard';
export function HealthPreparation({module,actions}:{module:'dental'|'hearing';actions?:ReactNode}){
 const {text:i18nText,node:i18nNode}=useTranslations();
 return <HealthStartCard module={module} actions={actions}/>;
}
