import {getLanguage} from '../i18n/core';
/** Optional isolated loopback port. Ordinary installations retain each caller's origin. */
export function localBackend(path:string,ordinaryOrigin='http://localhost:8000') {
 const port=process.env.NEXT_PUBLIC_ATTUNE_LOCAL_API_PORT;
 const origin=port&&/^\d{1,5}$/.test(port)&&Number(port)>0&&Number(port)<65536?`http://127.0.0.1:${port}`:ordinaryOrigin;
 return origin+path;
}
/** Locale is request-scoped; never add headers, broaden origins or alter request bodies. */
export function apiFetch(input:RequestInfo|URL,init?:RequestInit):Promise<Response>{
 if(typeof input==='string'){
  try{
   const url=new URL(input,typeof location==='undefined'?'http://localhost:3000':location.origin);
   if(['/api/'].some(prefix=>url.pathname.startsWith(prefix))&&['localhost','127.0.0.1'].includes(url.hostname)&&getLanguage()!=='tr'){
    url.searchParams.set('language',getLanguage());input=url.toString();
   }
  }catch{} // Native fetch retains responsibility for malformed inputs.
 }
 return globalThis.fetch(input,init);
}
