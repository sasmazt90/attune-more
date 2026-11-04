'use client';
import type {HealthRecord} from '../../utils/healthRecords';
import {HearingDinResult} from './HearingDinResult';
import {HearingToneResults} from './HearingToneResults';
/** Same selected-record interpretation in the overview popup and record table. */
export function HearingStoredResult({record,previous}:{record:HealthRecord;previous?:HealthRecord}){
 if(record.thresholds)return <HearingToneResults record={record} previous={previous}/>;
 return <HearingDinResult record={record} previous={previous}/>;
}
