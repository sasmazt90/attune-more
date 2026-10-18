"""Actual service timeout/stale-source/cancel semantics; worker event stub only.
Physical/clinical behavior is not asserted by this unit test.
"""
import subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def test_source_binding_cancel_deadline_and_reuse():
 script=r'''
const fs=require('fs'),ts=require('typescript'),Module=require('module'),assert=require('assert/strict');
let count=0,workers=[],timers=[],clock=0;
global.performance={now:()=>++clock};global.setTimeout=(f,ms)=>{const t={f,ms};timers.push(t);return t};global.clearTimeout=t=>{t.cleared=true};
global.Worker=class{constructor(){count++;workers.push(this)}postMessage(m){this.last=m}terminate(){this.terminated=true}};
let source=fs.readFileSync('apps/vehicle-app/src/utils/skinLocalMaps.ts','utf8').replace("new URL('./skinLocalMaps.worker.ts',import.meta.url)","'actual-bundled-worker-url-test-stub'");
const m=new Module('service',module);m.paths=module.paths;m._compile(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText,'service');
(async()=>{
 const s=new m.exports.SkinLocalAnalysis(),snap={width:1,height:1,angle:'FRONT',meshes:{},exclusions:[]};
 let promise=s.analyze(snap,new Uint8ClampedArray(4),true,()=>true,'original');
 assert.equal(count,1);workers[0].onmessage({data:{ready:true}});workers[0].onmessage({data:{id:1,photoId:'original',maps:{},analysisMs:1,allocatedBytes:4}});assert.equal((await promise).photoId,'original');
 promise=s.analyze(snap,new Uint8ClampedArray(4),true,()=>true,'different');assert.equal(count,1);
 workers[0].onmessage({data:{id:2,photoId:'old',maps:{}}});await assert.rejects(promise,/STALE_SOURCE/);
 promise=s.analyze(snap,new Uint8ClampedArray(4),true,()=>false);workers[0].onmessage({data:{id:3,photoId:'original',maps:{}}});await assert.rejects(promise,/STALE_SOURCE/);
 promise=s.analyze(snap,new Uint8ClampedArray(4),true,()=>true);assert.equal(timers.at(-1).ms,2500);timers.at(-1).f();await assert.rejects(promise,/CANCELLED_OR_TIMEOUT/);assert(workers[0].terminated);
 promise=s.analyze(snap,new Uint8ClampedArray(4),true,()=>true);assert.equal(count,2);s.cancel();await assert.rejects(promise,/CANCELLED_OR_TIMEOUT/);assert(workers[1].terminated);
 assert(timers.every(t=>t.cleared));
})().catch(e=>{process.stderr.write(String(e));process.exitCode=1});
'''
 r=subprocess.run(['node','-e',script],cwd=ROOT,capture_output=True,text=True,encoding='utf8');assert r.returncode==0,r.stdout+r.stderr
