'use client';
import {Check,ChartNoAxesColumn,Minus,Smile,ScanFace} from 'lucide-react';
import {useTranslations} from '../../i18n/LanguageProvider';
import styles from './dental.module.css';
const STEPS=[['Ön',ScanFace],['Sağ',ScanFace],['Sol',ScanFace],['Kapanış',Smile],['Sonuç',ChartNoAxesColumn]] as const;
/** Capture progress in the approved hearing "journey" style; skipped poses stay visible. */
const POSES=['FRONT','RIGHT','LEFT','BITE'];
export function DentalJourney({active,skipped=[]}:{active:number;skipped?:readonly string[]}){
 const {text:t}=useTranslations();
 return <nav className={styles.journey} aria-label={t('Tarama aşamaları')} data-dental-step={active}>{STEPS.map(([label,Icon],i)=>{const skip=i<4&&skipped.includes(POSES[i]),done=i<active&&!skip;return <span key={label} aria-current={i===active?'step':undefined} className={skip?styles.skipped:done?styles.done:''}>{skip?<Minus aria-hidden="true"/>:done?<Check aria-hidden="true"/>:<Icon aria-hidden="true"/>}<span>{t(label)}</span></span>;})}</nav>;
}
