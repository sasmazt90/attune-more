'use client';
import {HealthStartCard,HEALTH_START_ACTION} from '../HealthStartCard';
import {HEALTH_MODULES} from '../../utils/healthModules';
export function SkinStartView({onStart}:{onStart:()=>void}){
 return <div className="space-y-6"><h1 className="text-2xl font-bold">{HEALTH_MODULES.skin.name}</h1><HealthStartCard module="skin" actions={<button onClick={onStart} className={HEALTH_START_ACTION}>Analizi Başlat</button>}/></div>;
}
