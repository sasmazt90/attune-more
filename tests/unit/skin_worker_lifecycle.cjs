const fs=require('fs'),ts=require('typescript'),vm=require('vm'),assert=require('node:assert/strict');
const {test}=require('node:test');
function fixture(){
 const workers=[],timers=new Map();let sequence=0;
 class Worker{constructor(){workers.push(this);this.sent=[];}postMessage(value){this.sent.push(value);}terminate(){this.terminated=true;}}
 const source=fs.readFileSync('apps/vehicle-app/src/utils/skinInference.ts','utf8').replace("new URL('./skinInference.worker.ts', import.meta.url)","'worker-fixture'");
 const context={exports:{},Worker,setTimeout:fn=>{const id=++sequence;timers.set(id,fn);return id;},clearTimeout:id=>timers.delete(id),createImageBitmap:async()=>({close(){}})};
 vm.runInNewContext(ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS}}).outputText,context);
 return {Engine:context.exports.SkinInference,workers,timers};
}
test('concurrent startup callers share the actual ready response',async()=>{
 const {Engine,workers,timers}=fixture(),engine=new Engine();const first=engine.initialize(),second=engine.initialize();assert.equal(first,second);assert.equal(workers[0].sent.length,1);
 workers[0].onmessage({data:{id:workers[0].sent[0].id,ready:true}});await first;assert.equal(timers.size,0);engine.close();
});
test('startup timeout terminates stalled worker; fresh retry can initialize',async()=>{
 const {Engine,workers,timers}=fixture(),engine=new Engine();const first=engine.initialize();const failure=assert.rejects(first,/yanıt vermiyor/);[...timers.values()][0]();await failure;assert(workers[0].terminated);
 const replacement=new Engine(),ready=replacement.initialize();workers[1].onmessage({data:{id:workers[1].sent[0].id,ready:true}});await ready;assert(!workers[1].terminated);replacement.close();
});
test('unreadable worker response rejects pending startup and releases resources',async()=>{
 const {Engine,workers}=fixture(),engine=new Engine(),ready=engine.initialize();const failure=assert.rejects(ready,/kapatıldı/);workers[0].onmessageerror();await failure;assert(workers[0].terminated);
});
