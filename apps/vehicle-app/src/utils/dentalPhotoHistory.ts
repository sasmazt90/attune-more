import type {DentalCapture} from './dentalCapture';

export const DENTAL_PHOTO_PERMISSION='attune_privacy_dental_photos_allowed';
export const DENTAL_PHOTO_LIMITS={recordBytes:32*1024*1024,totalBytes:128*1024*1024};
export type DentalFrames=DentalCapture[];
type Frames=DentalFrames;
type Stored={id:string;payload:string;sha256:string;bytes:number;version:1};
const DATABASE='attune-dental-photos',STORE='records';
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
const permitted=()=>localStorage.getItem(DENTAL_PHOTO_PERMISSION)==='true';
function recordExists(id:string){return JSON.parse(localStorage.getItem('attune_dental_history_v1')||'[]').some((r:{id:string})=>r.id===id);}
const hash=async(value:string)=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(value)))).map(v=>v.toString(16).padStart(2,'0')).join('');
function validate(frames:Frames){
 if(!Array.isArray(frames)||frames.length<1||frames.length>4)throw Error('INVALID_PHOTO_RECORD');
 if(new Set(frames.map(f=>f.pose)).size!==frames.length||new Set(frames.map(f=>f.photoId)).size!==frames.length)throw Error('INVALID_PHOTO_SOURCE');
 for(const f of frames)if(!['FRONT','RIGHT','LEFT','BITE'].includes(f.pose)||!/^[a-f0-9]{64}$/.test(f.photoId)||!f.photo.startsWith('data:image/png;base64,')||!Number.isInteger(f.width)||!Number.isInteger(f.height)||f.width<16||f.height<16||f.width*f.height>24000000||Math.max(f.width,f.height)>8192)throw Error('INVALID_PHOTO_SOURCE');
}
function associated(id:string,frames:Frames){
 const record=JSON.parse(localStorage.getItem('attune_dental_history_v1')||'[]').find((r:{id:string})=>r.id===id);
 return record&&record.measurements?.length===frames.length&&frames.every((f,i)=>{const v=record.measurements[i];return v.photoId===f.photoId&&v.pose===f.pose&&v.sourceWidth===f.width&&v.sourceHeight===f.height;});
}
export async function verifyDentalPhotoPixels(frames:Frames){
 validate(frames);
 // Decode local PNG bytes directly. Fetching a data URL would incorrectly
 // require expanding connect-src in the production Content Security Policy.
 for(const f of frames){const blob=new Blob([Uint8Array.from(atob(f.photo.slice('data:image/png;base64,'.length)),c=>c.charCodeAt(0))],{type:'image/png'}),bitmap=await createImageBitmap(blob);try{if(bitmap.width!==f.width||bitmap.height!==f.height)throw Error('INVALID_PHOTO_DIMENSIONS');const canvas=document.createElement('canvas');canvas.width=f.width;canvas.height=f.height;const ctx=canvas.getContext('2d')!;ctx.drawImage(bitmap,0,0);const bytes=ctx.getImageData(0,0,f.width,f.height).data,digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))).map(v=>v.toString(16).padStart(2,'0')).join('');if(digest!==f.photoId)throw Error('INVALID_PHOTO_PIXELS');}finally{bitmap.close();}}
}
/** Caller holds the health-records lock. Numeric history contains no pixels. */
export async function saveDentalPhotos(id:string,frames:Frames,isCurrent:()=>boolean=()=>true):Promise<boolean>{
 if(!isCurrent()||!permitted()||!recordExists(id))return false;
 validate(frames);if(!associated(id,frames))throw Error('INVALID_PHOTO_ASSOCIATION');await verifyDentalPhotoPixels(frames);const payload=JSON.stringify(frames,(_key,value)=>value instanceof Float32Array?{typed:'Float32Array',items:Array.from(value)}:value instanceof Uint8Array?{typed:'Uint8Array',items:Array.from(value)}:value),bytes=new TextEncoder().encode(payload).byteLength;
 if(bytes>DENTAL_PHOTO_LIMITS.recordBytes)throw Error('PHOTO_RECORD_TOO_LARGE');
 const row:Stored={id,payload,bytes,sha256:await hash(payload),version:1};
 if(!isCurrent()||!permitted()||!recordExists(id))return false;
 return transaction<boolean>('readwrite',(store,set)=>{
  const request=store.getAll();request.onsuccess=()=>{try{
   const existing=request.result as Stored[];
   const ids=new Set(JSON.parse(localStorage.getItem('attune_dental_history_v1')||'[]').map((r:{id:string})=>r.id));
   if(!isCurrent()||!permitted()||!ids.has(id)||!associated(id,frames)){set(false);return;}
   const total=existing.filter(r=>ids.has(r.id)&&r.id!==id).reduce((n,r)=>n+r.bytes,bytes);
   if(total>DENTAL_PHOTO_LIMITS.totalBytes){store.transaction.abort();return;}
   for(const r of existing)if(!ids.has(r.id))store.delete(r.id);
   store.put(row);
   set(true);
  }catch{store.transaction.abort();}};
 });
}
export async function loadDentalPhotos(id:string):Promise<Frames|undefined>{
 if(!permitted()||!recordExists(id))return;
 const row=await transaction<Stored|undefined>('readonly',(store,set)=>{const r=store.get(id);r.onsuccess=()=>set(r.result);});
 if(!row||!permitted()||!recordExists(id))return;
 if(row.id!==id||row.version!==1||row.bytes>DENTAL_PHOTO_LIMITS.recordBytes||new TextEncoder().encode(row.payload).byteLength!==row.bytes||await hash(row.payload)!==row.sha256){await deleteDentalPhotos(id);throw Error('INVALID_PHOTO_RECORD');}
 let frames:Frames;try{frames=JSON.parse(row.payload,(_key,value)=>value?.typed==='Float32Array'?new Float32Array(value.items):value?.typed==='Uint8Array'?new Uint8Array(value.items):value);validate(frames);}catch{await deleteDentalPhotos(id);throw Error('INVALID_PHOTO_RECORD');}
 if(!associated(id,frames))throw Error('INVALID_PHOTO_ASSOCIATION');await verifyDentalPhotoPixels(frames);if(permitted()&&recordExists(id))return frames;
}
export async function deleteDentalPhotos(id:string){await transaction<void>('readwrite',store=>{store.delete(id);});}
export const DENTAL_PHOTO_DELETE_PENDING='attune_dental_photo_delete_v1';
const deletionBackup=(id:string)=>'delete-backup:'+id;
/** A durable photo undo row bridges IndexedDB and the numeric undo journal.
 * The caller holds the health-records lock; neither journal contains raw media.
 */
