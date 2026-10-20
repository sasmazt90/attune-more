/** Settings locks only; never supplies or overrides vehicle/capture readiness. */
const owners=new Set<string>(),listeners=new Set<()=>void>();
export const languageSwitchLocked=()=>owners.size>0;
export function setLanguageSwitchLock(owner:string,active:boolean){
 const before=languageSwitchLocked();if(active)owners.add(owner);else owners.delete(owner);
 if(before!==languageSwitchLocked())for(const listener of listeners)listener();
}
export function subscribeLanguageLock(listener:()=>void){listeners.add(listener);return()=>{listeners.delete(listener);};}
