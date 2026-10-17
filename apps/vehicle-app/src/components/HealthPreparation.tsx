import type {ReactNode} from 'react';
import {HealthStartCard} from './HealthStartCard';
export function HealthPreparation({module,actions}:{module:'dental'|'hearing';actions?:ReactNode}){
 return <HealthStartCard module={module} actions={actions}/>;
}