export async function deleteDentalPhotosWithRecords(id:string,apply:()=>void,rollback:()=>void,finalize:()=>void){
 const marker={id,phase:'prepared'};
 localStorage.setItem(DENTAL_PHOTO_DELETE_PENDING,JSON.stringify(marker));
 try{
  await transaction<void>('readwrite',store=>{
   const request=store.get(id);
   request.onsuccess=()=>{try{
    if(request.result)store.put({...request.result,id:deletionBackup(id),deleteRecoveryFor:id});
    apply();store.delete(id);
   }catch{store.transaction.abort();}};
  });
  // Only a completed IDB transaction may change the intent to committed.
  localStorage.setItem(DENTAL_PHOTO_DELETE_PENDING,JSON.stringify({...marker,phase:'committed'}));
  finalize();
  await transaction<void>('readwrite',store=>{store.delete(deletionBackup(id));});
  localStorage.removeItem(DENTAL_PHOTO_DELETE_PENDING);
 }catch(error){
  const pending=JSON.parse(localStorage.getItem(DENTAL_PHOTO_DELETE_PENDING)||'null');
  if(pending?.phase!=='committed'){
   await recoverDentalPhotoDeletion(rollback,finalize);
  }
  throw error;
 }
}
export async function recoverDentalPhotoDeletion(rollback:()=>void,finalize:()=>void){
 const raw=localStorage.getItem(DENTAL_PHOTO_DELETE_PENDING);if(!raw)return;
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
 localStorage.removeItem(DENTAL_PHOTO_DELETE_PENDING);
}
export async function clearDentalPhotos(){await transaction<void>('readwrite',store=>{store.clear();});}
