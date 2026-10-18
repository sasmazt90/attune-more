import type {SkinSnapshot} from './skinSnapshot';
import type {SkinAngle} from './skinMultiAngle';

export const SKIN_PHOTO_PERMISSION='attune_privacy_skin_photos_allowed';
export const SKIN_PHOTO_LIMITS={recordBytes:32*1024*1024,totalBytes:128*1024*1024};
type Frames=Partial<Record<SkinAngle,SkinSnapshot>>;
type Stored={id:string;payload:string;sha256:string;bytes:number;version:1};
const DATABASE='attune-skin-photos',STORE='records';
function open():Promise<IDBDatabase>{
 return new Promise((resolve,reject)=>{
  const request=indexedDB.open(DATABASE,1);
  request.onupgradeneeded=()=>request.result.createObjectStore(STORE,{keyPath:'id'});
  request.onerror=()=>reject(request.error);request.onblocked=()=>reject(Error('PHOTO_STORE_BLOCKED'));
  request.onsuccess=()=>{request.result.onversionchange=()=>request.result.close();resolve(request.result);};
 });
}
async function transaction<T>(mode:IDBTransactionMode,action:(store:IDBObjectStore,set:(value:T)=>void)=>void):Promise<T>{
 const db=await open();
 return new Promise((resolve,reject)=>{
  const tx=db.transaction(STORE,mode);let value:T;
  tx.oncomplete=()=>{db.close();resolve(value);};tx.onabort=tx.onerror=()=>{db.close();reject(tx.error||Error('PHOTO_STORE_FAILED'));};
  try{action(tx.objectStore(STORE),v=>{value=v;});}catch(error){tx.abort();db.close();reject(error);}
 });
}
const permitted=()=>localStorage.getItem(SKIN_PHOTO_PERMISSION)==='true';
function recordExists(id:string){return JSON.parse(localStorage.getItem('togg_health_skin_history')||'[]').some((r:{id:string})=>r.id===id);}
const hash=async(value:string)=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(value)))).map(v=>v.toString(16).padStart(2,'0')).join('');
function validate(frames:Frames){
 const entries=Object.entries(frames);
 if(!entries.length||entries.length>3)throw Error('INVALID_PHOTO_RECORD');
 for(const [angle,s] of entries){
  if(!['FRONT','RIGHT','LEFT'].includes(angle)||s.angle!==angle||!s.photoId||!/^[a-f0-9]{64}$/.test(s.photoId)||!s.dataUrl.startsWith('data:image/png;base64,')||s.width<16||s.height<16||s.width*s.height>8400000)throw Error('INVALID_PHOTO_SOURCE');
  if(s.general&&(angle!=='FRONT'||s.general.captureId!==s.photoId||s.general.pose!=='FRONT'||s.general.sourceTransform.sourceWidth!==s.width||s.general.sourceTransform.sourceHeight!==s.height))throw Error('INVALID_OVERVIEW_SOURCE');
  for(const map of Object.values(s.localMaps||{}))if(map.photoId!==s.photoId||map.pose!==angle||map.sourceWidth!==s.width||map.sourceHeight!==s.height)throw Error('INVALID_PHOTO_MAP');
 }
}
/** Caller holds the health-records lock. Numeric history contains no pixels. */
export async function saveSkinPhotos(id:string,frames:Frames,isCurrent:()=>boolean=()=>true):Promise<boolean>{
 if(!isCurrent()||!permitted()||!recordExists(id))return false;
 validate(frames);const payload=JSON.stringify(frames,(_key,value)=>value instanceof Float32Array?{typed:'Float32Array',items:Array.from(value)}:value instanceof Uint8Array?{typed:'Uint8Array',items:Array.from(value)}:value),bytes=new TextEncoder().encode(payload).byteLength;
 if(bytes>SKIN_PHOTO_LIMITS.recordBytes)throw Error('PHOTO_RECORD_TOO_LARGE');
 const row:Stored={id,payload,bytes,sha256:await hash(payload),version:1};
 if(!isCurrent()||!permitted()||!recordExists(id))return false;
 return transaction<boolean>('readwrite',(store,set)=>{
  const request=store.getAll();request.onsuccess=()=>{try{
   const existing=request.result as Stored[];
   const ids=new Set(JSON.parse(localStorage.getItem('togg_health_skin_history')||'[]').map((r:{id:string})=>r.id));
   if(!isCurrent()||!permitted()||!ids.has(id)){set(false);return;}
   const total=existing.filter(r=>ids.has(r.id)&&r.id!==id).reduce((n,r)=>n+r.bytes,bytes);
   if(total>SKIN_PHOTO_LIMITS.totalBytes){store.transaction.abort();return;}
   for(const r of existing)if(!ids.has(r.id))store.delete(r.id);
   store.put(row);
   set(true);
  }catch{store.transaction.abort();}};
 });
}
export async function loadSkinPhotos(id:string):Promise<Frames|undefined>{
 if(!permitted()||!recordExists(id))return;
 const row=await transaction<Stored|undefined>('readonly',(store,set)=>{const r=store.get(id);r.onsuccess=()=>set(r.result);});
 if(!row||!permitted()||!recordExists(id))return;
 if(row.id!==id||row.version!==1||row.bytes>SKIN_PHOTO_LIMITS.recordBytes||new TextEncoder().encode(row.payload).byteLength!==row.bytes||await hash(row.payload)!==row.sha256){await deleteSkinPhotos(id);throw Error('INVALID_PHOTO_RECORD');}
 let frames:Frames;try{frames=JSON.parse(row.payload,(_key,value)=>value?.typed==='Float32Array'?new Float32Array(value.items):value?.typed==='Uint8Array'?new Uint8Array(value.items):value);validate(frames);}catch{await deleteSkinPhotos(id);throw Error('INVALID_PHOTO_RECORD');}
 if(permitted()&&recordExists(id))return frames;
}
export async function deleteSkinPhotos(id:string){await transaction<void>('readwrite',store=>{store.delete(id);});}
export const SKIN_PHOTO_DELETE_PENDING='attune_skin_photo_delete_v1';
const deletionBackup=(id:string)=>'delete-backup:'+id;
/** A durable photo undo row bridges IndexedDB and the numeric undo journal.
 * The caller holds the health-records lock; neither journal contains raw media.
 */
