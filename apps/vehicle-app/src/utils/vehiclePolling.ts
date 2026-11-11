/**
 * Vehicle-state polling interval of the web app. While an app audio stream owns output ('attune-stream-focus', e.g. the
 * Mental closing), the state is read four times as often, so the park/driving guard stops that audio sooner. The
 * native AAOS gate and its own polling are unchanged; this only shortens the web side's detection time.
 */
export const VEHICLE_POLL_MS=1000;
export const VEHICLE_POLL_DURING_AUDIO_MS=250;
export function vehiclePollInterval(activeStreams:number){return activeStreams>0?VEHICLE_POLL_DURING_AUDIO_MS:VEHICLE_POLL_MS;}
/** Tracks stream-focus owners; reports when the first owner appears (to read the state at once). */
export function streamFocusTracker(onFirstOwner:()=>void){
 const owners=new Set<object>();
 const listener=(event:Event)=>{const e=event as Event&{owner?:object;active?:boolean};if(!e.owner)return;const before=owners.size;if(e.active)owners.add(e.owner);else owners.delete(e.owner);if(!before&&owners.size)onFirstOwner();};
 return {owners,listener};
}
