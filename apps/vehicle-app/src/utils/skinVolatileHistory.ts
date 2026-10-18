import type {SkinSnapshot} from './skinSnapshot';
import type {SkinAngle} from './skinMultiAngle';
type Frames=Partial<Record<SkinAngle,SkinSnapshot>>;
const frames=new Map<string,Frames>(),listeners=new Set<()=>void>();
let installed=false,version=0;
const notify=()=>{version++;listeners.forEach(listener=>listener());};
function prune(){
 try{
  const permitted=localStorage.getItem('attune_privacy_skin_save_allowed')==='true';
  const records=JSON.parse(localStorage.getItem('togg_health_skin_history')||'[]');
  const ids=new Set(Array.isArray(records)?records.map(record=>record.id):[]);
  let changed=false;
  for(const id of frames.keys())if(!permitted||!ids.has(id)){frames.delete(id);changed=true;}
  if(changed)notify();
 }catch{if(frames.size){frames.clear();notify();}}
}
/** Same-app-session photos only. Never serializes pixels or changes consent. */
export function rememberSkinSnapshots(id:string,snapshots:Frames){
 if(typeof window==='undefined'||!id)return;
 if(!installed){installed=true;for(const event of ['attune-records','attune-privacy','storage'])window.addEventListener(event,prune);}
 if(localStorage.getItem('attune_privacy_skin_save_allowed')!=='true')return;
 frames.delete(id);frames.set(id,{...snapshots});
 while(frames.size>2)frames.delete(frames.keys().next().value!);
 prune();notify();
}
export const clearSkinSnapshots=()=>{frames.clear();notify();};
export const skinSnapshotVersion=()=>version;
export const subscribeSkinSnapshots=(listener:()=>void)=>{listeners.add(listener);return()=>{listeners.delete(listener);};};
export const readSkinSnapshots=(id:string)=>frames.get(id);
