'use client';
import {useEffect,useId,useSyncExternalStore} from 'react';
import {languageSwitchLocked,setLanguageSwitchLock,subscribeLanguageLock} from './locks';
export function useLocaleSwitchLock(owner:string,active:boolean){
 const id=useId(),key=owner+id;
 useEffect(()=>{setLanguageSwitchLock(key,active);return()=>setLanguageSwitchLock(key,false);},[key,active]);
}
export const useLanguageSwitchLocked=()=>useSyncExternalStore(subscribeLanguageLock,languageSwitchLocked,()=>false);
