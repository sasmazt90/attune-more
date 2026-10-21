import {NextRequest,NextResponse} from 'next/server';
export const runtime='nodejs';
export const dynamic='force-dynamic';
const fail=(status:number,detail:string)=>NextResponse.json({detail},{status,headers:{'Cache-Control':'no-store'}});
/** Same-origin browser boundary; the backend bearer secret never reaches a bundle. */
export async function POST(request:NextRequest){
 const origin=request.headers.get('origin');
 // NextURL normalizes 127.0.0.1 to localhost. Compare the actual Host, keeping
 // distinct loopback origins distinct and rejecting DNS-rebinding hosts.
 try{
  const host=request.headers.get('host');if(!host||!origin)throw Error();
  const configured=process.env.ATTUNE_MENTAL_TTS_FRONTEND_ORIGIN;
  const expected=new URL(configured||request.nextUrl.protocol+'//'+host);
  if(expected.origin!==origin||expected.host!==host||expected.pathname!=='/'||expected.search||expected.hash||expected.username||expected.password)throw Error();
  if(!configured&&!['localhost','127.0.0.1','[::1]'].includes(expected.hostname))throw Error();
  if(configured&&expected.protocol!=='https:'&&!['localhost','127.0.0.1','[::1]'].includes(expected.hostname))throw Error();
 }catch{return fail(403,'SAME_ORIGIN_REQUIRED');}
 if(!request.headers.get('content-type')?.startsWith('application/json'))return fail(415,'JSON_REQUIRED');
 const token=process.env.ATTUNE_MENTAL_TTS_TOKEN||'';
 if(token.length<32)return fail(503,'NEURAL_TTS_AUTH_UNCONFIGURED');
 let backend:URL;
 try{
  backend=new URL(process.env.ATTUNE_MENTAL_TTS_BACKEND_URL||'http://127.0.0.1:8000');
  if(backend.protocol!=='http:'||!['127.0.0.1','localhost','[::1]'].includes(backend.hostname)||backend.username||backend.password||backend.pathname!=='/'||backend.search||backend.hash)throw Error();
 }catch{return fail(503,'NEURAL_TTS_LOOPBACK_BACKEND_REQUIRED');}
 let payload:{text:string;language:string;speechConsent:boolean};
 try{
  // Bound actual streamed bytes, including requests without Content-Length.
  const reader=request.body?.getReader();if(!reader)return fail(422,'INVALID_SPEECH');
  const parts:Uint8Array[]=[];let size=0;
  while(true){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>20000){await reader.cancel();return fail(413,'SPEECH_TOO_LARGE');}parts.push(value);}
  const bytes=new Uint8Array(size);let at=0;for(const part of parts){bytes.set(part,at);at+=part.length;}
  const value=JSON.parse(new TextDecoder().decode(bytes));
  if(typeof value?.text!=='string'||!value.text.trim()||value.text.length>4096||!['tr','en','de'].includes(value.language)||value.speechConsent!==true)return fail(422,'INVALID_SPEECH');
  payload={text:value.text,language:value.language,speechConsent:true};
 }catch{return fail(422,'INVALID_SPEECH');}
 const controller=new AbortController(),cancel=()=>controller.abort();
 request.signal.addEventListener('abort',cancel,{once:true});
 const deadline=setTimeout(cancel,95000);
 try{
  if(request.signal.aborted)return fail(499,'SPEECH_CANCELLED');
  const target=new URL('/api/mental/neural-speech',backend);target.searchParams.set('language',payload.language);
  const response=await fetch(target,{method:'POST',cache:'no-store',headers:{'Content-Type':'application/json','Authorization':'Bearer '+token},body:JSON.stringify(payload),signal:controller.signal});
  if(!response.ok)return fail([401,403,409,422,429,503,504].includes(response.status)?response.status:503,'NEURAL_TTS_UNAVAILABLE');
  if(response.headers.get('content-type')?.split(';')[0]!=='audio/wav'||response.headers.get('x-tts-source')!=='chatterbox-multilingual-v3'||response.headers.get('x-tts-locale')!==({tr:'tr-TR',en:'en-US',de:'de-DE'}[payload.language]))return fail(502,'INVALID_TTS_RESPONSE');
  const reader=response.body?.getReader();if(!reader)return fail(502,'INVALID_TTS_RESPONSE');
  const chunks:Uint8Array[]=[];let size=0;
  while(true){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>8*1024*1024){await reader.cancel();return fail(502,'TTS_RESPONSE_TOO_LARGE');}chunks.push(value);}
  if(size<=44||controller.signal.aborted)return fail(502,'INVALID_TTS_RESPONSE');
  const bytes=new Uint8Array(size);let at=0;for(const chunk of chunks){bytes.set(chunk,at);at+=chunk.length;}
  return new Response(bytes,{headers:{'Content-Type':'audio/wav','Cache-Control':'no-store','X-Content-Type-Options':'nosniff','X-TTS-Source':'chatterbox-multilingual-v3','X-TTS-Locale':response.headers.get('x-tts-locale')!}});
 }catch{return fail(controller.signal.aborted?504:503,'NEURAL_TTS_UNAVAILABLE');}
 finally{clearTimeout(deadline);request.signal.removeEventListener('abort',cancel);}
}
