'use client';
import {useMemo,type MouseEvent} from 'react';
import {Check,CircleCheck,Ear,Hand,Headphones,RotateCcw,ChartNoAxesColumn} from 'lucide-react';
import {useTranslations} from '../../i18n/LanguageProvider';
import {tonePCM,HEARING_CONFIG,type Ear as EarSide} from '../../utils/hearingProtocol';
import type {ValidResponse} from '../../utils/hearingResults';
import styles from './hearing.module.css';
export type PreviousToneResponse=ValidResponse&{presentationNumber:number};
export type PlannedTone={ear:EarSide;round:number;presentationNumber:number;frequency:number;level:number};
export function HearingJourney({phase,ear}:{phase:'prepare'|'tone'|'result';ear:EarSide}){
 const {text:t}=useTranslations(),active=phase==='prepare'?0:phase==='result'?3:ear==='left'?1:2;
 return <nav className={styles.journey} aria-label={t('Ölçüm aşamaları')}>{['Hazırlık','Sol kulak','Sağ kulak','Sonuç'].map((label,i)=><span key={label} aria-current={i===active?'step':undefined}>{i===0?<Headphones aria-hidden="true"/>:i===3?<ChartNoAxesColumn aria-hidden="true"/>:<Ear aria-hidden="true" className={i===1?styles.mirror:''}/>}<span>{t(label)}</span></span>)}</nav>;
}
function LevelMeter({level,previous=false}:{level:number;previous?:boolean}){
 const {text:t}=useTranslations(),lit=Math.round((level+90)/60*12);
 return <div className={styles.meter} role="meter" aria-label={t(previous?'Önceki denemenin dijital ses seviyesi':'Dinletilecek sesin dijital seviyesi')} aria-valuemin={-90} aria-valuemax={-30} aria-valuenow={level} aria-valuetext={`${level} dBFS`}>{Array.from({length:12},(_,i)=><span key={i} className={i<lit?styles.lit:''} style={{height:`${7+i*1.6}px`}}/>)}</div>;
}
function PreviousWave({response}:{response:PreviousToneResponse}){
 const {text:t,locale}=useTranslations(),p=response.presentation,max=(p.duration||0)+HEARING_CONFIG.responseSeconds,x=40+response.seconds/max*320;
 const wave=useMemo(()=>{
  const data=tonePCM(p.frequency,p.level,p.duration!,48000),points=[];
  const magnitude=Math.max(...Array.from({length:100},(_,i)=>Math.abs(data[Math.floor(i*(data.length-1)/99)]))),durationWidth=p.duration!/max*320;
  for(let i=0;i<100;i++){
   const start=Math.floor(i*data.length/100),end=Math.floor((i+1)*data.length/100);let peak=0;
   for(let j=start;j<end;j++)peak=Math.max(peak,Math.abs(data[j]));
   points.push(`${i?'L':'M'}${40+i/99*durationWidth} ${65-(i%2?-1:1)*peak/Math.max(magnitude,1e-12)*17}`);
  }
  return points.join(' ');
 },[p.frequency,p.level,p.duration,max]);
 return <div className={styles.previousWave}><svg viewBox="0 0 400 95" role="img" aria-label={t('Önceki ses sunumunun zarfı ve basış zamanı')} data-hearing-previous-trial={response.trialId}><line x1="40" x2="360" y1="65" y2="65" stroke="#233246"/><path d={wave} stroke="#a6b4c7" strokeWidth="1.4" fill="none"/><line x1={x} x2={x} y1="35" y2="69" stroke="#00d2eb"/><circle cx={x} cy="32" r="5" fill="#00d2eb"/></svg><div className={styles.waveTime}><span style={{left:`${x/400*100}%`}}>{new Intl.NumberFormat(locale,{minimumFractionDigits:2,maximumFractionDigits:2}).format(response.seconds)} {t('sn')}</span></div></div>;
}
export function HearingTestPanels({planned,previous,onPointerDown,onPress,onStop}:{planned:PlannedTone;previous?:PreviousToneResponse;onPointerDown:()=>void;onPress:(e:MouseEvent<HTMLButtonElement>)=>void;onStop:()=>void}){
 const {text:t,locale}=useTranslations(),accepted=previous?.ear===planned.ear?previous:undefined;
 const title=(planned.round-1)%7===6?'Tutarlılık Kontrolü':planned.frequency>=4000?'İnce Sesler':planned.frequency<=500?'Kalın Sesler':'Orta Sesler';
 const hz=(n:number)=>new Intl.NumberFormat(locale).format(n)+' Hz';
 return <div className={styles.test} data-tone-progress><HearingJourney phase="tone" ear={planned.ear}/><div className={styles.panels}><section className={styles.panel} data-hearing-previous-panel><div className={styles.panelHead}>{t('Frekans Analizi')}</div><div className={styles.activeEar}><h3><Ear aria-hidden="true" className={planned.ear==='left'?styles.mirror:''}/>{t(planned.ear==='left'?'Sol kulak':'Sağ kulak')}</h3><span>{t('Devam ediyor')}</span></div><div className={styles.previousResponse}>{accepted?<><div className={styles.completedLabel}><CircleCheck aria-hidden="true"/><span>{accepted.presentationNumber}. {t('deneme tamamlandı')}</span></div><div className={styles.divider}/><p>{t('Bastığın an')}</p><div className={styles.previousLevel}><span>{hz(accepted.frequency)}</span><div><LevelMeter previous level={accepted.level}/></div></div><PreviousWave response={accepted}/></>:<p className={styles.empty}>{t('Henüz bir yanıt yok.')}</p>}</div><label className={styles.stop}><input type="checkbox" checked={false} aria-label={t('Testi durdur')} onChange={e=>{if(e.target.checked)onStop();}}/>{t('Durdur')}</label></section><section className={styles.panel} data-hearing-current-panel><h2>{t(title)}</h2><p>{t((planned.round-1)%7===6?'Önceki ölçümle bu ölçüm arasındaki fark kontrol edilir.':'Sonuç, aynı ses seviyesinde verdiğin yanıtların tutarlılığıyla belirlenir.')}</p><div className={styles.currentBox}><div className={styles.roundHead}><span>{t('Tur')}</span><strong>{planned.round} / 14</strong></div><div className={styles.segments} role="meter" aria-label={t('Güncel frekans turu')} aria-valuemin={1} aria-valuemax={14} aria-valuenow={planned.round}>{Array.from({length:14},(_,i)=><span key={i} className={i<planned.round-1?styles.complete:i===planned.round-1?styles.active:''} aria-label={`${i+1}. ${t(i<planned.round-1?'Tamamlandı':i===planned.round-1?'Aktif':i===13?'Kalibrasyon':'Sırada')}`}>{i<planned.round-1?<Check aria-hidden="true"/>:i===13?<RotateCcw aria-hidden="true"/>:null}</span>)}</div><div className={styles.divider}/><span data-hearing-presentation-count={planned.presentationNumber}>{planned.presentationNumber}. {t('deneme')}</span><div className={styles.currentLevel}><span className={styles.currentHz}>{hz(planned.frequency)}</span><span className={styles.verticalDivider} aria-hidden="true"/><div><p>{t('Ses seviyesi')}</p><LevelMeter level={planned.level}/></div></div><button type="button" className={styles.heard} onPointerDown={onPointerDown} onClick={onPress}><Hand aria-hidden="true"/>{t('Duydum')}</button></div><div className={styles.currentLegend}><span><Check aria-hidden="true"/>{t('Tamamlandı')}</span><span><b/>{t('Aktif')}</span><span><RotateCcw aria-hidden="true"/>{t('Kalibrasyon')}</span></div></section></div></div>;
}
