/** Completed alternating pairs only. Keep a bounded recent window without
 * silently discarding the old prefix: caller commits this offset only after
 * a successful, cited memory update. Character limits cover long ASR turns. */
export function contextWindowThrough(messages:{text:string}[],previousThrough:number):number {
 const pending=messages.slice(previousThrough);
 if(pending.length<=32&&pending.reduce((n,m)=>n+m.text.length,0)<=80000)return previousThrough;
 let keep=Math.min(16,pending.length);
 while(keep>2&&pending.slice(-keep).reduce((n,m)=>n+m.text.length,0)>48000)keep-=2;
 return Math.max(previousThrough,messages.length-keep);
}
