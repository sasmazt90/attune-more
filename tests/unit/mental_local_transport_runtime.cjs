/** Real loopback HTTP transport, synthetic bytes only; no provider or inference. */
require('./ts_loader.js');const assert=require('assert/strict'),http=require('node:http');
const {mentalLocalTransport}=require('../../apps/vehicle-app/src/utils/mentalLocalTransport.ts');
global.fetch=()=>{throw Error('Node fetch header-timeout path must not be used');};
const delay=ms=>new Promise(done=>setTimeout(done,ms));
(async()=>{
 let hits=[],closed=0;const timers=new Set();
 const server=http.createServer((req,res)=>{
  hits.push({url:req.url,authorization:req.headers.authorization});
  res.on('close',()=>closed++);
  req.resume();
  if(req.url==='/redirect'){res.writeHead(302,{Location:'/should-not-follow'});res.end();return;}
  if(req.url==='/stream'){res.writeHead(200,{'Content-Type':'audio/wav'});res.write(Buffer.alloc(50));return;}
  const timer=setTimeout(()=>{timers.delete(timer);if(!res.destroyed){res.writeHead(200,{'Content-Type':'audio/wav'});res.end(Buffer.alloc(100));}},150);timers.add(timer);
 });
 await new Promise(done=>server.listen(0,'127.0.0.1',done));const base='http://127.0.0.1:'+server.address().port;
 const init=signal=>({headers:{'Content-Type':'application/json',Authorization:'Bearer synthetic-noncredential'},body:'{}',signal});
 try{
  const response=await mentalLocalTransport(new URL(base+'/slow-headers'),init(new AbortController().signal));
  assert.equal(response.status,200);assert.equal((await response.arrayBuffer()).byteLength,100);assert.equal(hits[0].authorization,'Bearer synthetic-noncredential');
  const redirect=await mentalLocalTransport(new URL(base+'/redirect'),init(new AbortController().signal));assert.equal(redirect.status,302);await redirect.arrayBuffer();assert(!hits.some(x=>x.url==='/should-not-follow'));
  const before=closed,waiting=new AbortController();
  const blocked=mentalLocalTransport(new URL(base+'/abort-headers'),init(waiting.signal));await delay(30);waiting.abort();await assert.rejects(blocked);await delay(30);assert(closed>before,'Caller cancellation must close the pending socket');
  const streaming=new AbortController();const stream=await mentalLocalTransport(new URL(base+'/stream'),init(streaming.signal));const reader=stream.body.getReader();assert.equal((await reader.read()).value.byteLength,50);streaming.abort();await assert.rejects(reader.read());
  assert.throws(()=>mentalLocalTransport(new URL('https://example.com/'),init(new AbortController().signal)),/LOOPBACK_REQUIRED/);
  assert.throws(()=>mentalLocalTransport(new URL('http://user:pass@127.0.0.1/'),init(new AbortController().signal)),/LOOPBACK_REQUIRED/);
  const canceled=new AbortController();canceled.abort();await assert.rejects(mentalLocalTransport(new URL(base+'/already-canceled'),init(canceled.signal)));
  console.log('PASS actual loopback delayed headers, unchanged bytes, no redirect, header/body cancellation and origin bounds; explicit HTTP fixtures');
 }finally{for(const timer of timers)clearTimeout(timer);server.closeAllConnections();await new Promise(done=>server.close(done));}
})().catch(e=>{console.error(e);process.exitCode=1;});
