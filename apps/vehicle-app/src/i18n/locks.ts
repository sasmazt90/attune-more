/** Settings locks only; never supplies or overrides vehicle/capture readiness. */
const owners=new Set<string>(),listeners=new Set<()=>void>();
export const languageSwitchLocked=()=>owners.size>0;
export function setLanguageSwitchLock(owner:string,active:boolean){
 const before=languageSwitchLocked();if(active)owners.add(owner);else owners.delete(owner);
 if(before!==languageSwitchLocked())for(const listener of listeners)listener();
}
export function subscribeLanguageLock(listener:()=>void){listeners.add(listener);return()=>{listeners.delete(listener);};}

/** Module-owned preferences snapshot on first lock, not on the first utterance. */
export function captureWhileLocked<T>(read:()=>T):()=>T {
 let held=languageSwitchLocked(),snapshot=held?read():undefined;
 subscribeLanguageLock(()=>{held=languageSwitchLocked();snapshot=held?read():undefined;});
 return()=>held?snapshot as T:read();
}
