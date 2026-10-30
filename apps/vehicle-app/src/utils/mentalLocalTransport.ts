import {request} from 'node:http';
import {Readable} from 'node:stream';

/** Server-only local transport. The caller's existing deadline owns the entire
 * request, including header wait; Node fetch adds an earlier 300-second cap. */
export function mentalLocalTransport(url:URL,init:{headers:Record<string,string>;body:string;signal:AbortSignal}):Promise<Response>{
 if(url.protocol!=='http:'||!['127.0.0.1','localhost','[::1]'].includes(url.hostname)||url.username||url.password)throw Error('LOOPBACK_REQUIRED');
 return new Promise((resolve,reject)=>{
  const req=request(url,{method:'POST',headers:init.headers,signal:init.signal,agent:false},incoming=>{
   try{
    const headers=new Headers();
    for(let i=0;i<incoming.rawHeaders.length;i+=2)headers.append(incoming.rawHeaders[i],incoming.rawHeaders[i+1]);
    const status=incoming.statusCode||502;
    // Do not follow redirects: the bearer remains on the validated loopback.
    if([204,205,304].includes(status)){incoming.resume();resolve(new Response(null,{status,headers}));return;}
    resolve(new Response(Readable.toWeb(incoming) as ReadableStream<Uint8Array>,{status,headers}));
   }catch(error){incoming.destroy();reject(error);}
  });
  req.on('error',reject);req.end(init.body);
 });
}