export async function deleteSkinPhotosWithRecords(id:string,apply:()=>void,rollback:()=>void,finalize:()=>void){
 const marker={id,phase:'prepared'};
 localStorage.setItem(SKIN_PHOTO_DELETE_PENDING,JSON.stringify(marker));
 try{
  await transaction<void>('readwrite',store=>{
   const request=store.get(id);
   request.onsuccess=()=>{try{
    if(request.result)store.put({...request.result,id:deletionBackup(id),deleteRecoveryFor:id});
    apply();store.delete(id);
   }catch{store.transaction.abort();}};
  });
  // Only a completed IDB transaction may change the intent to committed.
  localStorage.setItem(SKIN_PHOTO_DELETE_PENDING,JSON.stringify({...marker,phase:'committed'}));
  finalize();
  await transaction<void>('readwrite',store=>{store.delete(deletionBackup(id));});
  localStorage.removeItem(SKIN_PHOTO_DELETE_PENDING);
 }catch(error){
  const pending=JSON.parse(localStorage.getItem(SKIN_PHOTO_DELETE_PENDING)||'null');
  if(pending?.phase!=='committed'){
   await recoverSkinPhotoDeletion(rollback,finalize);
  }
  throw error;
 }
}
export async function recoverSkinPhotoDeletion(rollback:()=>void,finalize:()=>void){
 const raw=localStorage.getItem(SKIN_PHOTO_DELETE_PENDING);if(!raw)return;
 const marker=JSON.parse(raw);
 if(!marker||typeof marker.id!=='string'||!marker.id||!['prepared','committed'].includes(marker.phase))throw Error('INVALID_PHOTO_DELETE_JOURNAL');
 await transaction<void>('readwrite',store=>{
  const request=store.get(deletionBackup(marker.id));
  request.onsuccess=()=>{try{
   if(marker.phase==='prepared'&&request.result){const {deleteRecoveryFor,...row}=request.result;if(deleteRecoveryFor!==marker.id)throw Error('INVALID_PHOTO_DELETE_BACKUP');store.put({...row,id:marker.id});}
   if(marker.phase==='committed')store.delete(marker.id);
   store.delete(deletionBackup(marker.id));
  }catch{store.transaction.abort();}};
 });
 if(marker.phase==='prepared')rollback();else finalize();
 localStorage.removeItem(SKIN_PHOTO_DELETE_PENDING);
}
export async function clearSkinPhotos(){await transaction<void>('readwrite',store=>{store.clear();});}
