/** One turn, one absolute deadline. Only fully playable candidates may resolve the tasks. */
export const HYBRID_DEADLINE_MS=3000;
export type HybridChoice<T>={path:'personal'|'prepared';value:T};
export type HybridClock={now:()=>number;set:(fn:()=>void,ms:number)=>ReturnType<typeof setTimeout>;clear:(id:ReturnType<typeof setTimeout>)=>void};
const clock:HybridClock={now:()=>performance.now(),set:(fn,ms)=>setTimeout(fn,ms),clear:id=>clearTimeout(id)};
export function chooseHybridTurn<T>(options:{receivedAt:number;signal:AbortSignal;current:()=>boolean;
 personal:(signal:AbortSignal)=>Promise<T|null>;prepared:(signal:AbortSignal)=>Promise<T|null>;
 priority?:(value:T)=>boolean;observe?:(stage:string)=>void;clock?:HybridClock}):Promise<HybridChoice<T>|null>{
 const c=options.clock||clock,deadline=options.receivedAt+HYBRID_DEADLINE_MS;
 const personal=new AbortController(),prepared=new AbortController();
 return new Promise((resolve,reject)=>{
  let settled=false,preparedValue:T|null=null,preferPrepared=false;
  const allowed=()=>!options.signal.aborted&&options.current();
  let timer:ReturnType<typeof setTimeout>,guard:ReturnType<typeof setTimeout>;
  const cleanup=()=>{c.clear(timer);c.clear(guard);options.signal.removeEventListener('abort',cancel);};
  const cancel=()=>{if(settled)return;settled=true;cleanup();personal.abort();prepared.abort();resolve(null);};
  const finish=(path:'personal'|'prepared',value:T)=>{
   if(settled)return;if(!allowed()){cancel();return;}
   settled=true;cleanup();(path==='personal'?prepared:personal).abort();
   // Keep the winning arm tied to the session until its playback finishes.
   options.signal.addEventListener('abort',()=>{personal.abort();prepared.abort();},{once:true});
   options.observe?.('hybrid-selected-'+path);resolve({path,value});
  };
  const fallback=()=>{
   if(settled)return;if(!allowed()){cancel();return;}
   preferPrepared=true;personal.abort();
   if(preparedValue!==null){finish('prepared',preparedValue);return;}
   if(c.now()>=deadline){settled=true;cleanup();prepared.abort();reject(Error('HYBRID_PREPARED_NOT_READY'));}
  };
  const watch=()=>{if(!allowed()){cancel();return;}guard=c.set(watch,50);};
  const due=()=>{const remaining=deadline-c.now();if(remaining>0)timer=c.set(due,Math.ceil(remaining));else fallback();};
  timer=c.set(due,Math.max(0,Math.ceil(deadline-c.now())));guard=c.set(watch,50);
  options.signal.addEventListener('abort',cancel,{once:true});
  if(!allowed()){cancel();return;}
  // Launch both without awaiting selection, chat, TTS, or worker cancellation.
  void Promise.resolve().then(()=>options.prepared(prepared.signal)).then(value=>{
   if(settled)return;if(!allowed()){cancel();return;}preparedValue=value;
   if(value!==null&&(options.priority?.(value)||preferPrepared||c.now()>=deadline))finish('prepared',value);
  },()=>{});
  void Promise.resolve().then(()=>options.personal(personal.signal)).then(value=>{
   if(settled)return;if(!allowed()){cancel();return;}
   if(value!==null&&!preferPrepared&&c.now()<deadline)finish('personal',value);else fallback();
  },fallback);
 });
}
