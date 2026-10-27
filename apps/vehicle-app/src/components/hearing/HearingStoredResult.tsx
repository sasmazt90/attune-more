'use client';
import {useTranslations} from '../../i18n/LanguageProvider';
import type {HealthRecord} from '../../utils/healthRecords';
import {ResultValue} from '../ResultValue';
import {HearingToneResults} from './HearingToneResults';
/** Same selected-record interpretation in the overview popup and record table. */
export function HearingStoredResult({record,previous}:{record:HealthRecord;previous?:HealthRecord}){
 const {text:t,node}=useTranslations();
 if(record.thresholds)return <HearingToneResults record={record} previous={previous}/>;
 return <div data-hearing-result-record={record.id}><p>{node(record.validTrials)}{t(' geçerli üçlü · ')}{node(Number.isFinite(record.digitAccuracy)?Math.round(record.digitAccuracy*100):'—')}{t('% doğru sayı')}</p><ResultValue value={record.value} status={record.value===null?'Kararlı eşik bulunamadı':undefined} unit="dB SNR"/></div>;
}
